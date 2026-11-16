"""Google OAuth consent, PKCE and encrypted refresh-token persistence."""
import base64
import json
import threading
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import SMTP
import httplib2
import google_auth_httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = [
    "openid", "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/contacts.readonly",
]

class Google:
    def __init__(self, settings, store):
        self.s, self.store = settings, store
        self.lock = threading.Lock()

    def flow(self, **kwargs):
        if not self.s.google_client_id or not self.s.google_client_secret:
            raise PermissionError("Google OAuth client is not configured")
        return Flow.from_client_config({"web": {
            "client_id": self.s.google_client_id, "client_secret": self.s.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }}, scopes=SCOPES, redirect_uri=self.s.public_url+"/oauth/google/callback", **kwargs)

    def start(self, binding):
        flow = self.flow(autogenerate_code_verifier=True)
        url, state = flow.authorization_url(
            access_type="offline", prompt="consent", include_granted_scopes="true",
            login_hint=self.s.google_email)
        self.store.put("oauth:"+state, dict(
            binding=binding, verifier=flow.code_verifier, expires=time.time()+600))
        return url

    def complete(self, state, code, binding):
        saved = self.store.get("oauth:"+state)
        import secrets
        if not saved or saved["expires"] < time.time() or not secrets.compare_digest(saved["binding"], binding):
            raise PermissionError("OAuth browser binding or state invalid")
        saved = self.store.take("oauth:"+state)
        if not saved:
            raise PermissionError("OAuth state already consumed")
        flow = self.flow(state=state, code_verifier=saved["verifier"])
        flow.fetch_token(code=code, timeout=20)
        creds = flow.credentials
        identity = id_token.verify_oauth2_token(creds.id_token, Request(), self.s.google_client_id)
        if not identity.get("email_verified") or identity.get("email", "").casefold() != self.s.google_email.casefold():
            raise PermissionError("Google account does not match the allowed owner")
        if not creds.refresh_token:
            raise PermissionError("Offline access not granted; revoke consent and reconnect")
        self.store.put("google_credentials", json.loads(creds.to_json()))
        self.store.put("google_identity", {"email": identity["email"], "sub": identity["sub"]})
        self.store.audit("google_connected")

    def service(self, api, version):
        with self.lock:
            raw = self.store.get("google_credentials")
            if not raw:
                raise PermissionError("Google consent is required")
            if raw.get("token_uri") != "https://oauth2.googleapis.com/token":
                raise PermissionError("Invalid stored token endpoint")
            creds = Credentials.from_authorized_user_info(raw, SCOPES)
            if not creds.valid:
                creds.refresh(Request())
                self.store.put("google_credentials", json.loads(creds.to_json()))
        transport = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http(timeout=20))
        return build(api, version, http=transport, cache_discovery=False)

    def inbox(self):
        gmail = self.service("gmail", "v1")
        page = None
        for _ in range(5):
            result = gmail.users().messages().list(
                userId="me", q="in:inbox newer_than:7d", maxResults=100,
                **({"pageToken": page} if page else {})).execute(num_retries=2)
            for item in result.get("messages", []):
                yield item["id"], gmail
            page = result.get("nextPageToken")
            if not page:
                break

    def message(self, gmail, message_id):
        return gmail.users().messages().get(userId="me", id=message_id, format="full").execute(num_retries=2)

    def send(self, payload, draft=False):
        msg = EmailMessage(policy=SMTP)
        msg["To"], msg["From"], msg["Subject"] = payload["to"], self.s.google_email, payload["subject"]
        if payload.get("in_reply_to"):
            msg["In-Reply-To"], msg["References"] = payload["in_reply_to"], payload["in_reply_to"]
        msg.set_content(payload["body"])
        raw = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}
        if payload.get("thread_id"):
            raw["threadId"] = payload["thread_id"]
        gmail = self.service("gmail", "v1")
        if draft:
            return gmail.users().drafts().create(userId="me", body={"message": raw}).execute(num_retries=0)
        return gmail.users().messages().send(userId="me", body=raw).execute(num_retries=0)

    def events(self, start, end):
        service = self.service("calendar", "v3")
        result, page = [], None
        while True:
            chunk = service.events().list(calendarId="primary", timeMin=start, timeMax=end,
              singleEvents=True, maxResults=100, **({"pageToken": page} if page else {})).execute(num_retries=2)
            result.extend(chunk.get("items", []))
            page = chunk.get("nextPageToken")
            if not page:
                return result

    def appointment(self, payload, action_id):
        if any(e.get("status") != "cancelled" and e.get("transparency") != "transparent"
               for e in self.events(payload["start"], payload["end"])):
            raise ValueError("Calendar conflict requires a revised proposal and approval")
        body = {
            "id": action_id, "summary": payload["title"], "description": payload["details"],
            "start": {"dateTime": payload["start"]}, "end": {"dateTime": payload["end"]},
        }
        if payload.get("attendee"):
            body["attendees"] = [{"email": payload["attendee"]}]
        return self.service("calendar", "v3").events().insert(
            calendarId="primary", body=body,
            sendUpdates="all" if payload.get("attendee") else "none").execute(num_retries=0)

    def contacts(self, query):
        return self.service("people", "v1").people().searchContacts(
            query=query, readMask="names,emailAddresses,phoneNumbers", pageSize=10).execute(num_retries=2)

    def probe(self):
        checks = {}
        for name, callback in {
            "gmail": lambda: self.service("gmail", "v1").users().getProfile(userId="me").execute(num_retries=1),
            "calendar": lambda: self.events(datetime.now(timezone.utc).isoformat(),
                datetime.fromtimestamp(time.time()+3600, timezone.utc).isoformat()),
            "contacts": lambda: self.service("people", "v1").people().connections().list(
                resourceName="people/me", personFields="names", pageSize=1).execute(num_retries=1),
        }.items():
            try:
                callback()
                checks[name] = {"status": "verified_read", "at": time.time()}
            except Exception as exc:
                checks[name] = {"status": "blocked", "error_type": type(exc).__name__, "at": time.time()}
        self.store.put("google_probe", checks)
        return checks
