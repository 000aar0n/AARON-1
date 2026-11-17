"""Fail closed: secrets arrive through the host secret manager, never source code."""
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

@dataclass(frozen=True)
class Settings:
    public_url: str
    owner_token: str
    encryption_key: str
    google_email: str
    data_dir: str = "/var/lib/jarvis"
    google_client_id: str = ""
    google_client_secret: str = ""
    openai_key: str = ""
    text_model: str = "gpt-4o-mini"
    voice_model: str = "gpt-realtime"
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_number: str = ""
    monitor_seconds: int = 300
    scheduler_enabled: bool = True
    test_mode: bool = False

    def validate(self):
        u = urlsplit(self.public_url)
        if u.scheme != "https" or not u.hostname or u.path not in ("", "/") or u.query or u.fragment or u.username:
            raise ValueError("PUBLIC_URL must be an HTTPS origin")
        if len(self.owner_token) < 32:
            raise ValueError("OWNER_TOKEN must have at least 32 characters")
        if not self.google_email or "@" not in self.google_email:
            raise ValueError("GOOGLE_ALLOWED_EMAIL is required")
        if self.monitor_seconds < 60:
            raise ValueError("MONITOR_SECONDS must be at least 60")
        from cryptography.fernet import Fernet
        Fernet(self.encryption_key.encode())
        return self

    @classmethod
    def from_env(cls):
        return cls(
            public_url=(os.getenv("PUBLIC_URL") or os.environ["RENDER_EXTERNAL_URL"]).rstrip("/"),
            owner_token=os.environ["OWNER_TOKEN"],
            encryption_key=os.environ["TOKEN_ENCRYPTION_KEY"],
            google_email=os.environ["GOOGLE_ALLOWED_EMAIL"],
            data_dir=os.getenv("DATA_DIR", "/var/lib/jarvis"),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            openai_key=os.getenv("OPENAI_API_KEY", ""),
            text_model=os.getenv("TEXT_MODEL", "gpt-4o-mini"),
            voice_model=os.getenv("VOICE_MODEL", "gpt-realtime"),
            twilio_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
            twilio_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
            twilio_number=os.getenv("TWILIO_PHONE_NUMBER", ""),
            monitor_seconds=int(os.getenv("MONITOR_SECONDS", "300")),
            scheduler_enabled=os.getenv("SCHEDULER_ENABLED", "true") == "true",
        ).validate()
