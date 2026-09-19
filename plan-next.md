# Alfie — security enhancement plan

Date: 2026-09-20. Status: useful natural-language modes, four-container hardening and Telegram
Google approvals deployed; automated checks, owner self-test approval/rejection and an approved
Drive mutation passed.
Latest owner direction: keep the existing containers and scarce resources. Use Telegram approvals;
gateway access is available and deployment has proceeded. This supersedes additional-service proposals
as the immediate implementation target. The larger isolation design below remains a future option.
Account re-authorization, provisioning and credential rotation remain separate work. Encrypted
Drive backups are manual, with the recovery key on the owner's Mac. Brief outages are permitted
after advance notice; no recurring backup or retention deletion is authorized.
Difficult/disruptive recovery tests are deferred by owner direction, not release blockers.
Use code-path reasoning and small focused checks, and distinguish those from live evidence.
Current deployed design remains in [main-spec](main-spec.md); prior acceptance remains in
[deployment/acceptance](deployment/acceptance.md). Git retains the completed build plan.

## P0 — usefulness and natural-language intent (deployed)

Owner requirement: the assistant must be useful, not blocked by routine permissions and rigid
wording. Deployed without relaxing exact-action account approval or private/public separation.

1. Replace the narrow fallback with a tool-free intent proposal using only the authenticated
   owner's current text, fixed mode catalogue, bounded input/output and existing model/provider.
   No conversation history, retrieved content, memory, tools or additional credentials.
2. Validate the proposal outside the model. Unsupported/mixed requests get a specific, useful
   clarification. The model cannot invent capabilities, authorizations or approval decisions.
3. Normal chat and read requests must not require prefixes. Keep explicit prefixes as an optional
   diagnostic interface. Review unnecessary read-confirmation friction while retaining bounded
   selectors/result IDs; exact account changes always require their own owner review.
4. Preserve all forum topics as valid request origins, the dedicated approvals topic, fixed cron
   grants, no paid fallback and current container/resource limits. Existing writes remain queued.
5. Use small paraphrase, malformed-output and authorization regressions, installed-runtime checks
   and safe read-only live checks. Do not block delivery on difficult recovery exercises.
6. Record actual deployment evidence separately from source reasoning and owner UI confirmation.

Deployment result: routine chat, public research/browser work, bounded private reads, local
memory, safe reminders and voice/photo input work without mode-prefix memorization. Private
reads pin their first bounded selector without a confirmation card. Supported Google writes go
straight to one immutable exact-action review. Mixed private/public tasks fail with a specific
clarification. General shell, cron, messaging, private export and unsupported attachments remain
blocked. Next work is provider-side redirect/DNS containment and the remaining restricted
records/observation promotion path; difficult recovery exercises remain deferred.

## Deployed four-container increment

- Google reads retain their current interface. Every Google write queues a bounded private
  pending action. There is deliberately no model-callable approve path. The deterministic Telegram
  handler validates owner/chat/topic/review-message identity and consumes an approval once before
  executing the frozen action. Reply recipients/headers are resolved before review. Requests expire
   after the task's 30-minute lifetime or restart; queue retention is 24 hours and unknown
   execution outcomes are retained without automatic retry.
- email-watch validates full batch schemas and IDs, stores pending/quarantined observations,
  and reports for review. It no longer writes Calendar, personal records or USER.md. Observations
  expire after 30 days when the ledger is opened; at most 2000 are retained. Existing personal
  records remain on disk and existing reminders are not deleted.
- Deployment removes known personal-data binds from sandbox, makes code mounts read-only and
  stages email-watch code as read-only mounts without changing its cron registration.
- Firewall rules were syntax-tested and replaced in one filter-table transaction;
  worker restrictions run before the general established-connection allowance.
- No persistent application service, container or third-party Python dependency is added; configured container
  memory ceilings are unchanged. Existing images were reused. Live isolation/packet checks and
  resource samples passed; see deployment/acceptance.md. A systemd firewall-first startup gate,
  real VPS reboot, update-gap probes and offline encrypted data recovery have now passed.

Release status and remaining gates:

1. Exact-action Google acceptance passed: after fixing the dispatcher mismatch, the owner approved
   the synthetic Drive-folder request; private state records succeeded with a valid digest and a
   read-only search found exactly one folder. All 47 Google runtime tests pass. Decide
   whether to retain it or add an explicitly approved deletion operation. The broader audit remains open.
   A dedicated approval topic is now deployed: owner requests are accepted from any topic in the
   same configured forum, while buttons and callbacks remain restricted to the approval topic.
   The earlier natural-language scope confirmation was removed after its two-review test: it was
   redundant with the exact-action card. Natural-language writes now receive only the meaningful
   immutable action review; the exact-action queue continues to enforce rejection/execution.
2. Initial task-scoped enforcement is deployed: forty installed-runtime policy/approval tests
   and live read/denial checks passed. Owner write-mode review/approval now has a matching
   succeeded queue record. Subsequent owner rejection and web-read smoke checks passed;
   repeatable instructions are in [task-permissions/SMOKE-TESTS.md](task-permissions/SMOKE-TESTS.md).
   The discovery integration fix is deployed: tasks receive direct connector schemas without
   granting discovery helpers. All-mode runtime schema checks and post-cutover read/denial
   checks passed; fresh owner tasks used direct connectors without discovery errors.
   Cron review completed: one active reminder has a frozen tool-free grant; two completed
   reminders stay disabled. Fixed-script grants and all schedules are unchanged. Restore
   usability only through bounded resource scopes and explicit exports. Fresh task history is
   retained; public tasks exclude private memory. Disposable public browsing, isolated local
   memory, narrow tool-free reminders, authenticated voice and chat-only photographs are restored.
   Shell, general scheduling and messaging remain disabled. See
   [task permissions](deployment/task-permissions.md) for implementation and remaining contract.
3. Research access-token delivery is removed. A fixed gateway broker handles bounded, job-bound
   inference over the existing mutual-TLS connection; all 34 installed-worker tests and live
   research passed. Research subprocesses are killable on deadline/disconnect. Still implement
   further provider-side redirect/DNS containment; browser/research share a UID. Local retrieval
   now limits raw responses before parsing, rejects compression/redirects at provider endpoints,
   validates result schemas and preflights scraper URLs against public addresses. Remote scraper
   DNS/redirect behavior is not controlled by the local firewall or preflight.
4. Actual sandbox mounts and firewall packet rules passed. Audit residual caches, restore required
   lookup/promotion workflows through a restricted gateway interface. Firewall-first reboot and
   update-gap probes passed. Encrypted Drive upload/read-back and offline recovery passed (26
   artifacts, 14 SQLite databases, restored approval invalidation). Full replacement-host/image
   recovery remains deferred, not a release blocker. Backups stay manual; no retention deletion is enabled.
5. OAuth scope metadata matches the documented Drive restriction; missing metadata now fails
   closed. Google streaming output/process-group limits are deployed. Complete
   provider-specific outcome evidence and atomic preconditions where available. Target enrichment,
   pre-execution context comparison, nested argument validation, literal Sheets values and a
   read-only reconciliation helper are deployed. Private reads pin the first bounded selector and
   permit only bounded returned IDs afterward, without a redundant review. Private exports remain disabled.
   Expanded cron fingerprints are deployed; all five existing definitions match, three grants
   remain permitted and two completed reminders remain disabled. No jobs were executed in tests.

The gateway remains a shared credential/process trust boundary. The queue protects the exposed
Google plugin path, not arbitrary code execution inside that gateway. Approval code is deployed,
and real self-test clicks plus an approved Drive mutation are verified. Observations cannot currently be
promoted directly into personal records through Telegram.

## 1. Objective and evidence

Contain malicious web/mail/document content, arbitrary agent commands and a compromised public
worker. Prevent those inputs from granting permissions, performing unapproved account writes,
exporting private information or changing trusted instructions. Preserve research, Google
assistance, email triage, records, reminders and voice/image input through explicitly scoped paths.

The current release includes live SSH inspection, pinned Hermes source review and runtime
acceptance; it is not proof that prompt injection is impossible. The findings table below records
the pre-hardening baseline and longer-term design, not a claim that all listed weaknesses remain
unchanged. Current deployed controls and test limits are in the status above, main-spec.md and
deployment/acceptance.md. Authenticated voice notes and chat-only photographs have a tested narrow
path; documents, ordinary audio files and video remain blocked. Do not assume an untested path is safe.

Threats include indirect prompt injection, cross-task data disclosure, poisoned persistent memory,
misused credentials, unsafe parsing, dependency compromise, denial of service and lost backups.
Host administrator, approval service and connector compromise remain trusted-boundary failures.
A mistaken human approval can still authorize a harmful action. Payment/login automation remains
outside scope.

## 2. Pre-hardening findings and longer-term changes

| Subsystem | Verified source or documented baseline | Enhancement |
|---|---|---|
| Hermes gateway and Telegram | Gateway combines private context, credentialed plugins and broad network access. Deployment enables Google, research and browser toolsets together. Full upstream authorization is not vendored. | Separate authenticated transport/policy from model orchestration. Remove account credentials from the orchestrator; enforce permissions at connector endpoints. Inventory every native tool and alternative path. |
| Google Workspace | Fixed operations, argument validation, no shell, 60-second timeout. No task/recipient/resource authorization check in the plugin; read and write operations share credentials. | Separate read and write connector identities; resource-scoped read grants and exact-action write approval. No arbitrary URL, shell, credential or file transfer API. |
| email-watch | Tool-less classifier; deterministic code subsequently creates records/calendar events. Suspicious results are reported but still applied. Travel records can update USER.md. | Unprivileged parser/classifier producing pending proposals. Separate validator and executor. Approval before external writes and promotion to trusted preferences. |
| Records, memory and reminders | Sandbox has read/write shared records and email-watch ledger according to the specification. update_zone reads travel records and writes persistent user context. Other memory/records sources are absent. | Single records service owns databases. Remove shared DB mounts from arbitrary execution. Separate external observations, approved facts and owner policy; protect scheduler configuration. |
| Command sandbox | SSH command isolation, narrow egress, no forwarded Google credentials. Persistent shared data remains accessible; sshd needs startup capabilities. | Disposable per-job workspace, no personal-data mounts and no network by default. Explicit bounded data exports and independently checked artifact imports. |
| Public research | Bounded briefs and tool-less model calls; gateway sends a reusable provider access token to the worker. Search and scrape requests disclose queries/URLs to external providers. | Dedicated research service, no provider credentials, fixed inference broker and retrieval-provider egress only. Public-only input contract. |
| Public browser | Sandboxed Chromium, ephemeral context, bounded actions, URL checks, no account mounts. Shares worker/process environment with research; raw text returns to gateway. | Separate browser runtime and identity; public-only task context. Default inspection mode, deliberate grants for interaction. Stronger isolation from private services. |
| Egress | Squid plus host filtering; public web worker has arbitrary public HTTP(S). Docker DNS is explicitly not an exfiltration-proof boundary. Gateway remains broadly connected. | Per-service network policy including gateway; controlled DNS; fixed connector destinations; no private-context process with arbitrary public egress. |
| Deployment and host | Active firewall chains are flushed before reconstruction. Compose is modified from existing live configuration. Staging can replace active bind-mounted code. Reboot/restore untested. | Atomic filtering, explicit validated runtime manifest, immutable release staging, fail-closed startup and tested recovery. |
| Voice, images and attachments | Local transcription/model vision documented; ingestion source absent. Transcribed or extracted content can contain instructions. | Isolated decoding, bounded inputs and retention; provenance survives transcription/OCR. Media text cannot itself approve actions. |
| Publication and operations | Local scanners pass, but source still contains owner-specific prompt text. Off-host backup and remote artifact review remain incomplete. | Manual identifier review, broader CI scanning, encrypted independent backups, patch/expiry monitoring and incident procedures. |

Source anchors (line numbers refer to the reviewed source):

- Gateway configuration: deployment/apply.py:69 and main-spec.md:95.
- Google permissions and validation: google-workspace/gateway-plugin/__init__.py:10, :34, :70.
- OAuth discrepancy: google-workspace/scripts/google_api.py:45 lists full Drive scope; :71
  falls back to SCOPES when stored scope metadata is unavailable. main-spec.md describes
  drive.file. This does not prove the live token has full Drive access or silently gains it.
  Verify actual grants privately, reconcile code/docs, and fail closed on unknown scopes.
- Email effects: email-watch/email_watch.py:535, :606, :652, :706, :766, :791.
  ensure_event tests the truthiness of confirmed rather than requiring a boolean; JSON parsing
  is not a complete schema validator. For example, a string "false" is truthy.
- Shared personal data: sandbox/README.md, deployment/acceptance.md:63.
- Token transport: web-search/gateway-plugin/__init__.py:82. Its expires_at value is constructed
  as current time plus 420 seconds; it is not the provider token's actual expiry or revocation.
- Research follow-up queries: web-search/worker/research.py:235 and :242.
- Browser routing/actions: web-browser/worker/browser.py:93 and :152.
- Firewall replacement: deployment/firewall.sh:11 and :33.
- Recovery limits: deployment/acceptance.md:51. Publication gates: publication-plan.md.

## 3. Authorization and data-flow design

Use a small deterministic policy service that the model cannot edit. These are proposed new
components/contracts, not existing functions. mTLS authenticates a service; a separate job grant
authorizes its particular action. Neither an LLM-produced approved=true nor a valid client
certificate alone is sufficient authorization.

1. The authenticated owner request enters a transport service with a fixed destination policy.
   Owner identity is established from authenticated transport metadata, never message prose,
   forwarded-message attribution, email headers, transcription or model output.
2. The policy service creates a bounded task grant from an owner-selected mode or confirmed
   proposed scope. Model classification may propose a mode but cannot expand privileges.
   Bind each grant to owner/session, task, caller service, operation, resource selection,
   permitted data destinations, expiry, policy version and usage budget.
3. The orchestrator gets only that task's data and tool handles. Do not reuse private mailbox
   context in public research sessions. Derived summaries keep their source confidentiality.
   Labels/provenance are assigned by trusted runtime code and cannot be cleared by the model.
4. A connector validates the grant on every invocation, including reads. Searching an inbox
   requires a bounded query/date/result scope; changing that scope requires authorization.
   A record ID or browser session ID is not evidence that the caller may access it.
5. Only tasks with explicit write-proposal permission may create pending actions. Read-only
   tasks cannot generate actionable approval requests. A deterministic review shows recipients, all
   destination fields, exact content or change, target resource, relevant source and effects.
   Materialize reply recipients before review; a message ID alone does not identify a trusted
   recipient. Escape untrusted markup and clearly separate source text from approval controls.
6. An authenticated owner confirmation authorizes the canonical stored action, bound to its
   digest, nonce, expiry and task. Any content/recipient/resource change invalidates approval.
   Atomically consume single-use authority; prevent replay and concurrent double execution.
   The model cannot submit or manufacture the owner confirmation.
7. The executor checks policy again immediately before use. Record pending/executing/succeeded/
   failed/unknown outcomes. If the provider might have accepted a timed-out write, reconcile
   before retrying; do not promise exactly-once delivery where the API cannot guarantee it.

Keep one Telegram poller. A transport adapter forwards authenticated events to policy; the
orchestrator cannot call Telegram or create actionable approval buttons directly. Plain-text
"yes" without a bound pending action is insufficient. For maximum assurance, perform sensitive
approvals in an independently authenticated owner interface reachable only over private access;
Telegram can notify without carrying sensitive previews. Telegram remains a trust dependency
for any approvals intentionally supported there. No new public dashboard is required.

Proposed task permissions:

| Task | Allowed inputs and capabilities | Forbidden without a new explicit grant |
|---|---|---|
| Public research/shopping | Owner-supplied public brief; search/browser; reply to owner | Mail, records, private conversation history, account writes |
| Private lookup | Specific mail/docs/records; inference via approved provider; reply to owner | Public browsing/search, third-party destinations, modifications |
| Draft correspondence | Selected thread/context; local pending draft | Actual send, extra recipients, unrelated mailbox searches |
| Approved account action | Exact stored action and authorized resource; one execution | Changed body/target, replay, additional actions |
| Email triage | Bounded new-message batch; tool-less extraction; pending observations; fixed owner digest | Sending mail, automatic calendar write, trusted memory/preferences changes |
| Code execution | Explicit task files in isolated workspace; bounded output | Host/personal DBs, credentials, general internet, policy/cron edits |

A task allowed to read private data must not be able to encode it into public URLs, search
queries, DNS names, form values, filenames or outbound notifications. Exporting private-derived
information to a public task requires owner review of the exact exported material and destination.
An LLM redactor or another LLM's safety verdict cannot authorize that export.

Owner output is a permitted sink, but render external links without automatic previews or
remote image loads. Resolve and validate links; do not automatically fetch links emitted by
private-data models. Provider inference is an explicit data transfer with its own policy;
brokered access does not make model processing local or prevent provider exposure.

## 4. Proposed runtime boundaries

Establish separate service identities, filesystem ownership and narrowly allowed connections.
Network segmentation must remain effective if an untrusted process ignores proxy environment
variables. No runtime service receives the Docker socket, host administration key or permission
to change policy.

- Transport/policy/approval: small reviewed service; owner authentication, grants and pending
  actions. Holds messaging credential and authorization state. No plugins or generated code.
- Model orchestration: no external-account secrets, deployment tools or policy-signing authority.
  Runs with a strict tool allowlist; worker and connector access requires task grants.
- Google connectors: credentials owned only here; distinct read/write grants and, where provider
  consent supports it, distinct narrowly scoped tokens. Writer never interprets free-form requests.
- Records service: sole DB owner; typed reads/writes, provenance and policy-controlled promotion.
  Keep external observations out of owner instruction files. Runtime timezone is a typed setting.
- Email/media processing: isolated parsing/classification jobs. Retrieve only assigned messages
  through the read connector. No direct credentials, calendar access or user-memory mounts.
- Inference broker: sole provider-token owner/refresher, fixed upstream and request schema,
  no arbitrary HTTP forwarding or caller-supplied authorization headers. Enforce caller/task,
  model, input/output sizes, deadlines, concurrency and usage limits; preserve no paid fallback.
- Public research: separate from Chromium; provider retrieval plus inference broker only.
  Validate outbound URLs before sending them to a remote scraper; host SSRF rules do not govern
  requests made by the external scraper. Bound response bytes before JSON parsing/text slicing.
- Browser: its own process/container, service identity, tmpfs and ephemeral job storage.
  No model token, refresh token, private data or research-worker mount.
- Shell: separate disposable jobs; fixed execution API or hardened SSH with pinned host keys,
  forwarding disabled and minimal startup privilege. Exported results are untrusted.
- Egress: distinct source policies for each class of service, including trusted connectors.
  DNS forwarding for private workers accepts only required service/provider names.

These are security boundaries, not a requirement for one permanent container per bullet.
Combine components only after documenting the permissions exposed by their joint compromise.
Google credentials and public parsing/browser execution must never share a process or mount.

For the strongest isolation target, put arbitrary code and browser workloads on a separate
VM/host or compatible VM-based execution runtime, away from credentials and personal databases.
Separate containers on the same kernel remain an intermediate defense. Evaluate compatibility,
resource use and operations before choosing the runtime; do not silently disable Chromium's
sandbox. A host/kernel exploit or compromised administrator is not contained by ordinary Docker.

The last documented host has about 3.8 GiB RAM. Existing memory ceilings total 2944 MiB before
host overhead; they are ceilings, not reservations. Do not assume the larger topology fits.
Measure representative browser, transcription, research and mail workloads with headroom;
retain scheduling limits and provision additional capacity before accepting higher concurrency.

## 5. Subsystem implementation requirements

### Google and approvals

- Default all account mutations to pending approval: Gmail send/reply/modify, calendar
  create/delete, Drive folder creation, Sheets and Docs writes. Resolve full target details.
- Reduce OAuth scopes and resources to the demonstrated use cases. Verify actual grants and
  perform deliberate revocation/re-consent when needed; editing a source list is insufficient.
  drive.file deliberately limits file visibility; preserve that restriction rather than silently
  adding broad Drive access when a lookup fails.
- Bound input and output bytes during execution, not only after subprocess capture. Terminate
  subprocess groups on timeout; validate nested JSON values and header/address syntax.
- Protect existing shared documents/sheets as external disclosure destinations, even when the
  operation looks like an ordinary edit. Audit record contains action metadata and protected
  content references; avoid raw private bodies/tokens in general logs.

### Email, records, memory and scheduling

- Strict schema: exact booleans, input-associated unique message IDs, bounded lists and strings,
  valid dates/timezones, finite nonnegative monetary values and permitted enum values. Reject
  malformed/missing/duplicate entries without marking them successfully processed.
- Isolate messages or tightly constrain batch mappings to reduce cross-email contamination.
  Retain source IDs and extraction version. Parsed ICS is untrusted sender input, not proof of
  a real booking, owner consent or authority to change timezone.
- suspicious=true stops automatic effects and quarantines the proposal. suspicious=false does
  not authorize anything; policy validation is mandatory for every result.
- Store extracted tasks/bills/events/trips as pending observations with retention and review.
  Calendar creation requires approval; no automatic attendee invitations. Preserve useful
  automatic digest delivery to the fixed owner destination under an explicit standing policy.
- Remove records.db and email_watch.db mounts from command execution. Protect source bindings
  and processing ledger against modification by workers. Review all other record/memory writers.
- Eliminate free-form external text interpolation into USER.md. Owner policy/preferences remain
  separate from quoted evidence. Timezone changes and trusted fact promotion require approval.
- Scheduled work runs reviewed fixed handlers with separate grants, overlap locks, deadlines,
  per-run quotas and reconciliation. The model cannot create arbitrary cron code, alter delivery
  destinations, or change security policy through memory/skill files.

### Browser, research and execution

- Retain no login/payment, no downloads/uploads, no exposed browser debugging endpoint, sandbox,
  no-new-privileges, dropped capabilities, read-only rootfs and bounded writable storage.
- Default to passive inspection. Enable click/fill/select only within an explicit public task;
  domain restrictions and input-field heuristics are supporting controls. A click or GET can have
  side effects; generic web interaction cannot be certified read-only from HTTP method alone.
  Maximum-assurance shopping produces product/variant links; cart interaction is optional.
- Fresh task sessions; associate browser ownership with authenticated service/task identity as
  well as opaque session ID. Expire/revoke worker identity and grants after a task.
- Enforce deadlines with cancellable job processes (deployed for research). Verify actual child
  termination, not merely connection timeout. Budget checks between rounds alone do not strictly
  cap a series of slow retrieval requests.
- Bound network responses, decompression, DOM/text extraction, websocket frames, model output,
  queues, disk, CPU and PIDs. Enforce limits before retaining whole responses in memory.
- Treat search results, source titles/URLs, summaries, shell output, transcriptions and OCR as
  untrusted. Test multi-step attacks that first persist content and act in a later session.
- Private code jobs receive only explicit snapshots, run without network, and return artifacts
  through validation. Adding LLM CLI access must use task-scoped inference, never copied tokens.

### Network, host and operations

- Replace active firewall flushing with validated transactional rule replacement or inactive
  chain construction and atomic switch. Preserve unrelated Docker rules and operator SSH.
  Review established-connection handling; deny revoked flows instead of assuming old sessions
  remain acceptable. Test continuous probes throughout update and rollback.
- Start workers only after filtering is installed; cover Docker daemon restart, host reboot,
  interface/address changes and failed policy loads. Discover/validate WAN interfaces rather
  than assuming eth0. Explicitly disable IPv6 or enforce equivalent IPv6 rules.
- Inspect DNS paths, bridge bypasses, host INPUT, forwarded traffic, proxy compromise, public
  host addresses and metadata. The private tier should have no unrestricted recursive DNS.
- Establish a sanitized explicit Compose/config baseline: mounts, capabilities, rootfs, user,
  networks, resource caps, published ports, tool/plugin registry and credentials. Reject drift.
- Build versioned immutable releases and activate together; do not overwrite running plugin
  mounts during staging. Pin reviewed dependencies/base digests with an update process, scan
  images/dependencies, record provenance and verify artifact integrity.
- Read-only code/skills; no runtime package installation in credentialed services. Keep seccomp
  and mandatory-access-control restrictions compatible with the verified browser sandbox.
- Rotate service PKI with distinct identities/roles, correct certificate usage and expiry alerts.
  Keep CA private material outside workers; test overlapping renewal and removal of old trust.
- Encrypt off-host backups; use SQLite online backups and include DBs, pending action state and
  configuration consistently. Keep recovery keys separately. After restore invalidate old grants
  and approvals; reconcile uncertain external actions before enabling writers.
- Add protected audit trails and alerts for denied actions, unusual volume, policy/mount drift,
  failed jobs, certificate expiry, disk pressure and patch backlog. Provide an operator kill
  switch that revokes writes/public access without deleting personal data.
- Review residual vaults, unused credentials and prior exposure privately. Revoke confirmed
  exposed credentials; clean backups/logs under a separate retention policy.
- Before publication, manually remove remaining personal prompt content and review remote
  artifacts/history. Pattern scanners do not prove the absence of personal identifiers.

## 6. Execution sequence and acceptance gates

| Phase | Work and primary ownership | Required evidence before proceeding |
|---|---|---|
| 0 — establish baseline | deployment; inspect running upstream/Compose/tools, scopes, mounts, auth paths and schedules; capture recoverable backups | Private inventory with boolean/count summaries, tested backup readability, exact gap list and resource budget. No mail/content/credential dumps. |
| 1 — contain current paths | deployment, Google, email-watch; atomic firewall; interim code-enforced write approval or disabled writes; pending extraction; stop external-to-USER.md promotion | Continuous denied network probes during update, restart/reboot acceptance in a scheduled window; every write path accounted for. Interim in-gateway checks are explicitly not process-compromise isolation. |
| 2 — authorization services | new policy/transport and connector boundaries; move secrets; task grants; review UI; protect records and scheduler | Forged, expired, modified, cross-task, replayed and simultaneous approvals denied; direct credential/API bypass impossible from orchestrator. |
| 3 — isolate untrusted work | browser/research split, inference broker, isolated mail/media and disposable shell; remove DB mounts; evaluate separate host/VM boundary | Compromised-worker simulation cannot access private data/tokens, reach other services, mint grants or exceed budgets. Measure host headroom. |
| 4 — recover and maintain | deployment/operations; immutable releases, scope/PKI lifecycle, update automation, encrypted backup/restore, monitoring | Full restore rehearsal, stale grants invalidated, unknown writes reconciled, certificate renewal and rollback pass. Independent security review before broadening access. |

Phases 2 and 3 must be designed together so existing tools cannot bypass the new broker.
Deploy each cutover as a complete boundary change; avoid leaving a legacy credentialed path
enabled beside the new approved path. Migrate pending records and existing cron state without
discarding data. Update main-spec and subsystem READMEs only to reflect verified runtime changes.

Minimum adversarial acceptance suite, using synthetic data and controlled endpoints:

- Webpage/summary asks to search Gmail and send it away: private reads and sends denied.
- Authorized private lookup asks for a public URL, query, form submission, DNS lookup or new
  message destination carrying a canary: denied before network transmission.
- Email/ICS asks to change trusted memory, timezone, cron or calendar: stays pending; no effect.
- Cross-email IDs, malformed booleans, oversized arrays, non-finite values and embedded markup
  cannot produce writes or forge approval UI.
- Altered recipients/body/target after approval, stolen task grant from another service,
  cancellation, expiry, concurrent replay and service restart all fail closed.
- External write timeout does not cause blind retry; restore does not resend completed mail.
- Kernel/process-level worker compromise assumptions tested separately from model injection:
  no secret mounts, no unrestricted private network/DNS path, no authority to change policy.
- Slow/hanging retrieval, decompression expansion, huge DOM, model stream and client disconnect
  remain bounded; cancelled jobs actually terminate.
- Malicious stored record resurfacing in a later session cannot become policy or obtain new tools.
- Voice/image input claiming approval cannot invoke the approval endpoint.
- Normal research, private lookup, owner-reviewed sending, digest, reminders and approved records
  still work. Provider side effects use mocks/test accounts; live real-account writes need exact
  action approval. Verify the actual Hermes tool path as well as service-level tests.

Rollback must preserve denied writes, credential separation and firewall restrictions. Disable
an affected feature when no safe compatible rollback exists. Never restore local shell execution
or old broadly credentialed mounts as an automatic recovery step.

## 7. Tradeoffs and residual risk

Owner review adds friction; private-to-public research requires explicit export; narrow Drive
scopes reduce searchable files; pending email records delay automatic calendar/timezone changes.
Removing shared DB access changes shell workflows. Additional services and VM isolation increase
maintenance and may require a larger or second host. More components also need more patching.

Even after acceptance, models may produce false summaries, misleading drafts or incorrect facts.
Schema validation establishes shape, not truth. Approvals protect only actions whose full effects
the owner can assess. Containers/VMs do not eliminate vulnerabilities. External providers, owner
device security, transport authentication, trusted connector code and backup custody remain
dependencies. Do not label the system prompt-injection-proof.

## 8. Guidance used

The concrete architecture above is a proposal derived from Alfie's source and owner direction.
Supporting principles: minimize task privileges, validate authorization outside the model and
treat external content as untrusted, as described in
[OWASP agent security](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html).
Prompts, detectors and separate summarization are supporting layers, not authorization boundaries:
[OWASP prompt injection guidance](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html).

Bind confirmation to the transaction actually executed:
[OWASP transaction authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html).
Review Docker forwarding controls separately from host access:
[Docker iptables documentation](https://docs.docker.com/engine/network/firewall-iptables/).
Choose Drive scopes deliberately; drive.file covers files explicitly shared with/created through
the application, whereas drive covers all Drive files:
[Google Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).
