"""Gmail OAuth for local AARON-1. Read-only, user-authorized, no passwords.

Requires a Google Cloud Web OAuth client with http://localhost:8501
registered as an authorized redirect URI. Credentials and tokens are stored
only in gitignored data/ on the user's own machine.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CLIENT_FILE = DATA / "gmail_client.json"
TOKEN_FILE = DATA / "gmail_token.json"
PENDING_FILE = DATA / "gmail_auth_pending.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
REDIRECT_URI = "http://localhost:8501"


def secure_save(path, payload):
    DATA.mkdir(parents=True, exist_ok=True)
    path = Path(path)
    pending = path.with_suffix(path.suffix + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(pending), flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)
    os.replace(pending, path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def store_client_upload(upload: bytes):
    """Validate a Web OAuth JSON export. Never accept raw user passwords."""
    if len(upload) > 128_000:
        raise ValueError("OAuth JSON is too large")
    try:
        obj = json.loads(upload)
    except (ValueError, TypeError) as exc:
        raise ValueError("Upload your Google OAuth Client JSON file") from exc
    web = obj.get("web") if isinstance(obj, dict) else None
    if not isinstance(web, dict) or not web.get("client_id") or not web.get("client_secret"):
        raise ValueError("Create a Web application OAuth client in Google Cloud, then upload its JSON")
    if not str(web.get("auth_uri", "")).startswith("https://accounts.google.com"):
        raise ValueError("Unrecognized Google authorization URL")
    configured = web.get("redirect_uris") or []
    if REDIRECT_URI not in configured and REDIRECT_URI + "/" not in configured:
        raise ValueError("In Google Cloud, register http://localhost:8501 as an authorized redirect URI")
    secure_save(CLIENT_FILE, json.dumps({"web": web}))
    return True


def client_ready():
    return CLIENT_FILE.is_file()


def connected():
    """Only confirms that a credential file exists, not that its token is valid."""
    return TOKEN_FILE.is_file()


def make_auth_url():
    from google_auth_oauthlib.flow import Flow
    if not client_ready():
        raise RuntimeError("First upload a Google OAuth client JSON")
    config = json.loads(CLIENT_FILE.read_text(encoding="utf-8"))
    flow = Flow.from_client_config(config, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    state = secrets.token_urlsafe(32)
    url, actual_state = flow.authorization_url(
        access_type="offline", prompt="consent", state=state,
        include_granted_scopes="false"
    )
    secure_save(PENDING_FILE, json.dumps({"state": actual_state, "at": time.time()}))
    return url


def finish_auth(query):
    """Validate state and exchange the Google callback code for read-only token."""
    from google_auth_oauthlib.flow import Flow
    if not PENDING_FILE.exists():
        raise RuntimeError("No login was started from this dashboard")
    pending = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    if time.time() - float(pending.get("at", 0)) > 600:
        raise RuntimeError("Login expired. Please restart Gmail connection.")
    if query.get("error"):
        raise RuntimeError("Google did not grant access")
    if not secrets.compare_digest(str(query.get("state", "")), str(pending.get("state", ""))):
        raise RuntimeError("Login security check failed")
    code = query.get("code")
    if not code or not isinstance(code, str):
        raise RuntimeError("Google did not return an authorization code")

    config = json.loads(CLIENT_FILE.read_text(encoding="utf-8"))
    flow = Flow.from_client_config(config, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    flow.fetch_token(code=code)
    granted = set(flow.credentials.scopes or SCOPES)
    if not set(SCOPES).issubset(granted):
        raise RuntimeError("Read-only Gmail permission wasn't granted")
    secure_save(TOKEN_FILE, flow.credentials.to_json())
    PENDING_FILE.unlink(missing_ok=True)
    return True


def load_credentials():
    from google.oauth2.credentials import Credentials
    if not connected():
        raise RuntimeError("Connect Gmail first")
    return Credentials.from_authorized_user_file(str(TOKEN_FILE), scopes=SCOPES)


def gmail_service():
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=load_credentials(), cache_discovery=False)


def check_account():
    service = gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    return profile.get("emailAddress", "Connected Gmail account")


def list_messages(search="in:inbox", max_results=15):
    """Fetch Gmail metadata and short snippets, never download full bodies."""
    from googleapiclient.errors import HttpError
    max_results = max(1, min(30, int(max_results)))
    service = gmail_service()
    data = service.users().messages().list(userId="me", q=search, maxResults=max_results).execute()
    rows = []
    for item in data.get("messages", []):
        msg = service.users().messages().get(
            userId="me", id=item["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = {h.get("name", "").lower(): h.get("value", "")
                   for h in msg.get("payload", {}).get("headers", [])}
        rows.append({
            "id": item["id"],
            "subject": headers.get("subject", "(no subject)")[:250],
            "from": headers.get("from", "")[:250],
            "date": headers.get("date", "")[:120],
            "snippet": msg.get("snippet", "")[:300],
        })
    return rows


def disconnect():
    TOKEN_FILE.unlink(missing_ok=True)
    PENDING_FILE.unlink(missing_ok=True)
