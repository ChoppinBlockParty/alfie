# Google Workspace gateway operations

UC2/UC5. This plugin runs in the existing Hermes gateway; no separate email container.
`google_workspace(operation, arguments)` validates a fixed operation/argument map and invokes
an immutable Google CLI with an argument vector, no shell, a restricted environment and a
60-second timeout. Unknown operations/arguments and positional option injection fail closed.
No local file upload/download, arbitrary URL or credential-return operation is exposed.

The CLI is vendored from the VPS's existing patched upstream skill (Hermes revision
77915e344cb0cd8e20661d4a7b393f987a2eef32, Nous Research MIT). It preserves recursive Gmail MIME
handling and attachment names. Original source provenance is retained here; no token files
are in this subsystem. The operation inventory is in SKILL.md and gateway-plugin/__init__.py.

Google credentials remain `/opt/data/google_token.json` and `google_client_secret.json` in the
gateway. The existing granted scopes are unchanged. Gmail send/reply/modify retain their
existing authorization policy. Tool access can misuse account permissions even when token
bytes cannot be read; this is not a prompt-injection-proof account boundary.

The plugin never prints subprocess stderr/tracebacks to the agent. Authentication failures
return a generic re-authorization message. Success output is capped at 24,000 characters and
is untrusted data. Do not automatically retry writes after a timeout.

## Deployment boundary

`deploy.sh` stages code. `../deployment/deploy.sh` activates read-only plugin and script mounts,
replaces the old Google skill with gateway-tool instructions, removes Google credential mounts
from the sandbox, clears terminal credential forwarding, and patches the gateway's read/sync
guard to refuse Google credential filenames. Recreating the sandbox clears previously synced
files; removing a mount alone does not. Verify again after any upstream image upgrade.

`email-watch` continues running in the gateway and imports the same protected CLI module at
its existing path. Its source and schedule are not changed by this deployment. Operator OAuth
setup is outside the agent tool; it must not copy credentials into the command sandbox.

Tests: `python3 -m unittest discover -s google-workspace -p 'test_*.py'`.
Acceptance: actual tool registration, read-only Gmail labels call reporting status/count only,
credential read/sync rejection and clean sandbox through the Hermes environment path.
