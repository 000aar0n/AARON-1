"""Post-deployment READ-ONLY probes; never send mail, place calls, or invoke a model."""
import json
import os
import sys
import urllib.request

def main():
    origin=os.environ["PUBLIC_URL"].rstrip("/")
    token=os.environ["OWNER_TOKEN"]
    if not origin.startswith("https://"):
        raise SystemExit("HTTPS is required")
    def read(path,method="GET"):
        req=urllib.request.Request(origin+path,method=method,
            headers={"Authorization":"Bearer "+token})
        with urllib.request.urlopen(req,timeout=60) as response:
            return json.load(response)
    health=read("/healthz")
    status=read("/api/status")
    probes=read("/api/probe","POST")
    report={
        "service_health":health.get("status"),
        "google_owner_matches":(status.get("google_identity") or {}).get("email","").casefold()
            ==os.environ["GOOGLE_ALLOWED_EMAIL"].casefold(),
        "google":probes["google"],
        "twilio_account":probes["twilio"],
        "live_email_send":"NOT_TESTED",
        "live_appointment_write":"NOT_TESTED",
        "live_phone_audio":"NOT_TESTED",
        "model_inference":"NOT_TESTED",
    }
    print(json.dumps(report,indent=2))
    return 0 if all(x.get("status")=="verified_read" for x in probes["google"].values()) and report["google_owner_matches"] else 1

if __name__=="__main__":
    sys.exit(main())
