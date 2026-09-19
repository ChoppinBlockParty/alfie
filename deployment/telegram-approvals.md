# Telegram approvals in the existing gateway

Status: Google exact-action approval handler and executor deployed in the existing gateway.
The latest installed-runtime suite has 47 Google tests with external writes mocked. Real owner
self-test approval/rejection, an approved Drive mutation and natural-write exact-action rejection
have been verified. The earlier preliminary write-scope and private-read confirmation cards were
removed in the proportional-confirmation release; private reads pin bounded selectors automatically.
The new layer checks an immutable matching write-mode grant before proposal and before execution;
read tasks cannot propose writes. Task grants expire after 30 minutes. Owner end-to-end acceptance
of the new write-mode layer passed: the owner received/approved the folder review and the
queue records success with its task grant. Remaining smoke checks are documented in
`task-permissions/SMOKE-TESTS.md`.
No SSH approval command or second poller was added.

Implemented: owner/chat/topic/session/source-message binding from ContextVars (no environment
identity fallback), exact review-message binding, full ASCII JSON reviews, single-use transactions,
expiry, restart invalidation, immutable Gmail reply targets, rejection and unknown outcomes.
Oversized reviews are rejected instead of paginated. Legacy requests cannot execute. Private
policy uses `ALFIE_OWNER_TELEGRAM_USER_ID` plus `ALFIE_APPROVAL_CHAT_ID/THREAD_ID` in ignored `.env.local`
and is mounted read-only with the gateway plugin; it is not model-editable configuration. Owner
requests may originate in any topic of the same forum, while review delivery and callback authority
remain restricted to the dedicated approval topic. Email-watch retains its separate destination.

Also deployed: bounded query/result-ID reads, target-name and prior Sheets-value context,
pre-execution metadata comparison, subprocess limits and read-only reconciliation tooling.
Useful natural-language routing and specific clarification are deployed.
Remaining contract work: atomic provider preconditions, direct
email-observation promotion and isolation from arbitrary gateway code compromise. Difficult
recovery tests remain deferred by owner direction, not delivery blockers.
The sections below remain the target security contract, not a claim that all requirements are met.

## Integration points to inspect

Read the installed Hermes Telegram transport, sender authorization, callback dispatch, plugin
registration, tool invocation context, cron delivery and session handling. Use the existing
poller; never run a second getUpdates consumer. Inventory every credentialed native tool and
all alternate routes (cron, integrations, Google scripts, memory, execution backend). Disable
unmediated writes. Keep shell execution in the SSH container.

The integration should be a small deterministic handler in the existing gateway process, with
SQLite state and no extra container, daemon or model call. Preserve existing memory ceilings;
measure RSS and latency before/after. This does not isolate a compromised gateway process.

## Review and execution protocol

1. A tool only proposes an action. Persist canonical operation/arguments under a random ID,
   then bind the request to authenticated owner, conversation, task and intended destination
   from transport context. Never accept these bindings as model-provided arguments.
2. The trusted handler retrieves and validates the proposal. Resolve dynamic targets before
   showing it: gmail.reply must resolve the actual recipient/thread/subject; document/calendar
   IDs need resource details. Freeze the final action before computing its review digest.
3. Send a deterministic review message to the configured owner destination. Show exact To/Cc,
   subject/body or exact resource/diff/date/timezone. Escape markup and controls, prevent
   untrusted text from creating buttons, suppress link previews, and paginate long content.
   Do not silently approve unseen truncation. Message content remains private operator data.
4. Confirm/Reject buttons refer to an opaque, expiring challenge held in private state. The
   handler validates the real Telegram sender, chat, bound message, request and challenge;
   reject replayed updates, forwarded text, bot senders, mismatched sessions and arbitrary
   callback payloads. The model cannot call this handler as a tool or mint an approval.
5. In one transaction, consume the challenge and move the approved immutable snapshot to
   executing. Recheck expiry, digest, resource scope and policy immediately before the call.
   Modified content/target requires a new review. The tool's pending ID/digest is not authority.
6. Invoke only a fixed operation using the approved snapshot. No shell command, arbitrary URL
   or credential-return primitive. Enforce input/output/process limits and redact errors.
7. Record succeeded/failed/unknown outcomes. A timeout with possible remote acceptance stays
   unknown until reconciled; never automatically resend. Report actual outcome to the owner.

Migrate the current queue's pending-only schema explicitly; do not infer approval from existing
rows. Existing requests have no authenticated task binding and must be re-proposed through the
new handler before execution. Expired requests remain invalid. On backup restore invalidate all
unconsumed challenges and reconcile actions that were executing.

## Task and data boundaries

Approval of writes alone does not prevent disclosure through private reads plus public browsing.
Attach an owner-selected task mode to trusted runtime context, and enforce it in every Google,
browser, research, records and shell handler. A missing task context fails closed. A model may
propose changing modes but cannot grant itself the new mode.

- Public tasks get only a public brief, with no mailbox, private memory or records context.
- Private tasks get bounded selected resources, no public web/search/form/DNS output path, and
  replies only to the authenticated owner. Preserve the configured inference-provider policy.
- Private-to-public export needs review of exact content and destination before a fresh task.
- Owner preferences and scheduler policy cannot be changed by email-derived observations.
- Email observations require separate review before promotion to facts or calendar actions.
  A suspicious=false classifier result is not approval. Preserve sources and quarantine flags.

Task IDs must originate from the runtime; random IDs supplied by the model are not authentication.
Avoid a global mutable current-task flag: overlapping cron/chat requests must not share authority.
Native memory and messaging tools also need destination/resource enforcement. Keeping all code
in one gateway retains a process-compromise risk even after these model-facing checks work.

## Release tests

Use fake Telegram updates and mocked Google mutations first. Cover wrong sender/chat/message,
expired/forged challenge, edited action, duplicate update, simultaneous confirmations, callback
after restart, stored-body tampering, changed reply recipient, failure/timeout and unknown result.
Verify no private body/token appears in logs. Test the actual registered Hermes tool/transport
path, not just helper functions. No real message or Google write is needed for these tests.

Then run controlled live owner-approved acceptance: review, reject, confirm an exact synthetic
action, verify the result, and measure resources. Production data changes still require their
specific approval. Update deployment acceptance only after the integrated version is running.
