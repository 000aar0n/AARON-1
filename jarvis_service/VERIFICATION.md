# Verification and activation report

The host is live at https://aaron-jarvis-c31q.onrender.com. Provider integrations require the owner's private credentials, Google consent and separately approved live tests. Deployment alone does not make those integrations operational.

## Spoken browser interface

Tap Talk after private sign-in and AI setup, allow microphone access, and speak. Jarvis uses browser speech recognition, the official OpenJarvis text engine, and browser speech synthesis. It listens again after playback; text mode is optional. This is distinct from the Twilio/OpenAI Realtime telephone bridge. Browser/device speech quality is not guaranteed.

The transcript reaches the authenticated, CSRF-protected HTTPS API and is encrypted in persistent conversation/task storage. Raw microphone audio is not uploaded to this app. The browser speech provider may process audio. Recognition stops while replies play, on hidden tabs, sign-out, pause and errors. Sessions end after 15 minutes. Spoken "stop" stops recognition; "new conversation" resets context.

Voice requests prepare proposals, never authorize sending, booking, calling or spending. Pending actions pause recognition and produce a fixed "not sent/booked/called" reply. A spoken yes cannot execute a pending action. The exact-payload approval card remains required.

## Test scope

Runtime source: 59c4c4521ed90d54ce82e09e6954f25c17ab418d.
CI: https://github.com/000aar0n/AARON-1/actions/runs/43996964028 .

Automated coverage includes 69 Python integration/security tests, 8 voice-controller tests, JavaScript syntax, a real Chromium setup/voice-interface test, Docker build, privilege drop and encrypted-state restart checks under a 512 MB no-swap container limit. Browser audio events and model turn responses are synthetic. This verifies control flow, not hardware microphone capture or a live model account.

Voice controller checks cover interim/final recognition, spoken playback, microphone restart after playback, permission errors, stop, stale replies, new-topic reset, setup prerequisites and approval pause/receipts. Backend checks cover owner-only access, idempotency, encrypted conversation history, bounded tasks, pause and spoken-approval rejection.

No real email sends, calendar writes, phone calls or paid model requests were exercised.

## Integration activation

| Component | Verified | Still required |
| --- | --- | --- |
| HTTPS host and persistent disk | Health, startup and restart contracts | Continued host monitoring and off-host encrypted backups |
| Owner authentication | Secure HttpOnly SameSite Strict session, CSRF, private settings, logout | Owner's one-time token from Render Environment |
| Browser conversation | Interface, synthetic listening/playback cycle, encrypted text conversation | Private AI key, approved allowance, real microphone/speaker/model test |
| Gmail | Mocked OAuth/read/draft/send contracts | Google OAuth client, school consent, live read probe and separately approved draft/send |
| Calendar | Mocked availability/conflict/write contracts | Google consent, live read probe and approved event test |
| Contacts | Mocked read-only search contracts | People API, Google consent and live read probe |
| Twilio/Realtime phone | Mocked webhook/signature/audio bridge/approval contracts | Owned voice number, private Twilio/OpenAI credentials, webhook and approved incoming/outgoing tests |
| Inbox monitoring | Bounded scheduling, classification and mocked analysis contracts | Authorized Google access; AI summaries require approved inference |
| Purchases/deletion/arbitrary computer control | No executor exists | Unsupported; voice does not add these tools |

Manual Google sign-in happens on Google's page; Jarvis never asks for the Google password or browser cookies. A school administrator restriction may still block OAuth on a personal device. Obtain administrator approval or use an allowed account.

## Hosting and credentials

Service: srv-dbtpsph42hec73albnog, one process/instance, 0.5 CPU / 512 MB RAM.
Disk: dsk-dbtpspp42hec73albo70, 1 GB mounted at /var/lib/jarvis.
Provisioned baseline: $7.25/month before taxes/overages; model/telephony usage is separate. No additional paid resource was provisioned for browser voice. Automatic deployments remain disabled.

Render: https://dashboard.render.com/web/srv-dbtpsph42hec73albnog .
Retrieve OWNER_TOKEN privately from Environment and enter it in the app once per 12-hour browser session. Provider keys may be saved through the authenticated setup panel; blank inputs preserve values. Keys are encrypted and never returned by setup reads. Saving a key does not authorize inference or calls. Protect the persistent encryption key separately from backups.

Google redirect: https://aaron-jarvis-c31q.onrender.com/oauth/google/callback .
Enable Gmail, Calendar and People APIs and configure a Web application OAuth client with the allowed school account. Twilio incoming webhook: https://aaron-jarvis-c31q.onrender.com/twilio/voice .

The Work environment is used to prepare and verify changes; the Render service hosts the persistent agent. Browser voice requires an open, visible page. A permanent wake word or operating-system-wide background voice agent has not been implemented.

Latest deployed runtime: 59c4c4521ed90d54ce82e09e6954f25c17ab418d. Render deployment dep-dbtr0v8u01pc73crltn0 became live November 16, 2026 at 8:41 PM America/New_York. CI completed successfully before deployment. Peak container memory during mocked-provider verification was 94,695,424 bytes.
