"""Owner sessions and encrypted provider configuration. No Google passwords."""
import hashlib
import secrets
import threading
import time
from typing import Literal
from pydantic import Field, SecretStr, field_validator
from .schemas import Strict

PRIVATE_FIELDS = ("openai_key","google_client_id","google_client_secret",
                  "twilio_sid","twilio_token","twilio_number")

class Login(Strict):
    token: SecretStr

class ProviderSettings(Strict):
    openai_key: SecretStr | None = None
    google_client_id: str | None = Field(default=None,max_length=300)
    google_client_secret: SecretStr | None = None
    twilio_sid: str | None = Field(default=None,max_length=100)
    twilio_token: SecretStr | None = None
    twilio_number: str | None = Field(default=None,max_length=30)

    @field_validator("openai_key","google_client_secret","twilio_token")
    @classmethod
    def secret_size(cls, value):
        if value is not None:
            raw=value.get_secret_value()
            if raw and (len(raw)<12 or len(raw)>2000 or any(c.isspace() for c in raw)):
                raise ValueError("Invalid secret format")
        return value

class RuntimeSettings:
    """Secrets remain encrypted on disk; clients read the current settings dynamically."""
    def __init__(self, base, store):
        self.base,self.store=base,store
        self.lock=threading.Lock()

    def __getattr__(self,name):
        if name in PRIVATE_FIELDS:
            values=self.store.get("private_settings",{})
            if values.get(name):
                return values[name]
        return getattr(self.base,name)

    def update(self,request):
        values={}
        for name in PRIVATE_FIELDS:
            value=getattr(request,name)
            if isinstance(value,SecretStr):
                value=value.get_secret_value()
            if value:
                values[name]=value.strip()
        if not values:
            raise ValueError("No changes supplied")
        with self.lock:
            current=self.store.get("private_settings",{})
            current.update(values)
            self.store.put("private_settings",current)
        # Config changes revoke cached verification results, never grant spending.
        self.store.put("google_probe",None)
        self.store.put("model_probe",None)
        self.store.audit("owner_updated_provider_settings")
        return self.summary()

    def summary(self):
        grant=self.store.get("inference_grant",{}) or {}
        allowance=bool(grant.get("remaining",0)>0 and grant.get("expires",0)>time.time()
                       and grant.get("model")==self.text_model)
        return {
            "model":{"configured":bool(self.openai_key),"verified":self.store.get("model_probe"),
                     "allowance_active":allowance,"model":self.text_model},
            "google":{"configured":bool(self.google_client_id and self.google_client_secret),
                      "connected":bool(self.store.get("google_credentials")),
                      "email":self.google_email,"redirect_uri":self.public_url+"/oauth/google/callback",
                      "verified":self.store.get("google_probe"),"last_error":self.store.get("google_last_error")},
            "phone":{"configured":bool(self.twilio_sid and self.twilio_token and self.twilio_number),
                     "live_verified":False,"webhook":self.public_url+"/twilio/voice"},
            "notice":"Saving credentials does not approve model charges, calls or external writes.",
        }

class Sessions:
    def __init__(self,settings,store):
        self.s,self.store=settings,store
        self.lock=threading.Lock()

    def login(self,token,client):
        fingerprint=hashlib.sha256(client.encode()).hexdigest()
        with self.lock:
            key="login_rate:"+fingerprint
            rate=self.store.get(key,{"count":0,"until":time.time()+60})
            if rate["until"]<time.time():
                rate={"count":0,"until":time.time()+60}
            if rate["count"]>=5:
                raise PermissionError("Too many attempts. Wait one minute and try again.")
            if not secrets.compare_digest(token,self.s.owner_token):
                rate["count"]+=1
                self.store.put(key,rate)
                raise PermissionError("The owner access token does not match. Copy its value from Render Environment.")
            self.store.put(key,{"count":0,"until":time.time()+60})
        cookie=secrets.token_urlsafe(32)
        csrf=secrets.token_urlsafe(32)
        self.store.put("session:"+self.digest(cookie),{"csrf":csrf,"expires":time.time()+43200})
        self.store.audit("owner_signed_in")
        return cookie,csrf

    @staticmethod
    def digest(cookie):
        return hashlib.sha256(cookie.encode()).hexdigest()

    def get(self,cookie):
        if not cookie or len(cookie)>200:
            return None
        session=self.store.get("session:"+self.digest(cookie))
        if not session or session["expires"]<=time.time():
            return None
        return session

    def logout(self,cookie):
        if cookie:
            self.store.put("session:"+self.digest(cookie),{"expires":0,"csrf":""})
        self.store.audit("owner_signed_out")
