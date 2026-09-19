# Task permissions contract

Status: initial enforcement deployed on 2026-09-19 using existing containers.
Implementation: [task-permissions](../task-permissions/README.md). The contract below remains
the target; not every planned capability is available yet.

Usability requirement (P0): ordinary owner language must work without prefix memorization.
Replace the brittle classifier, not the authorization boundary. Minimize unnecessary confirmation
friction while keeping selected-data limits, private/public separation and exact-action write review.

Implemented: authenticated owner-text classification, immutable expiring grants, mandatory
tool checks, fresh task context, Google approval scope checks and frozen cron fingerprints.
Supported natural-language writes now require owner confirmation of the proposed task scope
before granting tools, followed by a separate exact-action review. The owner two-review/rejection
test passed. Explicit operation prefixes remain supported. Read tasks never use this upgrade path.
Read tasks cannot propose writes. Browser interaction, memory changes, shell and delegation
are disabled. Unknown requests/sources fail closed. The one active reminder now has an
operator-reviewed tool-free grant; two completed reminders remain disabled. Two reviewed fixed
scripts remain permitted. Private reads now pin an owner-reviewed selector and bounded returned
IDs; query expansion requires a new task. Private exports,
browser interaction approvals and media handling are not implemented. The shared credentialed
gateway remains a trust boundary; this is not protection against arbitrary gateway code execution.
Implement inside the existing four containers without an additional service.

Every entry point must establish task permissions before loading private context, exposing tools,
running scripts or invoking an agent. Telegram identity comes from authenticated transport;
cron authority comes from a reviewed job definition. Other sources require their own registered
policy. Missing policy or task context denies tools and side effects.

## Classification and authority

Classify the authenticated owner's current request, or a cron job's approved specification.
Email/web/document content, tool results, stored memories and quoted or forwarded instructions
are data; they cannot establish a new owner request or change permissions. A scheduler firing
does not grant the job all owner privileges. A forum topic selects routing, not permissions.

Classification proposes a bounded category and resource scope. Deterministic policy validates
that proposal against source authority and a fixed catalogue. The classifier must not invent
capability names, destinations or approval rights. Uncertain intent asks the owner to clarify;
failure denies execution. Do not use keyword matches alone to authorize account mutations.
Classification is fallible and does not replace the existing exact-action approval requirement.

Separate four dimensions: data readable, actions permitted, destinations permitted, and durable
state writable. Permission to read one private service does not grant all other private services.

| Original task | Permitted scope | Excluded scope |
|---|---|---|
| Find something in my emails | Bounded Gmail search/get and answer to owner | Send/reply/modify, send approval requests, Calendar/Drive, public web, durable memory changes |
| Find something on the internet | Public brief, public search/page reads, answer to owner | Private reads/history, email or other account writes, memory changes, form submission, cron changes |
| Draft a reply | Selected email context and draft displayed to owner | Sending, send approval requests, unrelated private resources, public export |
| Send an email | Prepare the explicitly requested send for exact-action review | Execution without approval, unrelated writes or extra resources |
| Scheduled email digest | Reviewed bounded mail reads/extraction, private processing ledger, fixed owner delivery | Send/reply, Calendar changes, personal memory/policy changes, public web |

Operational audit records, delivery bookkeeping and temporary browser state are separately
allowlisted runtime effects. They are not permission to add facts/preferences to personal memory.
Data retention remains bounded. Account/tool permissions must not silently include memory writes.

## Task lifetime and approval

Store an immutable runtime grant with task ID, authenticated principal, source, originating
session/message or job/version, category, resources, operations, allowed destinations, expiry,
quotas and policy version. Never accept a task ID or scope supplied by model arguments as authority.
Use per-task context propagated through threads, asynchronous work and delegation. Children inherit
the same or fewer permissions. Concurrent jobs and forum topics must not share mutable authority.

A read-only task cannot propose a write or create an actionable approval card. A new explicit
owner instruction establishes a new task or reviewed scope expansion; retrieved content cannot
initiate that transition. A send-intent grant permits proposing a send; only the dedicated
approval callback authorizes execution of the exact stored action. Recheck both authorities
before execution, including expiry/revocation. A button cannot override missing task authority.

An unrelated next Telegram request starts with fresh permissions, even in the same topic.
Follow-ups may retain the previous scope only while remaining within it. Public work receives a
fresh context without private history, memory injection or private-derived summaries. Exporting
private-derived content requires review of exact content and destination before creating public
work. Switching a mode flag on an already private conversation is insufficient isolation.

Each cron run receives a fresh grant from its reviewed job definition. Arbitrary scripts, changed
code, destinations or expanded scopes require operator review. Existing no_agent scripts need
enforcement at scheduling and their connectors because they bypass model tool dispatch.

## Implementation sequence and evidence

1. Inventory all entry points and effects, including automatic memory extraction, skill/config
   edits, cron management, messaging, direct scripts, worker calls and approval callbacks.
2. Add source adapters, fixed classification catalogue and immutable per-task grants. Bind them
   before agent construction/context loading; fail closed for unsupported entry points.
3. Enforce grants at registry dispatch and connector execution, with separate operation checks
   inside multi-operation tools. Hiding tools in prompts is only an additional restriction.
4. Enforce reviewed grants for script cron jobs and automatic/background memory writers.
5. Enforce grant checks before write proposals and in the Telegram executor; invalidate old
   requests lacking task grants at cutover. Preserve dedicated approval-topic routing.
6. Test entry-to-effect paths with mocked account writes before deployment; then exercise owner
   read tasks and explicitly approved synthetic writes using the existing Telegram workflow.

Pinned Hermes source inspection identified `gateway/run.py::_set_session_env` for transported
context, `tools/registry.py::ToolRegistry.dispatch` for dictionary-envelope tool dispatch, and
`cron/scheduler.py::_run_no_agent_job` for direct script execution. Plugin middleware registration
exists in `hermes_cli/plugins.py`, but its coverage and failure behavior still need review before
using it as enforcement. These findings do not claim a complete bypass audit.

Required tests: email search containing instructions to send mail; internet result requesting
memory/cron writes; forged classifier capabilities; ambiguous requests; absent context; unknown
entry points; independent concurrent tasks; child-task escalation; cron definition drift;
write proposals from read-only tasks; callbacks without valid task grants; and public tasks after
private conversations. Verify denial occurs before approval-card delivery or external effects.
