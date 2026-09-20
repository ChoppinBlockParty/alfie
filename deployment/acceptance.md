# Deployment acceptance — 2026-09-20

## Latest verified increments

- Telegram media preprocessing is now a separate subsystem instead of policy-classifier code.
  The prior release evidence relied on mocked ingestion and missed an unusable local STT
  dependency. The deployed gateway now has the pinned STT runtime in its durable dependency
  target, transcribes voice before intent classification, and sends photographs through the
  existing vision path as tool-free, untrusted input. One-off diagnostics transcribed synthetic
  spoken audio and analyzed a generated image through the installed runtime. That synthetic test
  harness was then removed as disproportionate for the deeply WIP project; owner Telegram use is
  the current integration signal.
- The first owner retest exposed a second media defect: two valid 2.0--2.6 second Telegram Opus
  clips decoded correctly but were discarded as speech by the combined VAD and confidence defaults.
  Testing the cached clips without printing their transcripts showed that a bounded short-voice
  profile recovered them. The media subsystem now owns that profile and verifies configuration
  drift during activation. The permission-layer hard failure was also removed: STT remains the
  native Hermes path, and an empty result continues as a tool-free media response instead of
  rejecting the owner's message.
- Effect-oriented permission redesign deployed. Ordinary requests now choose tool-free chat,
  bounded all-service private Google reads, isolated public reads, additive memory, recoverable
  reminders, or one reviewed Google mutation. Private reads allow eight selectors/256 KiB but
  have no web, persistence or mutation path; an explicit write task may use bounded private reads
  to identify its target and then issue one matching proposal. Memory replacement/removal and
  reminder deletion are unavailable; cancellation pauses. The obsolete preliminary scope-review
  callback was removed. Eight configured-model probes covered personal facts, cross-service reads,
  public research, send intent, mixed private/public denial, memory, reminders and quoted malicious
  text. Local suites ran 135 tests (six environment-dependent skips). Post-cutover classifier,
  installed-schema, effect-denial, backup-readability and full deployment/network verification
  passed, including the operator-only Google labels health read. Owner Telegram UX remains to be
  retested.
- Personal-fact routing fix deployed after the configured classifier returned `unclear` for the
  owner's question `what is my inleg length`. Personal facts, measurements and preferences are now
  explicitly chat tasks, and any remaining `unclear` proposal falls back to tool-free chat rather
  than a generic permission-domain response. The exact reported text classified as `chat` after
  cutover with its original brief unchanged and no tools. Local suites passed 26 task-permission
  tests and 47 Google tests (two integration tests skipped); live denial checks and the latest
  rollback-backup readability check passed. Owner Telegram answer quality remains to be retested.
- Natural-language/use-case release deployed with the existing four containers and no new
  dependency. Eight synthetic calls through the live configured subscription model correctly
  classified email, web, Google write, memory, reminder and chat requests, rejected a mixed
  private/public request, and treated quoted prompt-injection text as chat data. Every accepted
  brief remained byte-for-byte the original owner text. Malformed/extra-key/unknown model output
  fails closed in unit tests.
- Installed overlay hashes/syntax, registry enforcement and every mode's concrete schema passed.
  Live denial checks preserve no-context, cross-mode, write, memory, cron, shell and unknown-browser
  denials. A real `web-read` grant opened and closed example.com in the disposable worker. Its
  first attempt exposed a browser registry-envelope mismatch before any page opened; the gateway
  was backed up/restarted with the adapter fix and the repeated check passed. A live read-only
  `reminder-read` call returned the filtered safe-reminder list; no reminder or memory entry was
  created. Existing cron policy and Google approval state were preserved.
- Private reads now pin their first bounded selector without a confirmation card. Natural-language
  Google writes go directly to the immutable exact-action card; the model still cannot approve or
  execute it. Memory is isolated to chat/memory tasks. New reminders are owner-only and tool-free.
  Voice is transcribed before classification; photographs are forced to chat-only and their
  vision/OCR text cannot grant tools. Other attachments remain blocked. The later media-subsystem
  evidence above supersedes this increment's mocked/runtime-only media evidence.

The remaining bullets in this section record earlier increments. Later evidence above supersedes
their statements about read-scope buttons, preliminary write-scope reviews and disabled use cases.

- Exact-selector private reads, target-context write reviews and bounded retrieval are deployed
  using the existing images/containers. Installed-runtime suites: 47 Google tests, 18 permission
  tests and 34 research tests pass. Coverage includes changed-query/unreturned-ID denial, rejected
  read scopes, cache/budgets, changed target context, nested values/addresses, literal Sheets
  writes, escaped Drive queries, response streaming limits and non-public destinations.
  Source inspection confirms owner/message binding and metadata checks; the new private-read
  button flow has not yet been exercised by the owner. No Google writes were made for acceptance.
  Post-cutover Google operator health read, unreviewed-private-read denial, network controls and
  public research passed. Existing cron grants are retained with the reviewed CLI dependency
  fingerprint updated. Difficult full-host recovery tests remain deferred, not a release blocker.
  Retrieval's initial direct-DNS preflight failed closed on this restricted worker and discarded
  valid results. The corrected implementation uses bounded fixed-endpoint HTTPS DNS over the
  existing proxy, with no direct DNS allowance. Installed-worker checks passed; a public probe
  returned three valid results and extracted a nonempty page. Remote scraper DNS/redirects remain
  a provider dependency. Rollback backups now include worker runtime overlays.
  The final full deployment verifier passed after the DNS correction and updating the obsolete
  unreviewed-read assertion. The new owner read-button interaction remains unobserved; runtime
  callback/identity tests are evidence of implementation behavior, not a claimed owner click.
- Expanded cron execution fingerprints deployed with private policy migration. All 18 permission/
  migration tests passed locally and in the installed runtime. Mocked live-policy checks verified
  all five definitions, three unchanged grants, two disabled jobs and rejection of added schedule,
  context, monitor, base-URL and session-attachment inputs. No jobs were executed for acceptance.
- Natural-language scope confirmation deployed. Owner confirmed both Telegram reviews appeared;
  the exact-action queue records rejection for the synthetic folder test. No Google mutation
  resulted. Scope cancellation/expiry/replay and wrong identity/message cases have automated tests.
- Research inference broker deployed with existing images/containers: no access token reaches
  the public worker. Job-bound fixed inference, streaming limits and killable research subprocesses
  passed 31 installed-worker tests and live end-to-end research acceptance.
- Google execution limits deployed: combined stdout/stderr capped at 256 KiB during reads,
  60-second process-group deadline, no automatic write retry. All 35 tests pass in the installed
  gateway runtime, including oversized output and a descendant holding the output pipe open.
- Firewall-first boot gating installed. Docker policies are `on-failure:5`; systemd starts the
  four containers only after the firewall unit. Real VPS reboot and full read-only/runtime
  acceptance passed. Continuous probes during transactional replacement: 50 attempts, zero
  connections. This sample is not a formal proof of zero update gaps.
- Encrypted off-host Drive backup uploaded, downloaded and checksum-verified. Offline Mac
  recovery authenticated/decrypted and checked 26 selected artifacts and 14 SQLite databases;
  synthetic pending/executing approvals became expired/unknown. No restored service was started.
  Recovery key stays on the Mac; backups are manual with no automatic deletion by owner choice.
  This is a data recovery rehearsal, not a complete replacement-host/image restore. The snapshot
  predates later boot/task/broker updates; apply current security code before enabling writers.

## Task permissions

Schema-exposure follow-up: deployed the schema-only `model_tools.py` overlay update after
verifying installed hashes and taking a backup. The gateway was stopped before replacing its
mounted source and recreated using the existing image. Direct connector schemas replace deferred
discovery; helper permissions were not broadened. All task modes passed installed-runtime schema
checks before and after activation, including repeated cached lookups. Post-cutover live Gmail
read and prohibited-effect checks passed. Local suites: 11 permission tests pass; 30 Google tests
run with two installed-runtime-only tests skipped locally. No external writes were made for this
follow-up. Subsequent owner Telegram tests passed: research called `research` directly and
returned a final answer mentioning IANA; the folder proposal called `google_workspace` directly
and its bound review was rejected. Neither fresh task attempted discovery helpers.

Cron review: only one of the three previously blocked agent jobs was active; two were completed
and disabled. The active future reminder now has a frozen tool-free `chat` grant. No schedule or
destination changed, no reminder was executed for testing, and completed jobs were not enabled.
An actual-policy mocked runner verified no Google, research, browser, shell, memory, messaging
or cron tools, rejection of a changed prompt and context cleanup. Fourteen local permission/
reminder tests passed. The two fixed-script grants are unchanged.

Backup verification: the latest private rollback backup passed readability, ten overlay digest/
syntax checks and three SQLite integrity checks. The separate encrypted off-host backup and
offline recovery evidence are above and in [backup/README.md](../backup/README.md).

Initial task enforcement is deployed through ten pinned-source read-only overlays plus a
read-only policy module and private cron policy. Existing images, four containers and memory
ceilings are unchanged. Backups were created before activation; subsequent offline data recovery
was exercised as described above.

- Installed runtime: all 10 permission tests and 30 Google/approval tests pass; external writes
  mocked. Overlay hashes, compilation, actual registry checks and agent initialization passed.
- Live: Gmail labels read succeeds with email-read; email-read/web-read deny sending, memory,
  cron, shell, browser fill/click. Web-read cannot read Gmail; no grant cannot read Gmail.
- Full post-cutover deployment verification passed, including sandbox/worker network denials,
  credential guards, report-only email-watch and end-to-end public research with a web-read grant.
  Browser form tests were replaced by denied-action checks because interaction is disabled.
- Approval handler wired without factory failure. Gateway used approximately 219 MiB after
  startup (an observation, not a peak-load benchmark).
- Two reviewed fixed cron scripts and one tool-free reminder remain permitted; two completed
  reminders remain disabled. Browser interaction and history/memory injection are disabled.
- Owner Telegram write-mode acceptance passed: the owner reported receiving the exact folder
  review and approving it. Read-only inspection of the approval database confirmed `succeeded`,
  a bound review message and matching `drive.create-folder` task grant. Remote Drive read-back
  was not repeated for this new test. Owner rejection/public-mode checks subsequently passed;
  earlier interactive browser acceptance does not mean current tasks can use the browser.
- Repeatable owner/operator checks are in [task-permissions/SMOKE-TESTS.md](../task-permissions/SMOKE-TESTS.md).

## Previous security cutover evidence

Status: security increment deployed; real owner self-test approval/rejection and an exact-action
Drive folder creation are verified. The folder action is recorded succeeded with a valid digest
and bound review message; a read-only Drive search found exactly one matching folder. Four
containers remain. Existing images and memory ceilings were retained;
no build, extra daemon or container was added. Hermes revision:
`77915e344cb0cd8e20661d4a7b393f987a2eef32`. Installed Telegram adapter, session-context and
plugin-SDK fingerprints match the inspected pinned source.

## Verified this cutover

- Local suites: Google/approvals 27 (25 pass, two real-Hermes tests skipped locally), deployment
  15, email-watch 30, browser 9, research 24. All 27 Google/approval tests subsequently pass
  inside the installed runtime, including real Hermes ContextVars/SDK and Telegram dependencies.
  External writes were mocked. Diff and sensitive-information scans pass.
- Running gateway log confirms the native Telegram handler was wired without a factory failure.
  Private policy and approval database initialize. Configured owner matches the runtime allowlist;
  no wildcard or allow-all flag was found in the inspected environment. This is not an exhaustive
  alternate-authentication-path audit.
- A dedicated approval forum topic was deployed separately from email-watch delivery. A live
  synthetic ContextVar check confirms that the authenticated owner may propose from another topic
  in the same forum, while the stored callback authority points to the approval topic. The gateway
  was restarted, the handler rewired successfully and a real-registry Google read still passes.
- Tests cover wrong sender/chat/topic/message, bot sender, revoked auth, forgery, content tampering,
  duplicate/concurrent confirmation, reject, expiry, legacy queue rejection, restart invalidation,
  failed delivery, execution failure/timeout, no environment identity fallback and callback
  propagation stopping. Gmail reply targets/headers freeze before review; header injection fails.
- Gateway discovers Google, browser and research tools. Forged approval flags do not execute
  mutations. Google labels read succeeds. Live scope metadata includes drive.file, not full Drive;
  grants were not changed and no re-authorization was performed.
- Email-watch remains no_agent at its existing schedule/destination. Report-only code is installed;
  timezone updates are disabled and owner context is unchanged by the tested update function.
  A complete new-mail classification/delivery run was not forced.
- Actual sandbox personal-data mounts are removed; code mounts are read-only. Sandbox was
  recreated, preserving named host-key storage. Real Hermes execution uses SSH; credential files
  are absent through that path. Read/sync guards reject Google credentials, auth.json and .env.
  No privileged containers or Docker socket mounts were found.
- Transactional firewall installation succeeded. Sandbox/worker direct traffic to private, host
  and public targets is blocked. Proxy rejects loopback, metadata, gateway, host public address
  and a hostname resolving to loopback. Sandbox model-endpoint CONNECT remains available;
  general-web/Google/metadata requests are denied. Worker public HTTPS succeeds.
- Worker refuses callers without an mTLS certificate. Browser open/snapshot/click/back/fill/close
  succeed on public fixtures; no form submission. Foreign session closure and metadata redirects
  are refused. Research is refused while a browser owns the worker, then succeeds end-to-end
  on the public example.com/IANA fixture (1160 returned characters).
- Firewall persistence service is enabled; inspected sandbox networks have IPv6 disabled.
  Root-only configuration/image rollback references and online shared/security SQLite snapshots
  were created before replacement. No database deletion or image/cache pruning was performed.

## Resource samples

Point-in-time Docker samples, not comparable warm-load benchmarks or peak measurements.
The post-cutover gateway has recently restarted.

| Container | Before cutover | After acceptance | RAM ceiling |
|---|---:|---:|---:|
| Gateway | 587.9 MiB | 208.9 MiB | 1024 MiB |
| Sandbox | 16.84 MiB | 4.14 MiB | 512 MiB |
| Research/browser | 136.3 MiB | 144.3 MiB | 1280 MiB |
| Proxy | 11.74 MiB | 11.74 MiB | 128 MiB |

## Owner acceptance and remaining limits

The owner completed both `/alfie_approval_test` outcomes; neither calls Google. The subsequent
folder proposal exposed a tool-dispatch signature mismatch before any approval was created.
Previous tests verified helper calls/registration but missed the real argument-envelope contract.
A dispatcher adapter and malformed-envelope regressions were added; the installed Hermes registry
now dispatches the synthetic folder proposal successfully with external writes mocked.
Google/approval coverage is now 29 tests, with two runtime-only checks skipped locally.
A synthetic Drive-folder mutation was subsequently approved and verified end to end.
No real Google mutation, Telegram message, email or purchase was sent by these automated tests.

Deferred: full replacement-host recovery. Not completed: historical sandbox-cache forensic audit,
provider-specific proof of uncertain outcomes, atomic provider write preconditions and
restricted personal-record lookup/promotion. Shell, browser interaction, native memory/scheduling
and other privileged tools are denied by task policy; restoring them requires dedicated controls.

Confirmations protect the exposed Google tool path, not gateway process compromise. Gateway
arbitrary code compromise bypasses in-process policy. Research/browser share one compromise boundary,
including the worker TLS key but no model token. Neither a container nor these approval
checks make prompt injection impossible. See [the active plan](../plan-next.md).
