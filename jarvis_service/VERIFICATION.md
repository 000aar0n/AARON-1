# Verification and activation report

**Hosting is live and externally verified. Google, AI and phone integrations are not operational yet.**

## Live hosting status

The website is deployed at **https://aaron-jarvis-c31q.onrender.com**.

- Render deployment: dep-dbtpsq142hec73albong, status **live**, finished November 16, 2026 at 7:24 PM America/New_York.
- Latest deployed commit: bbccbf2e0d63790f623a081b687bce182f06c6d7.
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



Runtime source tested: `04cd3544625c239b1baa1573d39c37e7de33fa1a`.
Evidence: [GitHub CI run 43983670164](https://github.com/000aar0n/AARON-1/actions/runs/43983670164).
Verified November 16, 2026 (America/New_York).

## Verified in CI

- Official OpenJarvis repository dependency at `3b1aa1792af41c5dfb14b31ed15a3d4573b58067` installed successfully.
- Dependency compatibility check passed; all Python files compiled.
- **33 offline tests passed** (one upstream test-client deprecation warning).
- Docker image built successfully from the supplied Dockerfile.
- Black-box container startup and health checks passed.
- The running service process was UID **10001**, after initializing its persistent volume.
- Owner-only API denied unauthenticated requests.
- A pending action survived a real container restart on its mounted volume.
- Deployment YAML parsed successfully and its single-instance/persistent-disk settings were checked. Render CLI/API platform validation has NOT been performed.

Tests cover encrypted persistence, expiration and exact-payload approval, concurrent single execution, crash recovery without retry, unsupported destructive tools, header injection, timezone validation, OAuth PKCE/state/browser binding and wrong-account rejection, refresh-token persistence, Gmail MIME draft/send separation, Calendar conflict checks and invitations, Contacts read requests, tool-less OpenJarvis inference adapter and spending allowance, signed voice hooks, one-use inbound grants, outbound/inbound duration limits, and an offline Realtime audio/provisional-appointment bridge.

**Provider responses in these contracts are fake.** No real Google tokens, Twilio account, OpenAI key or billable requests were used.

## Live integration status

| Integration | Verified live | Required to activate and test |
| --- | --- | --- |
| Dalton Gmail | No | Google Cloud OAuth web client, Gmail API enabled, exact hosted callback, school-account consent |
| Dalton Calendar | No | Calendar API enabled and consent; separately approve a specific test appointment before any write/invitation |
| Dalton Contacts | No | People API enabled and school-account consent; then run the read probe |
| OpenJarvis model analysis | No billable inference | Private OpenAI API key and explicit bounded inference allowance |
| Twilio account and number | No | Private Twilio credentials and an owned voice-capable number; run read-only account/number checks |
| Outbound/inbound voice audio | No | Working public HTTPS/WSS host, Twilio webhook settings, model access and explicit approval of one short call in each direction |
| 24/7 monitoring | Host running; school monitoring inactive | External always-on deployment and Google OAuth refresh token; verify heartbeat and real recovery on that host |

The initial ChatGPT connector checks succeeded for the connected **personal** Google account. They provide **no evidence** that `c29ak@dalton.org` works and do not supply reusable hosted credentials. No school mailbox messages have been read by this service.

## Manual school sign-in

The service is configured for **c29ak@dalton.org**. After a host and OAuth client are configured, the console redirects the owner to Google's own sign-in and consent pages. The owner enters their password/MFA there; neither ChatGPT nor this service collects it. A normal browser Gmail login alone does not grant API access.

School third-party-app restrictions may require administrator approval. No browser-session export, cookie capture, password login automation or policy bypass is implemented.

## Hosting approval and earlier provisioning attempt

The committed Blueprint proposes a new, separate Render web service, **0.5 CPU / 512 MB RAM**, one instance, with a **1 GB persistent disk**, in Virginia.

Listed incremental baseline: **$7.25/month** ($7 compute + $0.25 disk), before taxes, bandwidth/build overages, account-plan charges or other extras. Source checked November 16, 2026: https://render.com/pricing.md

A Twilio US local number is listed at $1.15/month; ordinary US local outbound calling is $0.014/minute, inbound is $0.0085/minute, and Media Streams is $0.0044/minute. OpenAI voice/text usage is additional. Destinations, provider features and taxes can change the bill. Source: https://www.twilio.com/en-us/voice/pricing/us

The owner approved deployment in **Aaron Kotchen's Workspace**. The initial billing blocker was cleared, a fresh plan succeeded, and the Blueprint was applied. The server and disk are now provisioned; see Live hosting status above. No phone number was purchased and no live provider usage was activated. Blueprint ID: exs-dbtpjup42hec73akm2tg.

## Work environment limitations

The local execution tool returned **No usable execution environment is available**. Python installation, a local OpenJarvis daemon, local browser interaction and a public callback/WebSocket listener could not be run in this Work session. GitHub API tools saved the implementation and GitHub CI performed the executable tests.

This conversation is not the deployed daemon. A host with persistent storage and public HTTPS/WSS is still required.

## Actions not taken and remaining limits

No emails sent, Gmail drafts written, calls placed/answered, appointments created, external data deleted or purchases made.

There is no purchase or deletion executor. Approved appointments may send Calendar invitations only when an attendee is explicitly included in the reviewed payload. Caller ID never grants access to personal data.

The voice model is instructed never to make verbal commitments. Calendar/API actions are gated in code, but the semantics of every spoken sentence cannot be guaranteed by a language model; real conversation tests remain necessary.

Provider timeouts on consequential writes are marked uncertain and are not automatically retried. Reconcile those outcomes at the provider before proposing another attempt.

Model allowances bound analysis invocations and expiry; they are not a guaranteed dollar cap. Configure provider spending controls. SDK retry behavior can affect charges.

Off-host backup scheduling, production alerts, provider-wide billing caps, a dependency vulnerability audit and a full production security review have not been completed. The scheduler and redacted local audit logs are implemented; this does not establish 24/7 uptime. Inbox monitoring uses a seven-day lookback and at most 500 messages per run rather than complete mailbox synchronization.

## Cost-reduction revision

The owner accepted the previously quoted $25.25/month hosting ceiling and the named workspace. A smaller $7.25/month proposal (0.5 CPU / 512 MB plus 1 GB disk) has passed the capacity checks before provisioning. Source and test changes are on the same draft PR. The resource-limited revision passed 33 tests, Docker build and restart checks: https://github.com/000aar0n/AARON-1/actions/runs/43984557836 . Tested commit: edf336a5f8482e0bad484ca460ece553d6b733b7. The container was limited to 512 MB with swap disabled and 0.5 CPU, while the HTTP server and actual OpenJarvis SDK inference pipeline ran concurrently with only the provider response mocked. Peak cgroup memory was 94,359,552 bytes (about 90 MiB). This supports initial use of the smaller tier; real voice/concurrent-provider load is still untested. Acceptance of the hosting cost does not authorize live phone/model usage or substitute for the provider's required deployment-plan review.

## Expanded personal-assistant task runner

Runtime tested: 117369a92f7e1a222851504d6a75f948dd021b90. [CI evidence](https://github.com/000aar0n/AARON-1/actions/runs/43985658937): **46 tests passed**, dependency and compile checks passed, Docker built, 512 MB/no-swap/0.5 CPU container health/auth/non-root/restart checks passed. Peak cgroup memory: **94,613,504 bytes**.

Added owner-authenticated natural-language task submission, follow-up, encrypted persistent task history, bounded read/plan loops, and automatic continuation after approved actions succeed. Tests verify contact lookup followed by a pending email proposal, owner-only API access, task persistence, pause behavior, unknown-tool rejection, prevention of self-granted inference allowance, validation before queueing, duplicate-proposal avoidance, bounded calendar reads, planning turn limits, and stopping after failed/uncertain writes.

The task model never executes an external write directly. Only the owner approval queue invokes existing executors. Natural-language answers are model output; the separately rendered action receipts carry actual API outcomes.

Capabilities are limited to installed adapters. General explanations and writing/code drafting can be produced through the model; monitored inbox reads, contact lookup, calendar checks and reviewed email/call/appointment actions are implemented. **Universal website/computer control is not implemented.** Browser automation, web research, purchases, data deletion, remote code execution and unconnected apps are explicitly reported as unavailable.

Hosting was subsequently deployed and verified as documented above. School OAuth and provider credentials remain absent, and live email/call/booking tests remain unverified.

## Setup repair deployed

The setup repair is LIVE as deployment dep-dbtq8vo8v5cc73b1limg at runtime commit bbccbf2e0d63790f623a081b687bce182f06c6d7. The same service, disk, encryption key, owner token and baseline hosting plan are retained.

Verified in CI at https://github.com/000aar0n/AARON-1/actions/runs/43990197452 :
- **63 tests passed**, dependency checks and Python/JavaScript syntax checks passed.
- Real Chromium setup flow passed over local HTTPS: login, HttpOnly secure cookie, automatic session restore after reload, encrypted credential forms, allowance queue approval, chat readiness and logout.
- Docker build and 512 MB/no-swap/0.5 CPU startup, authentication and persistence checks passed.
- Peak test cgroup memory: 94,138,368 bytes.
- Real Google OAuth library URL generation was tested for PKCE, offline access and exact redirect.
- Twilio read-only account checking no longer unnecessarily requires an OpenAI key.
- OpenJarvis resolves the request-scoped personal cloud engine without global credential mutation. Provider inference was mocked; no actual model charge was incurred by tests.
- Secret fields are not echoed in configuration reads or validation errors, arbitrary owner-key replacement is rejected, and missing credentials disable dependent UI actions.

The paid host is running. The app is not connected to Google, OpenAI or Twilio until the owner supplies valid provider settings and completes consent. First-time private access still requires the existing OWNER_TOKEN. The new app handles credential setup privately after that one unlock, and remembers the session for 12 hours. No Google password, provider keys or payment data need to be sent in chat.

Configured and verified-read statuses remain separate from operational live send/call/booking tests. No additional external commitments, calls, emails or purchases were made during this repair.

## Final recipient-data correction

Latest deployed runtime: **a2ca26869115ca2a4106798db7dd0ff0e079dfc0**. Deployment **dep-dbtqcv67bikc73fe9670** is **live** (November 16, 2026 at 7:58 PM America/New_York). CI https://github.com/000aar0n/AARON-1/actions/runs/43991289440 passed **64 tests**, the real browser setup flow, JavaScript/Python checks, Docker build and 512 MB/no-swap persistence checks. Peak test cgroup memory: 94,646,272 bytes.

A new test exercises the actual official SDK wrapper and verifies that exact recipient addresses survive model input/output. Automatic PII redaction is disabled specifically for requested task content because replacing email addresses prevents valid drafts; credential secret scanning is retained. The UI explains that relevant task, email and contact data is processed by OpenAI. Model calls remain allowance-gated and external actions remain owner-approved.

The external setup-page/authentication check for the earlier repair passed at https://github.com/000aar0n/AARON-1/actions/runs/43991025942 . The live checker is being run again against the final recipient-data revision. Real provider credentials and consent are still outstanding; external integrations must not be reported as operational based on these tests.
