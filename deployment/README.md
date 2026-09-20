# Four-container deployment

This subsystem coordinates the VPS selected by `ALFIE_VPS_HOST` in ignored `.env.local`. It is not a fresh-host
installer: Docker, Hermes, Compose, gateway credentials, SSH keys and existing volumes must
already exist. Current topology is in the [root README](../README.md); verified results are in
[acceptance](acceptance.md).

## Build and activate

The four-container security increment is deployed and automated acceptance passed. Telegram
Google approvals use the existing poller; real owner clicks remain the acceptance gate.
Email-derived Calendar/records/timezone changes are disabled. See
[Telegram approvals](telegram-approvals.md) for the remaining connector-level write boundary.
Voice and photo input use Hermes's native media pipeline.

For this existing-image increment, `bash deployment/deploy-security.sh` backs up configuration
and live SQLite consistently, stops the gateway before replacing mounted code, stages approvals
and report-only email code, recreates the sandbox, applies filtering and starts the gateway.
It adds no image build or service. Failures leave the gateway stopped for inspection rather
than automatically restarting mixed code. The full rebuild procedure below remains available.

From the repository root:

```sh
python3 -m unittest discover -s web-browser -p 'test_*.py'
python3 -m unittest discover -s google-workspace -p 'test_*.py'
python3 -m unittest discover -s web-search -p 'test_*.py'
python3 -m unittest discover -s email-watch -p 'test_*.py'
python3 -m unittest discover -s deployment -p 'test_*.py'
git diff --check
./deployment/deploy.sh
```

Copy `.env.example` to `.env.local`, fill in the target and addresses, and run `chmod 600 .env.local`.
Supply actual host addresses privately so host-destination deny rules are correctly generated.
The current private .env.local was reconciled against live interface addresses during cutover.
All deploy scripts load this trusted shell-format file and export its settings to child scripts.
The root deploy script validates public addresses before contacting the host. `render.py` substitutes
validated addresses into firewall, proxy and verification templates during transfer; never install
those templates directly. Missing/invalid addresses stop deployment. `.env.local` is never copied
to the server or included in build contexts. The script runs these steps in order:

1. `prepare.py` creates a root-only timestamped backup, copies operational configuration and
   existing managed plugin/skill/guard files, and tags the four running images for rollback.
   It records the path in `/opt/alfie/deployment/last-backup`. Shared/security SQLite databases
   are snapshotted using the online backup API, including committed WAL data. This is not a
   complete off-box backup. Restores must invalidate approvals and reconcile unknown actions.
2. Subsystem deploy scripts stage code and build sandbox, Squid and shared worker images locally.
   email-watch/stage.sh stages report-only code without changing the existing cron registration;
   apply.py mounts its script, validator and skill read-only. Sandbox personal-data mounts are
   removed while host databases remain intact.
   Dockerfiles use official `debian:13`; the existing gateway remains built from Hermes source.
   No unofficial prebuilt application image is used. Dependencies are pinned where stated in
   the worker Dockerfile; Debian package updates are resolved during rebuilds.
3. Run Chromium offline with its sandbox enabled, no capabilities, read-only rootfs and the
   deployed seccomp profile. A failed launch stops deployment before activation.
4. `apply.py` prepares Compose/config updates and mounts credential guards derived from the
   running Hermes image. `activate.sh` validates Compose and Squid, installs firewall rules,
   stops the gateway, recreates sandbox/proxy/worker, reapplies filtering and starts the gateway.
5. `verify.py --research` checks actual Hermes SSH execution, plugins, Google labels, credential
   guards, network restrictions, mTLS, browser actions and research. Failures return nonzero;
   rollback is operator-controlled.

Staging replaces bind-mounted plugin files, so it can affect a running process that loads code
again. Treat the full operation as a maintenance window, even before Compose activation.
Images, volumes and personal data are not pruned. The last full build left about 12 GiB free;
monitor disk space before another build.

For independent verification and memory samples:

Start `/bin/bash` first if your terminal uses zsh. The loader requires Bash and now rejects
other shells. In zsh, `HOST` is a shell parameter and is not evidence of the deployment target.
The target comes from the repository's ignored `.env.local` (with the leading dot). When using
an execution tool, select `/bin/bash` with `login: false` explicitly. Stop if loading fails.

```bash
set -e
source deployment/local-env.sh
ssh "$ALFIE_VPS_HOST" 'python3 /opt/alfie/deployment/verify.py --research'
scp deployment/measure.py "$ALFIE_VPS_HOST":/opt/alfie/deployment/
ssh "$ALFIE_VPS_HOST" 'python3 /opt/alfie/deployment/measure.py'
```

For a connection check from the repository root, this explicitly selects Bash even when
the surrounding terminal uses zsh:

```sh
/bin/bash -c 'source deployment/local-env.sh && ssh -o BatchMode=yes -o ConnectTimeout=8 "$ALFIE_VPS_HOST" true'
```

Fixtures are public pages. Tests never submit the demo form or send account messages. Research
consumes model quota. Fixture outages can fail acceptance without indicating a security failure.

## Firewall and runtime

The read-scope/retrieval increment is activated by `activate_read_scopes.py`, with staged files
under its documented private host staging root. It validates existing live source, backs up,
stops affected containers before copying read-only mounted code, updates only the reviewed CLI
dependency hash in cron policy, and recreates existing images. Its worker-only `--retrieval-dns`
follow-up supports the initial direct-DNS-to-HTTPS-DNS correction. Both cutovers use a temporary
startup guard; if a cutover fails, inspect before removing that guard or restarting services.
Do not run generic staging scripts against active code mounts. `prepare.py` includes worker
runtime overlays as well as gateway plugins in subsequent rollback backups.

`firewall.sh` installs `ALFIE-FORWARD` in Docker's `DOCKER-USER` chain and `ALFIE-HOST` in INPUT.
The prepared update uses a validated `iptables-restore --noflush` transaction. It preserves
unrelated chains and keeps the active rules until COMMIT. Worker source restrictions precede
the general established-connection allowance; only replies to gateway SSH/TLS and proxy traffic
are allowed. `--print` on a rendered script emits the transaction without modifying the host.
Local generation and actual Linux restore/traffic tests passed. Continuous firewall-update probes
(50 denied attempts), a real host reboot and offline encrypted data recovery also passed;
full replacement-host/image recovery remains outstanding.
Workers may initiate only to proxy port 3128. Proxy outbound traffic is public TCP 80/443 only;
private/reserved destinations and the VPS public address are denied independently of Squid.
Docker's embedded resolver supplies DNS; this is not a DNS exfiltration-proof boundary.
Gateway retains trusted network access for Telegram, Google and inference.

The script persists br_netfilter and bridge filtering, and the existing
`alfie-docker-firewall.service` is enabled. Re-run the firewall after network changes.
`alfie-boot-gate.service` starts containers only after the firewall. `boot_gate.py` changes the
four containers to `on-failure:5`, which does not independently start them after Docker daemon
restart ([Docker restart policies](https://docs.docker.com/engine/containers/start-containers-automatically/)).
The gate checks policy/overlay mounts and refuses startup when the private maintenance lock is
present. `verify.py` checks unit ordering and policies. Reboot acceptance passed. Do not flush
unrelated firewall chains or expose service ports. The lock is a startup guard, not a stop command
or protection against an operator directly invoking Docker.

Chromium requires the additional clone/unshare/setns/chroot seccomp allowances documented in
`web-browser/README.md`. All worker capabilities remain dropped; Chromium sandbox stays enabled.
Existing worker PKI verifies its explicit CA and hostname. It lacks newer CA key-usage metadata;
clients do not enable Python's extra strict X.509 flag. Neither certificate verification nor
mutual TLS is disabled. Rotate CA/server/client certificates together as separate maintenance.

## Rollback

For a browser-only fault, preserve the Google and network boundaries. On the VPS, disable the
browser plugin and restart gateway/worker:

```sh
python3 - <<'PY'
from pathlib import Path
import yaml
p=Path('/opt/alfie/data/config.yaml')
c=yaml.safe_load(p.read_text())
plugins=c.setdefault('plugins',{})
plugins['enabled']=[x for x in plugins.get('enabled',[]) if x!='web_browser']
if 'web_browser' not in plugins.setdefault('disabled',[]):
    plugins['disabled'].append('web_browser')
p.write_text(yaml.safe_dump(c,sort_keys=False))
PY
docker compose -f /opt/alfie/docker-compose.alfie.yml restart gateway websearch
```

For image-only rollback, select a saved image tag from the chosen root-only backup's
`images.json`, set that service's Compose `image` to the tag and recreate it. Match plugin code
to the saved image protocol. Verify again. Do not prune rollback tags.

A full pre-cutover restore can restore old Google credential exposure and remove task checks.
Do not activate it as a security rollback. Restore into an isolated rehearsal environment first;
preserve current denied writes, credential separation and firewall restrictions. If compatible
recovery is unavailable, keep the affected feature disabled. Verify restored plugin discovery,
task overlays, private policy, network layout and image compatibility before starting services.
Never leave firewall chains attached to an incompatible network layout or flush them without
replacement filtering. Invalidate restored approvals and reconcile unknown external actions.
Never use `terminal.backend: local` as a rollback.

`python3 /opt/alfie/deployment/verify_backup.py --latest` checks private rollback artifact
readability, overlay digests/syntax and SQLite integrity without restoring or uploading anything.
It does not establish a complete backup or prove recoverability after host loss. The separate
[backup subsystem](../backup/README.md) provides manually triggered encrypted Drive backups,
Mac-only recovery-key custody and an accepted offline data recovery rehearsal. A brief outage
was owner-authorized with advance notice; keep giving notice before disruptive operations.

Find backup locations in private operator records. Backups include managed
Google/browser/research plugin paths and both credential guards for repeat deployments.
