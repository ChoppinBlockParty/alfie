# Alfie

Spec version: 0.47. Updated: 2026-09-20.

Self-hosted personal AI agent with Telegram, memory, reminders, email and public-web research.
This document describes the whole system and current decisions. Subsystem READMEs own their
implementation details. History is in git. `plan-next.md` records the active build and checks.
Public-release cleanup and its remaining history gate are in [publication-plan.md](publication-plan.md).

## 1. Status

Hermes's native assistant flow handles conversation history, memory, voice transcription, image
analysis, reads, public research/browser use and scheduling. There is no task classifier, mode
prefix, scope grant or preliminary read confirmation.

The general task-permission system was tried and removed. It was too restrictive, hindered smooth
conversation and media handling, and made the bot nearly useless. Safety is now kept close to
concrete effects rather than placed in front of every request.

The four-container browser/security build remains deployed. Public research and disposable
interactive browsing use its isolated worker. Google operations run in the gateway without
forwarding credentials to the command sandbox.

The security increment is deployed using existing images: Google writes require authenticated
Telegram buttons, email-watch is report-only, personal database mounts are removed from the
command sandbox, and filtering updates transactionally. Automated runtime acceptance passed.
Real owner self-test approval/rejection and an exact-action Drive folder creation were verified.
The first proposal exposed a dispatcher mismatch; after the deployed fix, the approved immutable
action succeeded and a read-only search found exactly one matching folder.

Google reads execute directly. Supported Google writes still proceed only through a separate,
immutable exact-action Telegram review; the model cannot approve its own action. The command
sandbox has no Google credentials or personal-data mounts. Public browser/research workers remain
isolated from gateway credentials and private networks. Email-watch remains report-only.

Voice notes and photographs use Hermes's native media pipeline. The local faster-whisper runtime
uses a short-voice configuration that avoids discarding valid two-second Telegram clips.
See [plan-next](plan-next.md) for remaining work; this is not maximum-security completion.

The prior natural-language two-review smoke test verified the exact action was rejected; the
preliminary scope review has since been removed as redundant. Research model credentials stay in the
gateway behind a job-bound broker; stalled worker jobs are terminated. Google subprocesses have
streaming output limits and process-group deadlines. Firewall-first container startup passed a
real host reboot. An encrypted Drive backup passed read-back and offline data/approval recovery
checks. Backups remain manual; the recovery private key stays on the owner's Mac, not the VPS.
Web retrieval now has pre-parse response limits and public-destination preflight. Google write
reviews include target metadata and, for Sheets replacement, prior values; context is checked
again before execution. Spreadsheet writes use literal values, not formulas. A read-only operator
reconciliation helper supports uncertain outcomes without retrying. Difficult full-host recovery
tests are deferred by owner direction and are not implementation release blockers.

### Use cases

| ID | Use case | Scope |
|---|---|---|
| UC1 | Find a product and prepare a purchase | Public browsing/cart preparation; owner logs in and pays on their device |
| UC2 | Find an email record and act on it | Gmail search/read and supported Google operations; no private email in the public browser |
| UC3 | Research a question or product | Research summary with sources; interactive browsing when needed |
| UC4 | Voice notes and photographs | Local transcription and model vision |
| UC5 | Correspond by email | Gmail send/reply only after exact-action Telegram approval |
| UC6 | Remember facts, obligations and reminders | Local fact store, records, scheduled reminders |
| UC7 | Keep preferences and learning | Local memory and USER.md |

### Subsystems

| Directory | Responsibility |
|---|---|
| `email-watch/` | Tool-less classification, pending/quarantined observations, Telegram reports; no automatic account writes |
| `google-workspace/` | Fixed Google operations in the trusted gateway; no credential forwarding |
| `sandbox/` | Shell/file/code execution over SSH in the command container |
| `web-search/` | Search/read/analyse loop and shared worker server/image |
| `web-browser/` | Interactive public browsing; shares the research worker container |
| `egress/` | Squid destination policy |
| `deployment/` | Four-container cutover, resource limits, firewall and acceptance checks |

## 2. Current decisions

| Area | Decision |
|---|---|
| Host | Operator-managed Linux VPS; deployment identifiers stay in ignored local configuration |
| Orchestration | Hermes gateway in Docker; no host install or Docker socket available to the agent |
| Inference | `gpt-5.5`, `openai-codex`, subscription OAuth; empty fallback chain, no automatic paid API fallback |
| Containers | Four: gateway, command sandbox, research/browser worker, egress proxy |
| Shell | `terminal.backend: ssh`, gateway → container on port 2222; never local as a rollback |
| Google | Gateway plugin with fixed operations; credentials remain in gateway; sandbox mounts and credential sync removed |
| Public web | Research and browser share one untrusted-worker boundary; one research job or browser session at a time |
| Checkout | Logged-out product/cart preparation only; login, personal details and payment on owner's device |
| Browser lifecycle | On demand; one page; disposable profile; 120 s idle, 600 s total, 60 actions |
| Networking | Workers have no direct internet route. Proxy permits only model endpoint for shell, public HTTP(S) for web worker; blocks private/reserved destinations |
| Memory | Enforced ceilings: gateway 1024 MiB, sandbox 512 MiB, worker 1280 MiB, egress 128 MiB; browser starts on demand |
| Persistent facts | Local holographic fact store + SQLite records; no external memory service |
| Scheduled work | Deterministic `no_agent` scripts, model calls only when input exists; no agent-driven email polling |
| Voice | Native Hermes transcription with local pinned faster-whisper `base` |
| Search/extraction | Tavily and Firecrawl, currently keyless; no provider keys in public worker |
| Timezone | Configured home timezone; scheduled tasks and travelling owner use their explicit current timezone |

## 3. Host and runtime

### Local deployment configuration: `.env.local`

The repository-root **`.env.local` is the private source of truth for deployment settings**.
The leading dot matters: `env.local` is a different filename and is not loaded. Create it from
the tracked `.env.example`, supply real values privately and set its permissions to `0600`.

| Setting | Purpose |
|---|---|
| `ALFIE_VPS_HOST` | SSH destination: an operator-configured SSH alias or address. SSH resolves aliases through the operator's SSH configuration and uses their existing authentication. |
| `ALFIE_PUBLIC_IPV4`, `ALFIE_PUBLIC_IPV6` | Server public addresses rendered into host-destination deny rules, proxy configuration and acceptance checks. These are not interchangeable with the SSH alias. |
| `ALFIE_OWNER_TELEGRAM_USER_ID` | Numeric Telegram identity of Alfie's single owner; shared by all owner-only policies. |
| `EMAIL_WATCH_CHAT_ID`, `EMAIL_WATCH_THREAD_ID` | Private email-watch delivery destination. |
| `ALFIE_APPROVAL_CHAT_ID`, `ALFIE_APPROVAL_THREAD_ID` | Private dedicated Telegram forum/topic for approval reviews; distinct from email-watch delivery. |
| `TELEGRAM_BOT_USERNAME` | Operator reference; setting it here does not change the gateway's bot credentials. |

Load it through `deployment/local-env.sh` **in Bash**, from the repository root. For execution
tools, explicitly select `/bin/bash` with `login: false`. Chain the loader with `&&` so SSH does
not run if loading fails. For example:

```sh
/bin/bash -c 'source deployment/local-env.sh && ssh -o BatchMode=yes -o ConnectTimeout=8 "$ALFIE_VPS_HOST" true'
```

`ALFIE_VPS_HOST` is required; there is no fallback to the old `HOST` variable. Never infer the
deployment target from a pre-existing shell `HOST`: zsh defines its own HOST
parameter, which can refer to the local machine. The loader rejects non-Bash shells and exports
the loaded settings to child deployment scripts. Its loaded marker avoids repeated sourcing
within that process tree; start a fresh Bash process after changing `.env.local`.

This is trusted shell-format operator input, not an agent-editable settings file. It configures
deployment tooling; it is **not the agent's runtime `.env`, `config.yaml`, OAuth store or a way
to change live model/bot settings**. Reading or editing it alone does not deploy anything.
Do not copy it into containers, server build contexts, tracked documentation or Git. Publish
only placeholder variable names/examples; keep credentials in the existing private secret store.

Live inventory, provider identifiers, software inventory and resource snapshots belong in
private operator records. Public deployment layout below is the project's default layout.

No dashboard or published service ports. Telegram uses outbound polling. Key-only host SSH,
UFW incoming deny except SSH, Docker WAN filtering, unattended upgrades. All deployment
changes must preserve these controls.

### Paths

| Host path | Purpose |
|---|---|
| `/opt/alfie/hermes-agent` | Upstream source; gateway image baseline |
| `/opt/alfie/docker-compose.alfie.yml` | Operational Compose, service keys gateway/sandbox/websearch/egress |
| `/opt/alfie/data` → `/opt/data` | Gateway HERMES_HOME; credentials, config, memories, cron and databases |
| `/opt/alfie/data/shared` | records.db and email_watch.db; gateway-only, no shell sandbox mount |
| `/opt/alfie/data/security` | Private SQLite approval state; never mounted in sandbox |
| `/opt/alfie/ssh` | Gateway-to-sandbox SSH key; not under HERMES_HOME |
| `/opt/alfie/websearch/pki` | Worker mutual-TLS CA and certificates; not under HERMES_HOME |
| `/opt/alfie/google-workspace` | Gateway plugin, fixed Google scripts and skill |
| `/opt/alfie/web-browser` | Browser plugin, skill and seccomp profile |
| `/opt/alfie/deployment` | Cutover tooling and protected upstream credential guard |
| `/opt/alfie/backups/four-container-*` | Root-only rollback configuration and image references |
| `/usr/local/sbin/alfie-docker-firewall.sh` | Persisted host/bridge firewall |

The command sandbox can read immutable skill/script trees but cannot access the shared records mount. It must not receive
`.env`, `auth.json`, Google tokens/client secrets, gateway databases, host files, vaults or
Docker sockets. Google script dependencies live in the gateway. Skills carry no Google
`required_credential_files` declarations; the credential guard also refuses registration.

The public worker receives neither HERMES_HOME nor records. It holds its own TLS server key;
this is a service identity, not an external account credential. OpenAI access and refresh tokens
stay in the gateway; a fixed, bounded broker serves job-bound inference over the existing mutual-TLS
connection. Browser actions need no model token.

## 4. Capabilities

### Telegram and model

Telegram identity and user allowlist belong in private runtime configuration. Keep all alternate authorization
paths closed: wildcard allowlists, allow-all flags, bot allowances and unintended pairing
approvals. Telegram is not end-to-end encrypted; never send credential values there.

Model configuration belongs in config.yaml, which takes precedence over .env. Provider is
`openai-codex`; the paid API provider is `openai-api`. Empty fallback chain is an owner rule.
OAuth re-authorization is operator-managed. No token values in logs or validation output.

### Google and email-watch

The gateway tool `google_workspace` exposes fixed Gmail, Calendar, Drive, Contacts, Sheets
and Docs operations. No arbitrary shell, URL proxy, local-file upload/download or credentials
operation. Granted OAuth scopes remain unchanged by this deployment; Drive was narrowed to
`drive.file`; the live scope metadata was verified, and missing metadata fails closed.
Reads execute directly. Writes from the configured owner Telegram task receive a full JSON review;
only its authenticated button callback can execute the immutable action once. Replies freeze the
actual recipient/thread/headers before review. Reviews expire after 24 hours or restart. A timeout
or interruption after execution starts is unknown and must not be automatically retried.
Private approval policy uses `ALFIE_OWNER_TELEGRAM_USER_ID` for the sole owner plus the dedicated
`ALFIE_APPROVAL_CHAT_ID` and `ALFIE_APPROVAL_THREAD_ID` in `.env.local`. Owner requests may
originate in any topic of that forum; reviews and callbacks are restricted to the approval topic.
Runtime context, not model arguments, supplies identity.

`email-watch` runs every 30 minutes as an existing `no_agent` cron job. It reads each new email
once, calls a tool-less model, validates complete bounded results and stores pending/quarantined
observations. It cannot update Calendar, personal records or timezone. Its implementation and
budgets are in `email-watch/README.md`; the existing schedule/destination were preserved.
Direct observation-to-record promotion is not yet implemented. The owner can separately request
and approve a supported Google action. Shell-based records lookups are unavailable.

The live gateway Google labels read succeeded at acceptance. Existing email-watch remains a
configured `no_agent` job. No mail, calendar write, Telegram message or purchase was sent by tests.

### Research and interactive browsing

`research(question, depth)` returns a bounded summary with sources. It calls Tavily/Firecrawl
through egress and keeps bulk page content out of the orchestrator's context. The worker sends
bounded inference requests through the gateway broker without receiving model credentials.
The gateway broker/provider necessarily processes those inputs. See `web-search/README.md`.

`browse` provides open, snapshot, click, fill, select, scroll, back and close. It runs Chromium
in the same worker, with the Chromium sandbox enabled, read-only rootfs and bounded temporary
storage. Browser actions return bounded **raw page text** and element references to Hermes;
these are untrusted content, unlike the research tool's rebuilt brief. Summaries can also carry
malicious instructions; neither path eliminates prompt injection.

No account login, credentials injection, cookie export, uploads/downloads, arbitrary JavaScript
or public CDP endpoint. Anonymous session cookies exist until the disposable session closes.
Input guards are mitigations, not proof a website cannot disguise a credential/payment field.
Product links are portable; carts may depend on cookies and may not transfer to the owner.

### Memory, voice and scheduled operations

Local holographic memory stores facts/preferences. `records.db` stores obligations, events,
trips and bills. USER.md and MEMORY.md provide bounded hot context. Raw mail expiry remains
weekly; do not share personal records with the browser worker. SQLite WAL databases must be
mounted as directories so database and -wal/-shm files refer to the same storage.

Hermes natively handles Telegram voice notes and photographs. Voice transcription uses pinned
faster-whisper `base` in the gateway's durable optional-dependency target. Its short-voice profile
disables the redundant VAD pass and retains explicit confidence filtering. Actual Telegram use is
the current WIP integration check.
Keep the venv PATH patch at `/etc/profile.d/99-hermes-venv.sh`; verify actual execution paths.
Reminders use Hermes cron; `email-watch` and quota alerts are scripts. Existing expiry operations
remain operator-managed. Encrypted off-host backups use the pinned Drive backup folder manually,
with no recurring backup timer or automatic deletion. See `backup/README.md` for coverage,
offline recovery, key custody and limitations; this is not a complete host/image backup.
All cron deliveries use `cron.wrap_response: false`: send the job's content without the
automatic job-name/ID header, separator or management footer. Email reports use bold digest
and numbered email titles, unindented details and an explicit Open email link.

## 5. Security guarantees and limits

- Container isolation prevents shell/browser filesystem access to gateway credentials; no
  runtime component has the Docker socket. Workers cannot administer their own containers.
- Packet filtering enforces worker→proxy-only traffic, blocks worker→gateway/sandbox/host
  connections, and blocks proxy→private/reserved addresses. Squid separately enforces source
  and destination policy. Validate denial with live listeners, not only rule listings.
- Public browsing necessarily permits arbitrary public destinations. It can disclose anything
  sent to that worker. Do not claim destination allowlisting prevents public-worker exfiltration.
- Research and browser share one compromise boundary; a browser escape into the worker could
  expose its TLS identity and public task contents, but no model access/refresh token is there.
- Read-only rootfs, no swap for worker, bounded tmpfs and disabled core dumps reduce persistence.
  Provider credentials remain sensitive long-lived authority inside the trusted gateway.
- Google/Telegram tools can perform permitted account actions without revealing token bytes.
  Prompt injection can still misuse those actions or disclose content through the gateway.
- Native plugins, cron scripts and integration code run in the trusted gateway. Tool allowlists
  and prompts are not an OS boundary. Only reviewed operator-managed code belongs there.
- Payment details never belong on the VPS. Existing undocumented vault directories under
  HERMES_HOME must not be mounted, synced or connected to the browser; their disposition needs
  owner review. Do not delete personal data during this deployment.

## 6. Operating rules

1. Make subsystem changes in this repository, then deploy with its deploy.sh. Root deployment
   orchestration is `deployment/deploy.sh`; acceptance is `deployment/verify.py`.
2. Preserve user edits. Do not update Hermes upstream or enable provider fallback incidentally.
3. Every container write into HERMES_HOME uses uid 10000; host writes restore that ownership.
4. Never print credential files, unmasked config, private email or records to prove functionality.
   Report booleans/counts/status instead. Never call Telegram getUpdates beside the gateway.
5. Test through the real Hermes terminal/tool path, not only `docker exec`. SSH runs `bash -c`,
   not a login shell, and gets its proxy variables from sshd SetEnv.
6. Recheck boundaries after configuration changes. Preserve br_netfilter and bridge filtering;
   DOCKER-USER does not govern host INPUT.
7. Back up SQLite with its online backup API; never copy live WAL database files alone.
8. Scheduled scripts need deadlines and no automatic retries of non-idempotent writes.
9. Credentials originate in the operator's private secret store; provisioning may overwrite runtime .env.
10. Commit messages are one short line with no attribution trailers.

## 7. Remaining work

- Keep normal assistant interaction native and frictionless; do not introduce another general
  permission classifier in front of conversation or media.
- Keep exact-action approval for concrete Google account changes and connector-level validation.
- Decide whether to retain or separately approve deletion of the synthetic Drive test folder.
- Audit concrete write, deletion and export endpoints directly, and add useful personal-record lookup.
- Extend provider-specific outcome reconciliation and atomic write preconditions where supported.
  Full replacement-host recovery tests are deferred, not claimed complete. Google subprocess limits
  and credential-free research are deployed. Confirmations do not isolate gateway compromise.
- LLM commands in the shell sandbox need a separate access-token delivery implementation;
  no model credential is provisioned there by this build.
- Browser compatibility varies; CAPTCHA, popup-only flows and authenticated checkout are outside scope.
- Track Chromium security updates and rebuild the pinned worker promptly; do not leave a browser
  image indefinitely on its initial version.
- Research result caching and media-cache expiry remain deferred. Off-host backups remain manual.
- Review undocumented vaults, rotate previously exposed personal credentials if outstanding,
  decide whether to retain the unused paid API key, and review external firewall coverage.
- Certificate expiry is tracked privately; rotation is operator-managed and must update both ends.
- Maintain firewall-first boot gating and re-test after network/runtime changes. A real VPS reboot
  and continuous denied probes during transactional firewall replacement passed.
