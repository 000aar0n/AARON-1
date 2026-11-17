"""Read-only external deployment smoke test. No credentials or paid provider calls."""
import json
import os
import urllib.request
from urllib.error import HTTPError
from urllib.parse import urlsplit

origin=os.environ["JARVIS_CHECK_URL"].rstrip("/")
u=urlsplit(origin)
assert u.scheme=="https" and u.hostname=="aaron-jarvis-c31q.onrender.com"
def read(path):
    with urllib.request.urlopen(origin+path,timeout=30) as r:
        return r.status,r.headers,r.read()
status,headers,body=read("/healthz")
health=json.loads(body)
assert status==200 and health["status"]=="healthy"
assert headers["Cache-Control"]=="no-store"
status,_,body=read("/")
assert status==200 and b"Talk to Jarvis" in body and b"Owner access token" in body
assert b"Finish setup" in body and b'id="save-model"' in body and b'id="save-google"' in body
assert b"Task content, including relevant email and contact details" in body
status,_,body=read("/ui.js")
assert status==200 and b"/api/tasks" in body and b"/api/session/login" in body and b"/api/settings" in body
status,_,body=read("/speech.js")
assert status==200 and b"JarvisSpeech" in body
assert b"/api/voice/turn" in read("/ui.js")[2]
assert b'id="talk"' in read("/")[2]
try:
    urllib.request.urlopen(urllib.request.Request(origin+"/api/voice/turn",data=b"{}",headers={"Content-Type":"application/json"}),timeout=30)
    raise AssertionError("Spoken endpoint was accessible")
except HTTPError as e:
    assert e.code==401
for path in ["/api/status","/api/tasks","/api/actions","/api/inbox","/api/setup","/api/session"]:
    try:
        read(path)
        raise AssertionError("Private endpoint was accessible: "+path)
    except HTTPError as e:
        assert e.code==401, (path,e.code)
print("PASS: live health, spoken UI/controller, protected voice endpoint, guided setup, session frontend and authentication on all private endpoints")
print("NOT TESTED: authenticated owner session, Google consent, model inference, calls or writes")
