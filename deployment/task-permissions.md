# Task permissions contract

Status: effect-oriented redesign deployed on 2026-09-20. Initial enforcement was deployed on
2026-09-19. Implementation: [task-permissions](../task-permissions/README.md).

Usability requirement: ordinary owner language must work without prefix memorization. Chat and
read-only work require no approval. Security decisions follow effects and data destinations, not
how many Google products a read happens to use.

The simplified catalogue has two external read boundaries: `private-read` for all fixed Google
reads, and `web-read` for the isolated public worker. They never coexist in one task. A bounded
tool-free model chooses the boundary from only the current authenticated owner text; uncertainty
falls back to tool-free chat. Every Google mutation still requires one immutable exact-action
Telegram review. Memory is additive only, reminder cancellation is recoverable pause, and unknown
tools, shell, delegation, general cron and arbitrary messaging remain disabled.
The one pre-existing active reminder retains an operator-reviewed tool-free grant; two completed
reminders remain disabled. Two reviewed fixed scripts remain permitted. Private reads are bounded
to eight selectors and 256 KiB in a no-egress task. Private exports and broader attachment handling
are not implemented. The shared credentialed
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

Classification proposes a bounded category. Deterministic policy validates it against source
authority and a fixed catalogue. The classifier cannot invent capability names, destinations or
approval rights. Uncertainty receives only chat, never an external capability. Do not use keyword
matches or model confidence alone to authorize account mutations.
Classification is fallible and does not replace the existing exact-action approval requirement.

Separate four dimensions: data readable, actions permitted, destinations permitted, and durable
state writable. Private Google services may be read together because the task has no destination
except the authenticated owner; public browsing, persistence and mutations stay unavailable.

| Original task | Permitted scope | Excluded scope |
|---|---|---|
| Find something in my emails and calendar | Up to eight bounded selectors across fixed Google reads; answer to owner | Any account mutation, public web, durable memory changes |
| Find something on the internet | Public brief, public search/page reads, answer to owner | Private reads/history, email or other account writes, memory changes, form submission, cron changes |
| Draft a reply | Selected email context and draft displayed to owner | Sending, send approval requests, public export |
| Send/reply or change an account item | Bounded private reads to identify the target, then one matching exact-action review | Execution without approval, a second mutation, public web or persistence |
| Scheduled email digest | Reviewed bounded mail reads/extraction, private processing ledger, fixed owner delivery | Send/reply, Calendar changes, personal memory/policy changes, public web |

## Dangerous effects and enforced outcome

| Dangerous case | Policy outcome |
|---|---|
| A web page asks for memories, mail, calendar, contacts, documents or prior private answers | Denied: `web-read` has no memory snapshot or Google tool. |
| An email, document, image or tool result asks Alfie to send, publish, persist or delete data | It is untrusted data and cannot change the task grant. Read modes cannot create write reviews; an owner-requested write task can only propose its one matching effect for review. |
| One request asks to combine private Google data with public search/browsing | Rejected as mixed. The owner must separate the tasks; no private-derived brief enters the public worker. |
| Sending or replying to email, including private content | The complete recipient, headers and body are frozen and shown in an authenticated Telegram review; rejection, expiry or mismatch makes no change. |
| Calendar deletion, Gmail label changes, Sheet replacement/appending, Doc append, or other exposed Google mutation | One task may propose one exact action. It executes once only after its complete target/effect review; changed targets and replay are denied. |
| Deleting or replacing persistent Alfie memory | Not exposed to the assistant. `memory-write` can add one bounded fact from the current owner message and receives no old-memory snapshot. |
| Deleting a reminder | Not exposed. “Cancel” pauses the selected owner-only reminder, so it can be resumed. |
| A retrieved item attempts to poison durable memory | Denied: private/public read modes have no memory tool; memory-add tasks contain no retrieved data or existing memory snapshot. |
| Browser login, payment, upload/download, personal-data form entry or arbitrary script execution | Denied by task policy and the isolated browser/worker contract. |
| A forged tool call, approval flag, task ID, callback, expired grant or changed cron definition | Denied by deterministic checks outside the model. |
| Replying to the authenticated owner with private data they requested | Allowed. Telegram owner delivery is the intended private destination. |

The configured model provider necessarily processes classifier input and the selected task's model
input/results. The credentialed gateway, Telegram account, operator host and provider remain trust
boundaries; these controls address model/tool misuse and prompt injection, not compromise of those
trusted systems.

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
