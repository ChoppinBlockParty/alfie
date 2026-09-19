# Task permissions

Mandatory source patches for Hermes revision 77915e344cb0cd8e20661d4a7b393f987a2eef32.
Initial enforcement deployed on 2026-09-19; evidence is in deployment/acceptance.md.
No new service or container.

P0 usability defect: the deployed keyword classifier still rejects ordinary owner wording.
The next release replaces that narrow fallback with validated, tool-free intent proposals and
specific clarifications. Prefixes remain optional diagnostics, not the intended normal UI.
Useful routine chat/lookups and fewer unnecessary prompts are explicit owner requirements;
account-write approvals and private/public separation remain mandatory.

The trusted gateway creates an immutable ContextVar grant from authenticated owner text before
native command or agent dispatch. Unknown sources, internal notifications, media and unclassified
requests fail closed. Automatic classification recognizes only unambiguous email/web read tasks;
it cannot authorize writes. An explicit leading `mode: request` selects a fixed catalogue entry.
Supported natural-language write requests instead propose a mode in the approvals topic. The
authenticated owner must choose **Confirm task scope** before the agent receives that mode.
This is not action approval: a separate frozen exact-action review is still mandatory. Suggestions
come only from the original authenticated text, never retrieved content. Scope reviews expire
after three minutes or restart, are message-bound and single-use, and allow four pending requests.
Unrecognized requests remain denied; explicit prefixes remain available for precise testing.

Modes: email-read, calendar-read, drive-read, contacts-read, sheets-read, docs-read, web-read, chat;
or one exact supported write operation, for example `gmail.send: ...` or `calendar.create: ...`.
Write modes permit that operation's approval proposal, not automatic execution. Reply mode
resolves only the selected reply target before creating an immutable send review.

Grants last 30 minutes with at most 32 registered tool calls. Modes do not carry into a later
request. Every agent task uses a fresh brief, empty conversation history, no context files or
memory injection, no background memory review and only its permitted toolsets. Native tool calls
are checked before middleware and again at registry dispatch; custom Google/research connectors
also check authority. Denied tools include shell, delegation, memory, skills, scheduling and
messaging. Operational transcripts/bookkeeping still persist in the protected gateway.

`web-read` currently exposes research only. The interactive browser, including open/click/fill,
is disabled for every task mode until destination/content review can be enforced before effects.
Research still sends public queries and reads URLs; HTTP GET alone cannot guarantee a remote
site has no side effects. Public briefs must not contain private material: a deliberate export
approval workflow is not yet provided. Private reads now also require an authenticated **Approve
read scope** review of the original request and exact query/resource arguments. The first selector
is pinned; search results grant only their returned IDs for same-service fetches. Changed queries,
unreturned IDs and new selectors require a new task, not a scope expansion from retrieved content.
Search/list requests allow at most 20 results. Exact repeat calls return task-local cached data;
failed reads are not automatically retried. State is bounded to 32 tasks and 256 KiB per task,
expires with the grant and disappears on restart. Scope rejection cannot be re-proposed within
the same task. Docs/Sheets/direct-ID reads require the exact initial resource/range review too.
This relies on the owner assessing the selector; it is not a semantic proof of query relevance.

Cron execution checks a private frozen job fingerprint before any precheck, script or agent.
The two supported fixed scripts additionally require unchanged source/dependency hashes. Agent
cron jobs require a recognized read/chat classification of their frozen prompt. At cutover,
three existing agent jobs initially failed classification. Operator review found one active
future reminder and two already completed/disabled reminders. The active reminder now has a
frozen `chat` grant with no tools; the completed jobs remain disabled and ungranted. Two reviewed
fixed scripts remain permitted. Changed definitions or script hashes fail closed until review.
Agent cron jobs cannot obtain interactive private read scopes. Existing reviewed no-agent scripts
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
