# Google Workspace gateway operations

UC2/UC5. Telegram approval integration deployed on 2026-09-19. This plugin runs in the existing Hermes gateway;
no separate email container or background process.
`google_workspace(operation, arguments)` validates a fixed operation/argument map and invokes
an immutable Google CLI with an argument vector, no shell, a restricted environment and a
60-second timeout. Unknown operations/arguments and positional option injection fail closed.
No local file upload/download, arbitrary URL or credential-return operation is exposed.
Model tool calls execute reads or propose writes. Only the trusted Telegram callback can execute a write.

## Private reads

Natural-language private lookups route directly from a fresh authenticated owner task. The first
read automatically pins its exact selector and 20-result maximum; this read-only path has no
separate confirmation. It can return data only to the owner and cannot propose a write or public
export. The task cannot ask for a second selector after receiving private content.
`read_scope.py` binds arguments to the immutable task identity. Gmail/Drive searches
permit subsequent gets only for IDs in the bounded result set. Direct-ID, calendar, contacts,
Docs and Sheets reads pin all arguments. Exact repeated reads return cached results. A failed
read is not retried automatically. Limits: 32 retained task scopes, 256 KiB aggregate cached
output per task, 20 search/list results and a 30-minute grant lifetime. This protects tool access,
not arbitrary code inside the credentialed gateway. Existing fixed no-agent scripts remain
under their separately reviewed standing policies.

## Pending writes

The private gateway database `/opt/data/security/pending-actions.sqlite` holds at most 100
requests. Storage accepts at most 128 KiB per action; Telegram applies the stricter 3000-character
complete-review limit. Files are mode 0600 in a private directory. Requests expire after 24 hours
and are purged when new requests arrive, except unknown/executing records retained for
reconciliation. The digest is content comparison, not authorization.

The handler uses the existing Hermes poller and its pinned ContextVars. Private read-only policy
binds the owner and forum; transport supplies the originating topic, session and message. An owner
request may originate in any topic of that forum. Reviews are sent to, and callbacks accepted only
in, the dedicated approval topic configured separately from email-watch delivery. Reviews
show complete ASCII-escaped action JSON and target context without markup/link previews. Actions exceeding 3000 combined review
characters fail closed; they are not truncated. Gmail replies resolve and freeze To, subject,
thread and Message-ID before review. Caller-supplied approval flags have no authority.

Buttons are bound to the sent review message and authenticated owner; a transaction consumes
each random request once. Reject makes no change. Errors/timeouts after consumption stay unknown
and are never automatically retried. Restart invalidates outstanding buttons and marks interrupted
executions unknown. Legacy pending-only requests cannot execute. Unknown records remain retained
for reconciliation and count toward the 100-row limit. New requests do not deduplicate across reviews.
No queued action should be reported as performed. `/alfie_approval_test` creates a harmless review
that calls no Google API. Real owner approval and rejection clicks have both been verified.
A real owner-approved Drive folder creation passed before the task-mode release. Owner
approval of a new task-mode folder review is now confirmed by a succeeded queue record;
remote read-back of that new test was not repeated. Automated approval tests pass.

Hermes invokes registered tools with one argument dictionary. `tool_handler` validates and
unpacks that envelope before calling `google_workspace`; runtime kwargs grant no authority.
Regression tests exercise actual registry dispatch, not just helper calls or registration.

All gateway code still shares its trust boundary and credentials. This change is enforcement
in the exposed plugin, not isolation against gateway code compromise or other credentialed
tools. Mandatory task checks restrict private reads by service/operation plus a pinned initial
selector and returned resource IDs. Only a matching write mode may propose an action; its immutable
grant is checked again before approval consumption and execution. Task grants expire after
30 minutes, earlier than queue retention. Read modes cannot create write approval requests.

The CLI is vendored from the VPS's existing patched upstream skill (Hermes revision
77915e344cb0cd8e20661d4a7b393f987a2eef32, Nous Research MIT). It preserves recursive Gmail MIME
handling and attachment names. Original source provenance is retained here; no token files
are in this subsystem. The operation inventory is in SKILL.md and gateway-plugin/__init__.py.

Google credentials remain `/opt/data/google_token.json` and `google_client_secret.json` in the
gateway. Live scope metadata was verified: Drive is drive.file, plus Gmail read/modify/send,
Calendar and Contacts read. Grants are unchanged. Missing scope metadata now fails closed;
the full-Drive fallback was removed. This is not a prompt-injection-proof account boundary.

The plugin never prints subprocess stderr/tracebacks to the agent. Authentication failures
return a generic re-authorization message. `bounded_run` caps combined stdout/stderr at 256 KiB
while reading and kills the POSIX process group after a 60-second deadline or failure. Success
presentation is capped at 24,000 characters and remains untrusted data. These limits do not bound
every allocation inside Google's SDK; existing container resource ceilings remain the last limit.
Do not automatically retry writes after a timeout or output-limit failure: the provider may
already have applied them.

Natural-language supported writes first require **Confirm task scope** in the approvals topic.
This only grants permission to propose that operation; the subsequent **Approve exact action**
review remains mandatory. Scope reviews expire after three minutes or restart; read modes never
upgrade to writes from tool output. Explicit operation prefixes bypass the scope prompt, not
the exact-action review. See the task-permission smoke tests for safe rejection checks.

## Target reviews and uncertain outcomes

`scripts/review_context.py` performs fixed, target-only metadata reads for reviews. Existing
Drive/Docs/Sheets targets show ID, name, type, version and available sharing/parent metadata;
Calendar deletion shows the selected event and calendar; Gmail label changes show message
headers and label names. Sheets updates include prior values in the exact bounded range.
Metadata remains untrusted and never becomes model instructions. Unresolvable, trashed, wrong-type
or oversized targets fail closed. The stored context is re-read and compared before execution.
This is a precondition check, not an atomic provider transaction: concurrent changes after the
check remain possible. Sharing information is advisory, not a complete access-control audit.

Sheets use literal `RAW` values in both CLI backends, never `USER_ENTERED` formulas. Nested
values must be at most 50 rows, 20 columns and 200 cells, with bounded scalar values; explicit
A1 ranges are also bounded and updates cannot extend beyond reviewed dimensions. Appends still
use Google's table-end placement and the review says so. Recipients must be valid explicit
addresses (at most 20 per recipient field). Drive search escapes its text literal.
Provider semantics: [Sheets value input](https://developers.google.com/workspace/sheets/api/reference/rest/v4/ValueInputOption),
[Drive metadata](https://developers.google.com/workspace/drive/api/reference/rest/v3/files),
[Calendar event lookup](https://developers.google.com/workspace/calendar/api/v3/reference/events/get).

`reconcile.py --request-id REQUEST_ID` is operator-only and must run in the gateway with private
output handling. It opens approval state read-only, verifies the action digest and reports the
reviewed/current exact target context where available. It never retries, changes queue status or
claims a matching current state proves this request executed. Send/create operations still need
manual inspection of the exact destination; missing resources are not proof of non-execution.

## Deployment boundary

`deploy.sh` stages code. `../deployment/deploy.sh` activates read-only plugin and script mounts,
replaces the old Google skill with gateway-tool instructions, removes Google credential mounts
from the sandbox, clears terminal credential forwarding, and patches the gateway's read/sync
guard to refuse Google credential filenames. Recreating the sandbox clears previously synced
files; removing a mount alone does not. Verify again after any upstream image upgrade.

`email-watch` continues running in the gateway and imports the same protected CLI module at
its existing path. Coordinated deployment now stages its report-only implementation while
preserving its schedule. Operator OAuth
setup is outside the agent tool; it must not copy credentials into the command sandbox.
The read-scope release uses `deployment/activate_read_scopes.py`: stage off live mounts, validate,
back up, stop the gateway/worker, replace code and its reviewed cron dependency hash, then recreate
the two existing containers. Do not use generic staging scripts to overwrite active code mounts.

Tests: `python3 -m unittest discover -s google-workspace -p 'test_*.py'`.
Acceptance: actual tool registration, read-only Gmail labels call reporting status/count only,
credential read/sync rejection and clean sandbox through the Hermes environment path.
