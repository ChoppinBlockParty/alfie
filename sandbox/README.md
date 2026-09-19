# Command sandbox

A Compose-managed container running sshd on 2222. Hermes `terminal.backend: ssh` routes shell,
file tools and execute_code here. No Docker socket or host shell. Gateway initiates SSH;
sandbox cannot initiate connections to gateway, web worker or host services.

## Files and credentials

Allowed: read-only skill/script trees, read/write shared records and email-watch ledger, and
Hermes's synced skills/cache. Personal records remain readable by agent commands; this is why
public browsing has its own worker. Do not claim the sandbox contains no private data.

Google credentials are removed by the coordinated deployment. The gateway plugin owns Google
operations. The old skill's required_credential_files declarations are removed, gateway
credential registration/read guard blocks Google filenames, terminal credential forwarding
is cleared, and the sandbox is recreated to clear copied files. `.env`, `auth.json`, gateway
memory/state databases, vaults and host secrets are not mounted. No model token is provisioned
to shell commands by this build; future LLM CLI access needs explicit access-token delivery.

The image has Python, git, curl and ripgrep. Google SDKs are no longer installed. Google-related
shell instructions are replaced by the google_workspace gateway tool. Existing email-watch
cron executes in the gateway, not in this container.

## Runtime

512 MiB RAM/no swap, 256 PID cap, no-new-privileges. sshd starts as root for privilege separation;
agent sessions run uid 10000. Required capabilities: CHOWN, SETUID, SETGID, DAC_OVERRIDE,
FOWNER, SYS_CHROOT; no NET_BIND_SERVICE because port is 2222.

Account password field is `*`, not locked `!`: UsePAM=no rejects locked users even for public
keys. Host key persists in sandbox-hostkeys, so recreation preserves the gateway's known_hosts.
SSH runs bash -c, not a login shell. entrypoint.sh writes proxy variables into one sshd SetEnv
line; container environment alone does not reach SSH sessions. HERMES_HOME remains unset.

Sandbox may use Squid only for chatgpt.com; no public browsing or Google API egress. Proxy
variables do not enforce this: internal bridge and host packet rules do.

`./deploy.sh` builds without restart. Coordinated cutover is `../deployment/deploy.sh`.
Verify through tools.code_execution_tool._get_or_create_env, plus deliberate denied credential
registration and live network probes. Never roll back to terminal.backend=local.
