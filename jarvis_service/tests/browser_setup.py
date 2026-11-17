"""Real browser setup test using synthetic credentials and an isolated local HTTPS server."""
import os
import secrets
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, expect

def main():
    with tempfile.TemporaryDirectory() as temp:
        cert,key=Path(temp)/"test.crt",Path(temp)/"test.key"
        subprocess.run(["openssl","req","-x509","-newkey","rsa:2048","-nodes",
            "-keyout",str(key),"-out",str(cert),"-days","1","-subj","/CN=127.0.0.1"],
            check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        token=secrets.token_urlsafe(32)
        origin="https://127.0.0.1:18766"
        env={**os.environ,"PUBLIC_URL":origin,"OWNER_TOKEN":token,
             "TOKEN_ENCRYPTION_KEY":Fernet.generate_key().decode(),"GOOGLE_ALLOWED_EMAIL":"owner@example.com",
             "DATA_DIR":str(Path(temp)/"data"),"OPENJARVIS_HOME":str(Path(temp)/"upstream"),
             "SCHEDULER_ENABLED":"false"}
        process=subprocess.Popen([sys.executable,"-m","uvicorn","jarvis_service.app:create_app","--factory",
            "--host","127.0.0.1","--port","18766","--ssl-keyfile",str(key),"--ssl-certfile",str(cert),
            "--no-access-log"],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen(origin+"/healthz",context=ssl._create_unverified_context(),timeout=2)
                    break
                except Exception:
                    time.sleep(.5)
            else:
                raise AssertionError("Local HTTPS server failed to start")
            with sync_playwright() as p:
                browser=p.chromium.launch()
                context=browser.new_context(ignore_https_errors=True)
                page=context.new_page()
                errors=[]
                page.on("pageerror",lambda e:errors.append(str(e)))
                page.goto(origin)
                expect(page.locator("#token")).to_be_visible()
                page.locator("#token").fill(token)
                page.locator("#unlock").click()
                expect(page.locator("#console")).to_be_visible()
                expect(page.locator("#connect")).to_be_disabled()
                expect(page.locator("#task-submit")).to_be_disabled()
                page.locator("#openai-key").fill("synthetic-model-key-123456789")
                page.locator("#save-model").click()
                expect(page.locator("#model-state")).to_contain_text("Key saved")
                expect(page.locator("#openai-key")).to_have_value("")
                page.reload()
                expect(page.locator("#console")).to_be_visible()
                expect(page.locator("#token")).to_be_hidden()
                page.locator("#google-config").locator("summary").click()
                page.locator("#google-client-id").fill("synthetic.apps.googleusercontent.com")
                page.locator("#google-client-secret").fill("synthetic-google-secret")
                page.locator("#save-google").click()
                expect(page.locator("#connect")).to_be_enabled()
                expect(page.locator("#google-client-secret")).to_have_value("")
                page.locator("#review-allowance").click()
                expect(page.locator("#actions")).to_contain_text("inference_allowance")
                # This is a synthetic budget grant only; no task or model is invoked.
                page.on("dialog",lambda d:d.accept())
                page.locator("#actions").get_by_role("button",name="Approve and execute once").click()
                expect(page.locator("#task-submit")).to_be_enabled()
                cookies=context.cookies()
                session=next(c for c in cookies if c["name"]=="jarvis_session")
                assert session["secure"] and session["httpOnly"] and session["sameSite"]=="Strict"
                page.locator("#lock").click()
                expect(page.locator("#token")).to_be_visible()
                expect(page.locator("#console")).to_be_hidden()
                assert not errors,errors
                context.close()
                browser.close()
            print("PASS: real-browser login, persistent session, encrypted credential forms, approval flow and logout")
            print("No Google consent, external model calls or phone calls were performed.")
        finally:
            process.terminate()
            process.wait(timeout=15)

if __name__=="__main__":
    main()
