# Verification and activation report

**Jarvis is NOT operational and has not been deployed.**

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
| 24/7 monitoring | Not running | External always-on deployment and Google OAuth refresh token; verify heartbeat and real recovery on that host |

The initial ChatGPT connector checks succeeded for the connected **personal** Google account. They provide **no evidence** that `c29ak@dalton.org` works and do not supply reusable hosted credentials. No school mailbox messages have been read by this service.

## Manual school sign-in

The service is configured for **c29ak@dalton.org**. After a host and OAuth client are configured, the console redirects the owner to Google's own sign-in and consent pages. The owner enters their password/MFA there; neither ChatGPT nor this service collects it. A normal browser Gmail login alone does not grant API access.

School third-party-app restrictions may require administrator approval. No browser-session export, cookie capture, password login automation or policy bypass is implemented.

## Proposed hosting and approval

The committed Blueprint proposes a new, separate Render web service, **1 CPU / 2 GB RAM**, one instance, with a **1 GB persistent disk**, in Virginia.

Listed incremental baseline: **$25.25/month** ($25 compute + $0.25 disk), before taxes, bandwidth/build overages, account-plan charges or other extras. Source checked November 16, 2026: https://render.com/pricing.md

A Twilio US local number is listed at $1.15/month; ordinary US local outbound calling is $0.014/minute, inbound is $0.0085/minute, and Media Streams is $0.0044/minute. OpenAI voice/text usage is additional. Destinations, provider features and taxes can change the bill. Source: https://www.twilio.com/en-us/voice/pricing/us

No paid resource, number or service has been provisioned. No cost has been approved by the owner. The Render connection reports no selected workspace; the available workspace is **Aaron Kotchen's Workspace**. Confirm the target before planning/applying infrastructure. The next step is to prepare/review the provider's plan, then explicitly authorize its application.

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
