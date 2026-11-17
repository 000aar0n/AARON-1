"""Credential setup and cookie authentication contracts; all provider calls are mocked."""
import json
import time
from dataclasses import replace
from unittest.mock import MagicMock, patch
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from jarvis_service.app import create_app
from jarvis_service.config import Settings
from jarvis_service.setup import RuntimeSettings, ProviderSettings, Sessions
from jarvis_service.store import Store
from jarvis_service.inbox import Brain

@pytest.fixture
def settings(tmp_path):
    return Settings(public_url="https://jarvis.example",owner_token="x"*40,
        encryption_key=Fernet.generate_key().decode(),google_email="owner@example.com",
        data_dir=str(tmp_path),scheduler_enabled=False)

@pytest.fixture
def client(settings):
    app=create_app(settings)
    with TestClient(app,base_url=settings.public_url) as c:
        yield c,app

def login(client,settings):
    r=client.post("/api/session/login",json={"token":settings.owner_token},
                  headers={"Origin":settings.public_url})
    assert r.status_code==200
    return r.json()["csrf_token"]

def test_login_sets_private_cookie_and_does_not_return_owner_token(client,settings):
    c,app=client
    csrf=login(c,settings)
    assert csrf
    assert c.get("/api/status").status_code==200
    r=c.get("/api/session")
    assert settings.owner_token not in r.text
    assert "httponly" in c.post("/api/session/login",json={"token":settings.owner_token}).headers["set-cookie"].lower()
    assert c.cookies.get("jarvis_session")!=settings.owner_token
    assert c.get("/api/session").json()["authenticated"] is True

def test_cookie_writes_need_csrf_and_exact_origin(client,settings):
    c,app=client
    csrf=login(c,settings)
    assert c.post("/api/pause").status_code==403
    assert c.post("/api/pause",headers={"Origin":"https://evil.example","X-Jarvis-CSRF":csrf}).status_code==403
    assert c.post("/api/pause",headers={"Origin":settings.public_url,"X-Jarvis-CSRF":csrf}).status_code==200

def test_logout_revokes_session(client,settings):
    c,app=client
    csrf=login(c,settings)
    assert c.post("/api/session/logout",headers={"Origin":settings.public_url,"X-Jarvis-CSRF":csrf}).status_code==200
    assert c.get("/api/status").status_code==401

def test_session_expiry_and_login_rate_limit(settings):
    store=Store(settings.data_dir,settings.encryption_key)
    sessions=Sessions(settings,store)
    cookie,csrf=sessions.login(settings.owner_token,"owner")
    store.put("session:"+sessions.digest(cookie),{"expires":time.time()-1,"csrf":csrf})
    assert sessions.get(cookie) is None
    for _ in range(5):
        with pytest.raises(PermissionError):
            sessions.login("bad","client")
    with pytest.raises(PermissionError,match="Too many"):
        sessions.login(settings.owner_token,"client")

def test_public_settings_denied_and_cannot_replace_owner_token(client,settings):
    c,app=client
    assert c.get("/api/setup").status_code==401
    assert c.put("/api/settings",json={"openai_key":"private-test-secret"}).status_code==401
    h={"Authorization":"Bearer "+settings.owner_token}
    assert c.put("/api/settings",json={"owner_token":"attacker"},headers=h).status_code==422

def test_private_settings_are_encrypted_not_echoed_and_survive_restart(client,settings):
    c,app=client
    h={"Authorization":"Bearer "+settings.owner_token}
    secret="private-model-key-123456789"
    r=c.put("/api/settings",json={"openai_key":secret,"google_client_secret":"google-secret-12345",
        "google_client_id":"client.apps.googleusercontent.com"},headers=h)
    assert r.status_code==200 and secret not in r.text
    assert r.json()["model"]["configured"] is True
    assert r.json()["google"]["configured"] is True
    assert r.json()["model"]["allowance_active"] is False
    assert secret.encode() not in open(app.state.store.path,"rb").read()
    restarted=RuntimeSettings(settings,Store(settings.data_dir,settings.encryption_key))
    assert restarted.openai_key==secret
    assert restarted.google_client_id=="client.apps.googleusercontent.com"
    assert app.state.store.get("inference_grant") is None

def test_invalid_secret_does_not_echo_in_validation_response(client,settings):
    c,app=client
    h={"Authorization":"Bearer "+settings.owner_token}
    secret="secret with spaces"
    r=c.put("/api/settings",json={"openai_key":secret},headers=h)
    assert r.status_code==422 and secret not in r.text

def test_settings_change_does_not_send_call_or_grant_budget(client,settings):
    c,app=client
    h={"Authorization":"Bearer "+settings.owner_token}
    with patch.object(app.state.voice,"place") as call,patch.object(app.state.google,"send") as send:
        r=c.put("/api/settings",json={"twilio_sid":"AC123","twilio_token":"private-twilio-token",
                                   "twilio_number":"+12125550100"},headers=h)
    assert r.status_code==200
    call.assert_not_called()
    send.assert_not_called()
    assert app.state.store.actions()==[]

def test_new_form_configuration_reaches_live_clients(client,settings):
    c,app=client
    h={"Authorization":"Bearer "+settings.owner_token}
    c.put("/api/settings",json={"google_client_id":"new-client","google_client_secret":"private-new-secret"},headers=h)
    assert app.state.google.s.google_client_id=="new-client"
    assert app.state.google.s.google_client_secret=="private-new-secret"

def test_model_key_check_is_read_only_and_does_not_reserve_budget(settings):
    store=Store(settings.data_dir,settings.encryption_key)
    s=RuntimeSettings(settings,store)
    s.update(ProviderSettings(openai_key="private-key-123456"))
    brain=Brain(s,store)
    with patch("httpx.Client") as client:
        result=brain.probe()
        client.return_value.__enter__.return_value.get.assert_called_once()
        client.return_value.__enter__.return_value.post.assert_not_called()
    assert result["status"]=="verified_key_only"
    assert store.get("inference_grant") is None

def test_personal_engine_uses_context_key_and_never_environment_key():
    from jarvis_service.inference import PersonalCloudEngine,key_scope,_KEY
    with patch("jarvis_service.inference.OpenAI") as sdk:
        with key_scope("private-key"):
            engine=PersonalCloudEngine()
        sdk.assert_called_once_with(api_key="private-key",base_url="https://api.openai.com/v1",max_retries=0,timeout=45.0)
    assert _KEY.get() is None
    with pytest.raises(PermissionError):
        PersonalCloudEngine()

def test_real_official_sdk_resolves_private_engine_without_network(settings):
    from openjarvis import Jarvis
    from openjarvis.core.config import JarvisConfig
    from jarvis_service.inference import PersonalCloudEngine,key_scope
    cfg=JarvisConfig()
    cfg.telemetry.enabled=False
    cfg.analytics.enabled=False
    cfg.traces.enabled=False
    cfg.security.audit_log_path=":memory:"
    with key_scope("private-test-key"),patch.object(PersonalCloudEngine,"generate",
            return_value={"content":"SDK ready","usage":{}}):
        with Jarvis(config=cfg,engine_key="personal_cloud",model="gpt-4o-mini") as agent:
            assert agent.ask("Hello",context=False)=="SDK ready"

def test_google_callback_returns_to_app_and_records_denial(client,settings):
    c,app=client
    r=c.get("/oauth/google/callback?error=access_denied",follow_redirects=False)
    assert r.status_code==303 and r.headers["location"]==settings.public_url+"/?google=error"
    assert app.state.store.get("google_last_error")["code"]=="access_denied"

def test_cookie_session_survives_app_recreation(settings):
    with TestClient(create_app(settings),base_url=settings.public_url) as first:
        login(first,settings)
        cookie=first.cookies.get("jarvis_session")
    with TestClient(create_app(settings),base_url=settings.public_url) as second:
        second.cookies.set("jarvis_session",cookie,domain="jarvis.example",path="/")
        assert second.get("/api/status").status_code==200

def test_missing_provider_config_blocks_signin_in_setup_status(client,settings):
    c,app=client
    data=c.get("/api/setup",headers={"Authorization":"Bearer "+settings.owner_token}).json()
    assert not data["model"]["configured"] and not data["google"]["configured"]
    assert data["google"]["redirect_uri"]==settings.public_url+"/oauth/google/callback"
    assert not data["phone"]["configured"]

def test_real_google_authorization_url_contains_pkce_without_network(settings):
    from urllib.parse import urlsplit,parse_qs
    from jarvis_service.google import Google
    store=Store(settings.data_dir,settings.encryption_key)
    g=Google(replace(settings,google_client_id="synthetic.apps.googleusercontent.com",
                     google_client_secret="synthetic-google-secret"),store)
    url=g.start("browser-binding")
    parts=urlsplit(url)
    query=parse_qs(parts.query)
    assert parts.hostname=="accounts.google.com"
    assert query["code_challenge_method"]==["S256"]
    assert query["access_type"]==["offline"]
    assert query["redirect_uri"]==[settings.public_url+"/oauth/google/callback"]
    assert query["login_hint"]==[settings.google_email]
    saved=store.get("oauth:"+query["state"][0])
    assert saved["binding"]=="browser-binding" and saved["verifier"]

def test_twilio_account_probe_does_not_require_openai_key(settings):
    from jarvis_service.voice import Voice
    store=Store(settings.data_dir,settings.encryption_key)
    s=replace(settings,twilio_sid="AC123",twilio_token="synthetic-token",openai_key="")
    with patch("jarvis_service.voice.Client") as client:
        client.return_value.api.accounts.return_value.fetch.return_value.status="active"
        result=Voice(s,store).probe()
    assert result["status"]=="verified_account_only"
    assert result["account_status"]=="active"

def test_official_sdk_preserves_exact_recipient_data_while_secret_scanning_stays_enabled(settings):
    from jarvis_service.inference import PersonalCloudEngine
    store=Store(settings.data_dir,settings.encryption_key)
    store.put("inference_grant",{"model":settings.text_model,"remaining":1,"expires":time.time()+60})
    s=replace(settings,openai_key="synthetic-private-key")
    seen=[]
    def generate(messages,**kwargs):
        seen.extend(m.content for m in messages)
        return {"content":json.dumps({"to":"friend@example.com","subject":"Lesson","body":"Hi"}),"usage":{}}
    with patch.object(PersonalCloudEngine,"generate",side_effect=generate):
        result=Brain(s,store).complete_json("Prepare a draft for the exact recipient.",
                                          {"recipient":"friend@example.com"})
    assert any("friend@example.com" in prompt for prompt in seen)
    assert result["to"]=="friend@example.com"
