# Task permissions

Mandatory source patches for Hermes revision 77915e344cb0cd8e20661d4a7b393f987a2eef32.
Initial enforcement deployed on 2026-09-19; natural-language/use-case release deployed on
2026-09-20. Evidence is in deployment/acceptance.md.
No new service or container.

The policy is effect-oriented: it automatically permits conversation and bounded reads, while
blocking private-to-public data flow and requiring exact owner review for account changes.
Prefixes remain optional diagnostics, not the normal UI. Routine chat, private Google reads,
public browsing, additive local memory and recoverable reminders work from ordinary language.

The trusted gateway creates an immutable ContextVar grant from authenticated owner text before
native command or agent dispatch. Unknown sources, internal notifications and unclassified
requests fail closed. The classifier receives only the bounded current owner text and fixed
catalogue through the configured provider, with no tools, history, memory or retrieved data.
Its strict one-key JSON proposal is validated outside the model, and the original owner text—not
model output—becomes the task brief. It may select a write mode but cannot approve or execute a
write. A separate frozen exact-action review remains mandatory. Mixed private/public work and
unsupported effects are refused with specific guidance. An uncertain proposal falls back to
tool-free chat, where Alfie can answer from owner-only local memory or ask a specific follow-up
without acquiring Google, web or account-change access. Explicit prefixes remain available for testing.

Normal modes are `chat`, `private-read`, `web-read`, `memory-write`, `reminder-read` and
`reminder-write`; or one exact supported Google write,
for example `gmail.send: ...` or `calendar.create: ...`.
Write modes permit bounded private reads to identify the requested target and one proposal for
that operation, never automatic execution. Reply mode resolves and freezes the selected reply
target before creating an immutable send review.
The older service-specific private-read prefixes remain compatible diagnostics.

Grants last 30 minutes with at most 32 registered tool calls. Modes do not carry into a later
request. Every agent task uses a fresh brief, empty conversation history, no project context files,
no background memory review and only its permitted toolsets. Local memory is injected only into
tool-free chat; it never enters public, Google or memory-write tasks. Native tool calls
are checked before middleware and again at registry dispatch; custom Google/research connectors
also check authority. Shell, delegation, skills, general cron administration and arbitrary
messaging remain denied. Operational transcripts/bookkeeping still persist in the protected gateway.

`web-read` exposes research and the disposable public browser. The browser has no private context,
credentials, login, payment, downloads or personal-data fields; its public profile is destroyed
after the bounded session. Page text remains untrusted. Public briefs must not contain private
material because no export approval workflow exists. `private-read` exposes every fixed Google
read operation but no public, persistence or mutation tool. One task may use at most eight distinct
selectors across Gmail, Calendar, Drive, Contacts, Sheets and Docs; search/list calls return at
most 20 results and total output is limited to 256 KiB. Exact repeats are cached and failed reads
are not retried. This accepts that untrusted private content may influence later private reads,
because the result still has no destination other than the authenticated owner. It cannot reach
the public worker or create a write review.

`memory-write` can add one bounded fact to local MEMORY.md or USER.md. It receives no existing
memory snapshot and cannot replace, batch-edit or remove entries. `reminder-read` and
`reminder-write` expose a dedicated connector,
not general cron. New reminders have a fixed `chat` prompt marker, owner-origin delivery and no
scripts, monitors, skills, context chaining, work directory, alternate destination or toolsets.
Cancellation pauses a reminder so it remains recoverable; permanent removal is not exposed.
Their complete shape is revalidated at every fire. Photographs are forced to chat mode regardless
of caption and media/OCR instructions are marked untrusted. Authenticated voice notes are
transcribed once before classification. Other attachment types remain blocked. Media decoding,
STT/vision availability and real-fixture acceptance are owned by the separate `media/` subsystem;
this policy consumes only its transcript or image-task marker.

## Dangerous effects and their handling

The policy treats danger as an effect or data-flow property, not as a topic keyword:

| Case | Handling |
|---|---|
| Send private data to a website, public browser, email recipient or other external destination | Deny. There is no private-export mode. Split public research from private lookup without copying private results across. |
| Send/reply email or change Google data | Permit target lookup in the private task, then require one immutable exact-action Telegram review. The model cannot approve it. |
| Delete email, files, events, contacts, sheets, documents, memories or records | Not exposed. No generic delete capability exists. |
| Persist or alter personal memory | Permit one bounded additive fact only. Reading old memory, replacement, batch edits and removal are unavailable in that task. |
| Create or cancel reminders | Use the narrow owner-only reminder connector. Cancellation pauses; permanent deletion, scripts, alternate delivery, tools and chained context are denied. |
| Run shell/code, delegate, administer cron/configuration, install software or invoke arbitrary messaging | Deny from Telegram tasks. These remain operator actions outside the assistant permission catalogue. |
| Reveal credentials, tokens, private files or hidden instructions | Deny by tool surface and credential guards; such data is never a valid task payload or destination. |
| Combine private account data with public research/browsing | Deny and ask the owner to split the requests. Public workers receive no private memory or Google context. |
| Instructions found in email, webpages, documents, audio, images or forwarded messages | Treat as untrusted data. They cannot grant modes, approve effects or change destinations. Forwarded messages cannot start permissioned tasks. |
| Unauthenticated, wrong-chat, bot, internal or missing-message requests | Deny before classification or tool dispatch. |
| Unsupported attachments | Reject before an agent task starts. A failed native transcription or vision analysis continues as a tool-free media task and reports that the content could not be analyzed; failure never becomes authorization. |
| Login, payment, credential entry or authenticated checkout | Not supported. Public browsing remains logged out and cannot receive personal/payment fields. |

Cron execution checks a private frozen job fingerprint before any precheck, script or agent.
The two supported fixed scripts additionally require unchanged source/dependency hashes. Agent
cron jobs require a recognized read/chat classification of their frozen prompt. At cutover,
three existing agent jobs initially failed classification. Operator review found one active
future reminder and two already completed/disabled reminders. The active reminder now has a
frozen `chat` grant with no tools; the completed jobs remain disabled and ungranted. Two reviewed
fixed scripts remain permitted. Changed definitions or script hashes fail closed until review.
Agent cron jobs cannot obtain interactive private reads. Existing reviewed no-agent scripts
retain their separate standing policy and the tool-free reminder is unaffected.
Fingerprints also bind schedule/repeat limits, enabled state, context sources, monitor hooks,
model/provider snapshots, base URL, reasoning and session attachment. Mutable run counters and
claims are excluded; completed/paused/disabled jobs are denied independently. The version-2
operator migration preserves existing grants and rejects changed definitions or extra inputs.
`review_reminder.py` renders a private policy update for an explicitly selected inspected job;
it never edits schedules or runs jobs. Stage its output privately, back up, stop the gateway
before replacing the read-only policy file, then recreate and verify. Rebuilding policy from
scratch does not automatically preserve these manual grants: repeat the operator review.
Task policy/configuration changes remain operator-managed. Unsupported transports cannot execute
tools or construct a permissioned agent. Explicit mode prefixes are not accepted from tool output.

`patch_runtime.py` generates read-only overlay files and baseline/patched SHA-256 manifests;
never apply to a different source version or patch an already patched file in place. Patches
enforce at gateway entry, model tool routing, registry dispatch, agent initialization, prompt
construction, conversation entry, cache reuse and cron entry. Middleware alone is insufficient:
the pinned upstream middleware continues execution after a callback exception.

Tool schemas are exposed directly, without Hermes's deferred discovery bridge. Each task has
at most one connector, so discovery adds no useful scope reduction and its helper calls remain
denied. The Google schema describes the connector's full operation catalogue; mandatory dispatch
checks, not schema descriptions, enforce the task's narrower operations. `verify_tool_surface.py`
checks actual installed schemas for every mode and repeated cached lookups without external calls.
`activate_tool_surface.py` is the one-time schema-only maintenance cutover: it verifies the
previous overlay hashes, backs up, stops the gateway before replacement, and recreates it.

Tests: `python3 -m unittest discover -s task-permissions -p 'test_*.py'`.
Owner-facing examples, expected denials, safe rejection tests and troubleshooting are in
[SMOKE-TESTS.md](SMOKE-TESTS.md). Run them after changes; the real-write check is optional.
Google/approval tests now bind explicit synthetic grants and run without live mutations.
Generate overlays from the inspected pinned checkout using
`python3 task-permissions/patch_runtime.py PINNED_SOURCE .private/task-permissions-runtime`.
`deploy.sh` is initial activation only and refuses replacement of an existing overlay release.
Subsequent upgrades require a reviewed maintenance cutover with backup, regenerated/validated
overlays and cron hashes, and runtime acceptance. Never overwrite mounted policy files live.
`live_acceptance.py` runs inside the gateway and checks denied effects and private reads without
owner scope. It does not send mail or modify Google resources. `deployment/verify.py` separately
performs an explicit operator-only Gmail labels health read, not a permissioned model read.
The same gateway process still owns credentials and enforcement; arbitrary code compromise
inside it defeats these checks. The controls address tool misuse induced by untrusted content.
