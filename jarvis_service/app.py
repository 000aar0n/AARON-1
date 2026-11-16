"""Single-process service: durable scheduler, owner review, OAuth, signed voice hooks."""
import asyncio
import contextlib
import logging
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from .config import Settings
from .store import Store
from .schemas import Proposal, Approval
from .google import Google
from .inbox import Brain, Inbox
from .voice import Voice

class Executor:
    def __init__(self, settings, store, google, voice):
        self.s, self.store, self.google, self.voice = settings, store, google, voice

    def execute(self, action_id):
        if self.store.get("paused", False):
            raise PermissionError("Jarvis is paused")
        a = self.store.claim(action_id)
        p, kind = a["payload"], a["kind"]
        try:
            # Always validate again at the execution boundary.
            p = Proposal(kind=kind, payload=p).validated_payload()
            if kind == "send_email":
                result = self.google.send(p)
            elif kind == "save_draft":
                result = self.google.send(p, draft=True)
            elif kind == "create_appointment":
                result = self.google.appointment(p, action_id)
            elif kind == "place_call":
                result = self.voice.place(p, action_id)
            elif kind == "receive_call":
                result = self.voice.arm_receive(p, action_id, a["expires"])
            elif kind == "inference_allowance":
                if p["model"] != self.s.text_model:
                    raise ValueError("Allowance model must match configured TEXT_MODEL")
                self.store.put("inference_grant", {"model": p["model"], "remaining": p["requests"],
                                                   "expires": time.time()+p["hours"]*3600})
                result = {"status": "allowance_enabled", "requests": p["requests"], "hours": p["hours"]}
            else:
                raise PermissionError("Action type is not implemented")
            self.store.finish(action_id, "succeeded", result)
        except (PermissionError, ValueError, ValidationError) as exc:
            self.store.finish(action_id, "failed", {"error_type": type(exc).__name__})
        except Exception as exc:
            # Unknown provider outcome: NEVER retry a send, call, or booking automatically.
            self.store.finish(action_id, "uncertain", {"error_type": type(exc).__name__,
                "instruction": "Inspect the provider before creating a new action. Do not retry blindly."})
        return self.store.action(action_id)

def create_app(settings=None, google_override=None, voice_override=None, brain_override=None):
    s = (settings or Settings.from_env()).validate()
    store = Store(s.data_dir, s.encryption_key)
    google = google_override or Google(s, store)
    voice = voice_override or Voice(s, store)
    inbox = Inbox(s, store, google, brain_override or Brain(s, store))
    executor = Executor(s, store, google, voice)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for logger in ("httpx", "httpcore", "googleapiclient", "openai", "websockets"):
        logging.getLogger(logger).setLevel(logging.WARNING)

    async def scheduler():
        while True:
            try:
                if not store.get("paused", False) and store.get("google_credentials"):
                    await asyncio.to_thread(inbox.run)
                store.put("scheduler_heartbeat", time.time())
            except Exception as exc:
                store.audit("monitor_failed", code=type(exc).__name__)
                store.put("last_monitor", {"status": "error", "error_type": type(exc).__name__, "at": time.time()})
            await asyncio.sleep(s.monitor_seconds)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(scheduler()) if s.scheduler_enabled else None
        yield
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="Jarvis owner console", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.inbox, app.state.google = store, inbox, google
    app.state.voice, app.state.executor = voice, executor

    def owner(authorization: str | None = Header(default=None)):
        if not authorization or not secrets.compare_digest(authorization, "Bearer "+s.owner_token):
            raise HTTPException(401, "Owner authentication required")

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers.update({
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'",
            "Strict-Transport-Security": "max-age=31536000",
        })
        return response

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        store.audit("request_failed", code=type(exc).__name__)
        return JSONResponse({"error": "Request failed; inspect redacted audit logs"}, status_code=503)

    @app.exception_handler(PermissionError)
    async def forbidden(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=403)

    @app.exception_handler(ValueError)
    async def conflict(request, exc):
        return JSONResponse({"error": "Invalid, expired, or conflicting request"}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"error": "Not found"}, status_code=404)

    @app.get("/healthz")
    def health():
        with store.db() as db:
            db.execute("SELECT 1").fetchone()
        return {"status": "healthy", "service": "jarvis", "not_a_live_integration_test": True}

    @app.get("/")
    def console():
        return FileResponse(Path(__file__).with_name("index.html"))

    @app.get("/ui.js")
    def script():
        return FileResponse(Path(__file__).with_name("ui.js"), media_type="application/javascript")

    @app.get("/api/status", dependencies=[Depends(owner)])
    def status():
        return {
            "paused": store.get("paused", False),
            "google_connected": bool(store.get("google_credentials")),
            "google_identity": store.get("google_identity"),
            "google_tests": store.get("google_probe"),
            "twilio_configured": bool(s.twilio_sid and s.twilio_token and s.twilio_number),
            "model_key_configured": bool(s.openai_key),
            "inference_allowance": store.get("inference_grant"),
            "scheduler_enabled": s.scheduler_enabled,
            "scheduler_heartbeat": store.get("scheduler_heartbeat"),
            "last_monitor": store.get("last_monitor"),
            "voice_live_verified": False,
            "notice": "Configured is not operational; live send, booking and phone tests need approval.",
        }

    @app.post("/api/oauth/google/start", dependencies=[Depends(owner)])
    def oauth_start(response: Response):
        binding = secrets.token_urlsafe(32)
        url = google.start(binding)
        response.set_cookie("jarvis_oauth", binding, secure=True, httponly=True, samesite="lax", max_age=600,
                            path="/oauth/google/callback")
        return {"url": url}

    @app.get("/oauth/google/callback")
    def oauth_callback(request: Request, state: str, code: str):
        google.complete(state, code, request.cookies.get("jarvis_oauth", ""))
        response = JSONResponse({"status": "connected", "next": "Return to the console and run integration checks"})
        response.delete_cookie("jarvis_oauth", path="/oauth/google/callback", secure=True, httponly=True, samesite="lax")
        return response

    @app.post("/api/probe", dependencies=[Depends(owner)])
    def probe():
        return {"google": google.probe(), "twilio": voice.probe(),
                "voice_audio": "not_tested_requires_one_call_cost_approval",
                "email_send": "not_tested_requires_exact_message_approval",
                "appointment_write": "not_tested_requires_exact_appointment_approval"}

    @app.get("/api/actions", dependencies=[Depends(owner)])
    def actions():
        return store.actions()

    @app.post("/api/actions", dependencies=[Depends(owner)])
    def propose(proposal: Proposal):
        return store.propose(proposal.kind, proposal.validated_payload())

    @app.post("/api/actions/{action_id}/approve", dependencies=[Depends(owner)])
    def approve(action_id: str, approval: Approval):
        store.approve(action_id, approval.digest)
        # One owner click explicitly approves AND executes this exact action.
        return executor.execute(action_id)

    @app.post("/api/actions/{action_id}/reject", dependencies=[Depends(owner)])
    def reject(action_id: str):
        store.reject(action_id)
        return {"status": "rejected"}

    @app.post("/api/pause", dependencies=[Depends(owner)])
    def pause():
        store.put("paused", True)
        store.put("inference_grant", {})
        # Revoke unused inbound grants as well as inference spending authority.
        with store.db() as db:
            keys = [r["k"] for r in db.execute("SELECT k FROM kv WHERE k LIKE 'receive:%'").fetchall()]
        for key in keys:
            store.put(key, {})
        store.audit("owner_paused")
        return {"paused": True, "notice": "An external request already accepted by a provider cannot be undone."}

    @app.post("/api/resume", dependencies=[Depends(owner)])
    def resume():
        store.put("paused", False)
        store.audit("owner_resumed")
        return {"paused": False}

    @app.post("/api/monitor", dependencies=[Depends(owner)])
    def monitor():
        return inbox.run()

    @app.get("/api/inbox", dependencies=[Depends(owner)])
    def messages():
        return inbox.messages()

    @app.post("/api/inbox/{message_id}/draft", dependencies=[Depends(owner)])
    def draft(message_id: str):
        return inbox.reply_proposal(message_id, send=False)

    @app.get("/api/calendar", dependencies=[Depends(owner)])
    def calendar():
        now = datetime.now(timezone.utc)
        return google.events(now.isoformat(), (now+timedelta(days=7)).isoformat())

    @app.get("/api/contacts", dependencies=[Depends(owner)])
    def contacts(q: str):
        if not 1 <= len(q) <= 100:
            raise ValueError("Contact query length")
        return google.contacts(q)

    @app.get("/api/audit", dependencies=[Depends(owner)])
    def audit():
        with store.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM audit ORDER BY seq DESC LIMIT 100")]

    async def twilio_params(request):
        body = await request.body()
        if len(body) > 32768:
            raise HTTPException(413)
        multi = parse_qs(body.decode(), keep_blank_values=True)
        if any(len(values) != 1 for values in multi.values()):
            raise HTTPException(400)
        params = {key: values[0] for key, values in multi.items()}
        if not voice.validate(request.url.path, request.headers.get("x-twilio-signature"), params):
            raise HTTPException(403, "Invalid provider signature")
        return params

    @app.post("/twilio/voice")
    async def incoming(request: Request):
        params = await twilio_params(request)
        result = await asyncio.to_thread(voice.incoming, params)
        return Response(result, media_type="application/xml")

    @app.post("/twilio/status")
    async def call_status(request: Request):
        params = await twilio_params(request)
        if params.get("AccountSid") != s.twilio_sid:
            raise HTTPException(403)
        sid = params.get("CallSid", "")
        known = store.get("voice_call:"+sid)
        if known:
            store.put("voice_result:"+sid, {"status": params.get("CallStatus"),
                                          "duration": params.get("CallDuration"), "at": time.time()})
            store.audit("call_status", known["action_id"], params.get("CallStatus"))
        return Response(status_code=204)

    @app.websocket("/twilio/media")
    async def media(ws: WebSocket):
        await voice.bridge(ws)

    return app
