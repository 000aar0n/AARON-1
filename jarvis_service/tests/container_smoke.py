"""Black-box container smoke test with synthetic credentials and no provider access."""
import json
import secrets
import subprocess
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from cryptography.fernet import Fernet

def docker(*args):
    return subprocess.check_output(["docker",*args],text=True).strip()

def main():
    token=secrets.token_urlsafe(32)
    key=Fernet.generate_key().decode()
    volume="jarvis-ci-state"
    container="jarvis-ci"
    docker("volume","create",volume)
    try:
        docker("run","-d","--name",container,"-p","127.0.0.1:18765:10000",
            "-v",volume+":/var/lib/jarvis",
            "-e","PUBLIC_URL=https://jarvis.example",
            "-e","OWNER_TOKEN="+token,
            "-e","TOKEN_ENCRYPTION_KEY="+key,
            "-e","GOOGLE_ALLOWED_EMAIL=owner@example.com",
            "-e","SCHEDULER_ENABLED=false","jarvis-ci")
        def wait():
            for _ in range(60):
                try:
                    with urlopen("http://127.0.0.1:18765/healthz",timeout=2) as r:
                        assert json.load(r)["status"]=="healthy"
                    return
                except Exception:
                    time.sleep(1)
            raise AssertionError("Container health check never passed")
        def api(path,body=None):
            req=Request("http://127.0.0.1:18765"+path,
                data=json.dumps(body).encode() if body else None,
                headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
            with urlopen(req,timeout=5) as response:
                return json.load(response)
        wait()
        # docker exec runs as the image default user, so inspect the actual server PID.
        uid=docker("exec",container,"python","-c",
            "print(open('/proc/1/status').read().split('Uid:')[1].splitlines()[0].split()[0])")
        assert uid=="10001", uid
        p=api("/api/actions",{"kind":"send_email","payload":{
            "to":"test@example.com","subject":"Persistence test","body":"Synthetic test data only"}})
        assert p["state"]=="pending"
        docker("restart",container)
        wait()
        assert any(a["id"]==p["id"] and a["state"]=="pending" for a in api("/api/actions"))
        assert api("/api/status")["google_connected"] is False
        try:
            urlopen("http://127.0.0.1:18765/api/status",timeout=5)
            raise AssertionError("Owner endpoint was public")
        except HTTPError as exc:
            assert exc.code==401
        print("Container health, non-root server, auth and persistent restart: PASS. No live providers tested.")
    finally:
        subprocess.run(["docker","rm","-f",container],check=False,stdout=subprocess.DEVNULL)
        subprocess.run(["docker","volume","rm",volume],check=False,stdout=subprocess.DEVNULL)

if __name__=="__main__":
    main()
