# Alfie — current specification

Spec version: 0.39. Updated: 2026-09-19.

Self-hosted personal AI agent with Telegram, memory, reminders, email and public-web research.
This document describes the whole system and current decisions. Subsystem READMEs own their
implementation details. History is in git. `plan-next.md` records the active build and checks.
Public-release cleanup and its remaining history gate are in [publication-plan.md](publication-plan.md).

## 1. Status

The four-container browser/security build is deployed and verified on the VPS. Interactive
public browsing and research share one worker; Google operations run in the gateway without
forwarding credentials to the command sandbox. Live acceptance passed on 2026-09-19;
measurements and test limits are in [deployment/acceptance.md](deployment/acceptance.md).

### Use cases

| ID | Use case | Scope |
|---|---|---|
| UC1 | Find a product and prepare a purchase | Public browsing/cart preparation; owner logs in and pays on their device |
| UC2 | Find an email record and act on it | Gmail search/read and supported Google operations; no private email in the public browser |
| UC3 | Research a question or product | Research summary with sources; interactive browsing when needed |
| UC4 | Voice notes and photographs | Local transcription and model vision |
| UC5 | Correspond by email | Gmail send/reply; existing owner decision permits sending without a new confirmation gate |
| UC6 | Remember facts, obligations and reminders | Local fact store, records, scheduled reminders |
| UC7 | Keep preferences and learning | Local memory and USER.md |

### Subsystems

| Directory | Responsibility |
|---|---|
| `email-watch/` | Tool-less email classification, records/calendar updates, Telegram reports |
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
| Voice | Local faster-whisper `base` |
| Search/extraction | Tavily and Firecrawl, currently keyless; no provider keys in public worker |
| Timezone | Configured home timezone; scheduled tasks and travelling owner use their explicit current timezone |

## 3. Host and runtime

Deployment target and public host addresses are configured in ignored `.env.local`.
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
| `/opt/alfie/data/shared` | records.db and email_watch.db; shared with shell sandbox |
| `/opt/alfie/ssh` | Gateway-to-sandbox SSH key; not under HERMES_HOME |
| `/opt/alfie/websearch/pki` | Worker mutual-TLS CA and certificates; not under HERMES_HOME |
| `/opt/alfie/google-workspace` | Gateway plugin, fixed Google scripts and skill |
| `/opt/alfie/web-browser` | Browser plugin, skill and seccomp profile |
| `/opt/alfie/deployment` | Cutover tooling and protected upstream credential guard |
| `/opt/alfie/backups/four-container-*` | Root-only rollback configuration and image references |
| `/usr/local/sbin/alfie-docker-firewall.sh` | Persisted host/bridge firewall |

The command sandbox can read skill/script trees and modify shared records. It must not receive
`.env`, `auth.json`, Google tokens/client secrets, gateway databases, host files, vaults or
Docker sockets. Google script dependencies live in the gateway. Skills carry no Google
`required_credential_files` declarations; the credential guard also refuses registration.

The public worker receives neither HERMES_HOME nor records. It holds its own TLS server key;
this is a service identity, not an external account credential. The gateway sends an OpenAI
access token per research request, never its refresh token. Browser actions need no model token.

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
`drive.file`. A plugin changes token exposure, not the power of permitted send/modify actions.

`email-watch` runs every 30 minutes as an existing `no_agent` cron job. It reads each new email
once, calls a tool-less model, and applies structured records/calendar/timezone updates. Its
implementation and budgets are in `email-watch/README.md`. Preserve its current local edits
and live schedule. Do not redeploy unrelated changes as part of the browser cutover.

The live gateway Google labels read succeeded at acceptance. Existing email-watch remains a
configured `no_agent` job. No mail, calendar write, Telegram message or purchase was sent by tests.

### Research and interactive browsing

`research(question, depth)` returns a bounded summary with sources. It calls Tavily/Firecrawl
through egress and keeps bulk page content out of the gateway context. The worker uses a
per-request OpenAI access token and mutual TLS. See `web-search/README.md` for budgets.

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

Voice transcription uses faster-whisper `base`, installed via gateway lazy dependencies.
Keep the venv PATH patch at `/etc/profile.d/99-hermes-venv.sh`; verify actual execution paths.
Reminders use Hermes cron; `email-watch` and quota alerts are scripts. Host timers provide
backup and record expiry on privately configured schedules. Off-box backup remains deferred.
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
  expose the worker TLS identity or model access-token copies. No refresh token is there.
- Read-only rootfs, no swap for worker, bounded tmpfs and disabled core dumps reduce persistence.
  Python token memory erasure remains best effort. Access tokens are not assumed short-lived;
  the previous measured lifetime was 10 days.
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

- LLM commands in the shell sandbox need a separate access-token delivery implementation;
  no model credential is provisioned there by this build.
- Browser compatibility varies; CAPTCHA, popup-only flows and authenticated checkout are outside scope.
- Track Chromium security updates and rebuild the pinned worker promptly; do not leave a browser
  image indefinitely on its initial version.
- Research result caching, media-cache expiry, tool-schema/token reductions and off-box backups remain deferred.
- Review undocumented vaults, rotate previously exposed personal credentials if outstanding,
  decide whether to retain the unused paid API key, and review external firewall coverage.
- Certificate expiry is tracked privately; rotation is operator-managed and must update both ends.
- Verify firewall restoration after a scheduled host reboot; persistence is configured and enabled,
  but this deployment did not reboot the VPS.
