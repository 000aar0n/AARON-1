# Aaron's Jarvis service

This is a separate, reviewable personal-assistant service under AARON-1. The existing planner is not modified.

**Status: hosting live; 64 offline tests passed. Google, model and phone activation remains incomplete.** Consult [VERIFICATION.md](VERIFICATION.md) for test evidence and blockers.

## Official OpenJarvis dependency

The assistant uses the official repository https://github.com/open-jarvis/OpenJarvis, pinned at commit `3b1aa1792af41c5dfb14b31ed15a3d4573b58067`. The inbox intelligence adapter actually invokes the upstream `Jarvis` SDK. OAuth, scheduling, encrypted durable state, approvals and Twilio transport are application extensions; they are not represented as built-in OpenJarvis features.

No arbitrary shell, browser, skill installation, purchase, deletion, or tool-executing OpenJarvis agent is exposed to email or callers. The persistent application loop supplies monitoring and memory around tool-less upstream inference.

## School Google account: sign in manually

Use **c29ak@dalton.org**, not the personal Gmail connected to ChatGPT.

1. Create a Google Cloud project you control. Enable Gmail API, Google Calendar API and People API.
2. Configure the OAuth consent screen and create a **Web application** OAuth client. Register exactly `https://YOUR-HOST/oauth/google/callback` as its redirect URI. Add your school account as a test user if applicable.
3. Put GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in the host's private environment settings. Set GOOGLE_ALLOWED_EMAIL to your school address.
4. Open the owner console, unlock it with OWNER_TOKEN, and click **Sign in to school Google account**.
5. You sign in directly on Google's page, including any school SSO or MFA. The assistant never asks for, receives, or stores your Google password. Complete Google's consent screen yourself.
6. Return to the owner console and click **Test connections**. This probes Gmail, Calendar and Contacts independently and records timestamped results.

The app uses OAuth authorization code + PKCE, browser-bound expiring state, an allowlisted verified Google account and offline refresh tokens. Google tokens are encrypted before persistence.

School administrators may block third-party OAuth apps or particular scopes. Manual Google sign-in does not bypass that policy. If Google returns an admin-policy error, obtain school administrator approval or use an allowed account. Do not export browser cookies or give the assistant a password. In Google's external Testing mode, refresh-token expiry may require repeated consent; use the appropriate production/verification settings for durable access.

Requested scopes: OpenID verified email identity, Gmail read, Gmail compose, Calendar events, Contacts read-only. Gmail compose can also permit sending at Google's permission layer; the app enforces per-message approval before using that capability. There are no Gmail-delete or Contacts-write tools.

## Behavior and approval boundaries

- The scheduler checks the latest seven days of inbox messages every five minutes (maximum 500 per run). It stores categories and excerpts without paid inference. AI summaries and suggested replies require a separately approved, expiring model allowance.
- Email text is untrusted data. OpenJarvis gets no tools and no approval token. The app validates the model's JSON output. Suggested responses stay in encrypted application storage.
- Saving a Gmail draft also uses review. Sending requires a new send_email proposal with the exact recipient, subject, body and thread metadata. Approving a draft does not authorize sending it.
- Calls require approval of the exact number, purpose, maximum duration and model charges. A receive_call proposal arms ONE inbound call from the specified caller number for up to the proposal's expiry. All other inbound calls are rejected without auto-answer.
- Caller ID is not trusted identity. Voice sessions cannot access email, contacts or calendar. They can only queue provisional appointments for owner review. The model is instructed never to confirm a booking or make a verbal commitment. Natural-language compliance is probabilistic; provider tools and calendar writes are enforceably gated, but live dialogue behavior still needs testing.
- Calendar creation requires review of exact dates with UTC offsets, title, details and any invited attendee. Inviting an attendee sends a Calendar invitation and is part of that explicit approval. The app checks the primary calendar for conflicts immediately before insertion. It cannot atomically lock external calendars.
- No purchase or delete executor exists. Such requests are unsupported rather than silently approved.
- Only the owner bearer credential can approve. Payload hashes, expiry and atomic state transitions prevent changed-payload approval and duplicate execution.
- Network errors on consequential writes produce **uncertain** outcomes. No automatic retry occurs. Check the provider and audit log first.
- **Pause Jarvis** revokes unused model allowances and inbound grants. In-progress external requests can already have taken effect. Resuming does not restore spending authority.

Review actions in the console. For custom actions, paste a JSON proposal in New proposal, then review the immutable queue card. Approving and executing is one explicit click with a confirmation dialog.

### Example appointment proposal

```json
{"kind":"create_appointment","payload":{"title":"Piano lesson","start":"2026-11-20T17:00:00-05:00","end":"2026-11-20T18:00:00-05:00","details":"Provisional until owner approval","attendee":null}}
```

### Example outbound call proposal

```json
{"kind":"place_call","payload":{"to":"+12125550101","purpose":"Ask for available appointment times. Do not book or confirm.","max_seconds":180,"model":"gpt-realtime","cost_notice":"I approve Twilio and voice-model charges for this one call"}}
```

The example number is a placeholder; never approve it as a real test destination. Receive approval uses the same payload shape with kind receive_call and the expected caller in to.

### Example bounded model spending allowance

```json
{"kind":"inference_allowance","payload":{"model":"gpt-4o-mini","requests":10,"hours":1,"cost_notice":"I approve model charges for this bounded allowance"}}
```

One analysis is limited to approximately 10,000 input characters and 900 output tokens. The allowance bounds analysis invocations, not a guaranteed dollar charge. Provider pricing and SDK-level retries affect billing. Use provider project budgets/limits as an additional control. After an error, a reserved request remains consumed.

## Voice: Twilio + OpenAI Realtime

1. Use a Twilio account and voice-capable number. Trial accounts may require verified destinations.
2. Configure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER and OPENAI_API_KEY in private host settings.
3. Configure the number's incoming Voice webhook as POST `https://YOUR-HOST/twilio/voice`.
4. The service validates Twilio signatures for HTTP hooks and WebSocket upgrades against the configured public origin. It does not trust forwarded host headers.
5. The bridge uses bidirectional Twilio Media Streams and OpenAI Realtime WebSocket audio with G.711 mu-law (8 kHz), server VAD, interruption clearing and context truncation. Start frames must contain a random single-use session token bound to owner approval.
6. Approve one short call to a number you control. Test both directions, natural turn-taking, interruption, time limit, hangup, provider disconnect, signature rejection and an attempted unauthorized booking. Inspect provider call status and audit entries. Only then record live voice as verified.

The app makes a fixed AI disclosure before the model speaks. It does not enable Twilio recording or persist raw audio/transcripts. Audio is sent to Twilio and OpenAI; their account-level retention rules still apply. No cloned or impersonated human voice is used.

## Hosting proposal (requires cost approval)

A paid always-on Render web service, one instance, and a 1 GB persistent disk are proposed in [render.yaml](render.yaml). The revised plan selects 512 MB RAM at $7/month plus $0.25/month for a 1 GB disk (https://render.com/pricing.md). Review the actual workspace bill before applying; the resource-limited CI check passed at about 90 MiB peak memory, with real voice load still untested. Telephony, a number, model usage, bandwidth and disk charges are separate. No resources have been provisioned and no number purchased by this change.

Render's free web services sleep and lose local files; they are unsuitable for this durable agent. An external VPS with a persistent volume is also feasible. The Work conversation is not a 24/7 Python/WebSocket host.

The Blueprint path is `jarvis_service/render.yaml` and the branch is `jarvis/personal-assistant`. Do not apply an unrelated root Blueprint. The Docker build context is the repository root. Use one process and one instance because the state store is SQLite.

Before deployment:
1. Approve the actual hosting costs and provider usage budget.
2. Supply private settings listed in [.env.example](.env.example). Generate OWNER_TOKEN with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and TOKEN_ENCRYPTION_KEY with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` on your own trusted machine. Do not paste them into chat or commit them.
3. The container initializes ownership of its dedicated mounted data directory and drops root privileges to UID 10001 before starting the server. Verify this on the selected host; do not weaken file permissions.
4. Set PUBLIC_URL to the final HTTPS origin. Turn off access logging so OAuth codes and callback parameters are not logged.
5. Validate the Blueprint using the current Render CLI and the exact path. Then deploy only after cost approval.
6. Verify /healthz, authenticated status, Google consent and read probes, scheduler heartbeat across restart, encrypted-state recovery, and approved live write/call tests.
7. Configure host health alerts and an off-host encrypted backup schedule with the host. SQLite state and its encryption key need separate protected backups. Backup automation is not provisioned by this draft.

For a local test host: `pip install -r jarvis_service/requirements.txt`, set private environment variables, and run `uvicorn jarvis_service.app:create_app --factory --host 127.0.0.1 --port 10000 --workers 1 --no-access-log`. Google callback and Twilio require a stable public HTTPS endpoint. Local startup alone does not satisfy their live tests.

## Security and operational limits

Secrets are environment-managed; refresh tokens, messages, action payloads and provider results are Fernet-encrypted in a 0700 data directory. Logs contain action IDs, event names and error classes rather than message bodies, phone numbers, tokens or OAuth codes. The UI renders untrusted data as text, does not store the bearer credential in browser storage, and clears content on lock.

The encryption key must survive redeploys. Changing it without a migration makes existing data unreadable. Protect host backups and the owner credential. The service is a single-owner implementation; a production multi-user service would need proper identity management, key rotation, rate controls, retention controls and a security review.

The fixed lookback and 500-message cap are bounded monitoring, not a guaranteed complete archive. There is no ongoing ingestion of contacts; Contacts is searched read-only on demand. The primary calendar is checked on demand and at booking time. No automatic external deletion/retention job is installed.

## Tests

`python -m pytest -q jarvis_service/tests`

The GitHub workflow installs the pinned upstream repository, checks dependency compatibility and syntax, runs offline contract/security tests, and parses the deployment YAML. These tests use fake Google/Twilio/model providers. They are not proof that school OAuth, billing, email sending or phone audio work live.

After deployment, run `python -m jarvis_service.verify` with PUBLIC_URL, OWNER_TOKEN and GOOGLE_ALLOWED_EMAIL set privately. This only probes read access; it never sends, books, calls or spends on model inference. The CI container smoke test uses synthetic credentials and checks privilege drop, startup, authenticated access and persistence across a restart.

## Lower-cost hosting revision

The revised proposal uses 0.5 CPU / 512 MB RAM ($7/month) plus a 1 GB persistent disk ($0.25/month), totaling $7.25/month before taxes/overages and provider usage. CI now tests a 512 MB container with swap disabled, the running server plus the real OpenJarvis inference pipeline with a mocked provider, and restart persistence. This is an initial capacity check, not a live simultaneous voice-load benchmark. Upgrade only after measured resource pressure and within the owner's approved ceiling.

Initial deployment can generate OWNER_TOKEN and TOKEN_ENCRYPTION_KEY privately in Render, and derive its public origin from RENDER_EXTERNAL_URL. Google OAuth credentials are added privately later. All provider usage remains unavailable without credentials and explicit allowances.

Hosting is now deployed at https://aaron-jarvis-c31q.onrender.com . The server and 1 GB disk are provisioned; auto-sync remains disabled. External read-only health, UI and unauthenticated-access checks passed. Google/model/phone credentials and live integration tests remain outstanding.

## Natural-language personal assistant

The owner console now accepts plain-English tasks and follow-up instructions. The task runner uses the official OpenJarvis SDK to plan a bounded sequence of read operations and proposed actions. It can answer general questions, draft writing or code text, search connected contacts, check primary-calendar availability, inspect monitored inbox data and prepare messages, calls or appointments.

For example: “Find a free hour next week, look up the contact, and draft an invitation for me to review.” If it lacks the exact person, date, number or permission, it asks for the missing details instead of inventing them.

Tasks and observations are encrypted and persist across restarts. The scheduler resumes tasks after owner-approved actions succeed. Failed, rejected or uncertain writes stop automatic continuation. A task is limited to eight planning turns, and each model request consumes the owner's existing approved allowance. The owner can follow up in the console; typing instructions does not bypass per-action approval.

Task planning permits up to 24,000 data characters and 1,600 output tokens per model invocation, compared with the smaller inbox-analysis limit. This increases potential per-request usage but never starts paid inference without credentials and an approved allowance.

The authenticated /api/capabilities endpoint reports implemented and unavailable tools. Arbitrary computer control, browser automation, web research, purchases, deletions, remote code execution and unconnected apps remain unavailable. Drafting code in a response does not run or deploy it. It cannot automatically gain permissions to every app or use school Google access before OAuth consent.

No model receives the owner bearer token or an approval endpoint. Tool observations are untrusted data. All consequential external actions still enter the exact-payload approval queue. The UI displays provider receipts separately from model-generated prose.

Verification for this revision: [46 tests and resource-limited container checks](https://github.com/000aar0n/AARON-1/actions/runs/43985658937), runtime commit 117369a92f7e1a222851504d6a75f948dd021b90. Peak memory was 94,613,504 bytes with the server and a mocked-provider OpenJarvis inference pipeline. Real voice/load tests remain outstanding.

## Live hosting status

The website is deployed at **https://aaron-jarvis-c31q.onrender.com**.

- Render deployment: dep-dbtpsq142hec73albong, status **live**, finished November 16, 2026 at 7:24 PM America/New_York.
- Deployed commit: 4d07335171d7729a1749be64e53c46ee93b82621.
- Service: srv-dbtpsph42hec73albnog, 0.5 CPU / 512 MB RAM, one instance.
- Disk: dsk-dbtpspp42hec73albo70, 1 GB at /var/lib/jarvis.
- Baseline hosting is now provisioned at $7.25/month before taxes/overages. Provider inference and telephony remain unconfigured and are not included in that price.
- Automatic code/Blueprint deployments remain off.
- [Render service](https://dashboard.render.com/web/srv-dbtpsph42hec73albnog).
- [External read-only verification](https://github.com/000aar0n/AARON-1/actions/runs/43987558236) passed: GET /healthz returned healthy JSON; the owner console and task UI loaded; /api/status, /api/tasks, /api/actions and /api/inbox returned HTTP 401 without owner credentials.
- Render runtime logs reported successful application startup; no runtime startup error was observed.
- Authenticated live-owner operations, Google consent, model inference, email sends, calls and calendar writes remain unverified.

To unlock the console, retrieve OWNER_TOKEN privately from the service's Environment tab in Render and paste it into the console's Owner access token field. Do not put it in a URL or repository.

Before school sign-in can work, configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET privately for a Google OAuth web application, enable Gmail/Calendar/People APIs, and register this exact redirect:
https://aaron-jarvis-c31q.onrender.com/oauth/google/callback

Google credentials and OpenAI/Twilio keys have not been supplied. Adding a payment method and deploying the host does not connect these accounts or authorize paid provider usage. Complete the corresponding consent and approval flows, then perform live read probes and separately approved write/call tests.


## Guided setup and persistent sign-in

The live app now provides a Finish setup panel instead of requiring provider credentials to be edited in Render. Unlock once with the existing OWNER_TOKEN from Render. The browser then uses a Secure, HttpOnly, SameSite=Strict cookie for a 12-hour session, restored across reloads. Sign out revokes the session. Cookie-authenticated writes require an exact origin and CSRF token; bearer API clients remain supported.

Provider API keys and OAuth client settings can be entered privately in the app. They are encrypted in the existing durable SQLite store, are never returned by configuration reads, and take effect without a redeploy. Blank fields preserve existing values. Validation errors do not echo secrets. Saving credentials never grants an inference allowance or starts a call.

1. Save an OpenAI API key under AI chat, then review a bounded usage allowance and approve its exact queue item. Chat stays disabled until both are available.
2. Save the Google OAuth web client ID/secret under Google configuration, register the displayed exact redirect URL, and enable Gmail, Calendar and People APIs. Then sign in directly to Google. A Google password is never requested in Jarvis.
3. Save Twilio credentials and the owned number under Phone assistant, configure the displayed webhook, and separately approve live call tests. The Twilio account can now be checked independently of the AI key.
4. Check connections. AI credential checks use GET /v1/models, not paid inference. A successful key check is not proof that a particular model or live voice works.

The official OpenJarvis text engine now receives a request-scoped private OpenAI key without using global environment credentials. It pins the OpenAI endpoint and disables SDK retries. Each analysis/planning invocation still requires an owner-approved allowance.

CI evidence: https://github.com/000aar0n/AARON-1/actions/runs/43990197452 . All 63 tests, JavaScript syntax, a real Chromium browser test over local HTTPS, Docker build and the 512 MB persistence test passed. Browser coverage includes login, reload persistence, private credential forms, budget approval, chat readiness and logout. The browser used only synthetic credentials; no provider consent or paid usage was exercised.

Runtime update: bbccbf2e0d63790f623a081b687bce182f06c6d7, deployed as dep-dbtq8vo8v5cc73b1limg. The first-time owner token remains necessary because the assistant is private. Actual provider credentials and school consent are still required for external integrations.

Latest validated repair: runtime a2ca26869115ca2a4106798db7dd0ff0e079dfc0, Render deployment dep-dbtqcv67bikc73fe9670 (live). CI https://github.com/000aar0n/AARON-1/actions/runs/43991289440 passed 64 tests, real-browser setup, Docker build and resource-limited restart checks. This also fixes upstream PII redaction breaking exact recipient addresses: task/contact details needed for requested work are preserved, credential scanning remains enabled, and the setup panel discloses processing by OpenAI. No real provider operation was exercised.
