# Four-container deployment

This subsystem coordinates the VPS selected by `HOST` in ignored `.env.local`. It is not a fresh-host
installer: Docker, Hermes, Compose, gateway credentials, SSH keys and existing volumes must
already exist. Current topology is in [main-spec](../main-spec.md); verified results are in
[acceptance](acceptance.md).

## Build and activate

From the repository root:

```sh
python3 -m unittest discover -s web-browser -p 'test_*.py'
python3 -m unittest discover -s google-workspace -p 'test_*.py'
python3 -m unittest discover -s web-search -p 'test_*.py'
git diff --check
./deployment/deploy.sh
```

Copy `.env.example` to `.env.local`, fill in the target and addresses, and run `chmod 600 .env.local`.
The sanitized local file contains non-address placeholders; supply the actual host addresses
privately before deployment so the host-destination deny rules are correctly generated.
All deploy scripts load this trusted shell-format file and export its settings to child scripts.
The root deploy script validates public addresses before contacting the host. `render.py` substitutes
validated addresses into firewall, proxy and verification templates during transfer; never install
those templates directly. Missing/invalid addresses stop deployment. `.env.local` is never copied
to the server or included in build contexts. The script runs these steps in order:

1. `prepare.py` creates a root-only timestamped backup, copies operational configuration and
   existing managed plugin/skill/guard files, and tags the four running images for rollback.
   It records the path in `/opt/alfie/deployment/last-backup`. This is a configuration backup,
   not a backup of live databases or personal data.
2. Subsystem deploy scripts stage code and build sandbox, Squid and shared worker images locally.
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

```sh
source deployment/local-env.sh
ssh "$HOST" 'python3 /opt/alfie/deployment/verify.py --research'
scp deployment/measure.py "$HOST":/opt/alfie/deployment/
ssh ${HOST} 'python3 /opt/alfie/deployment/measure.py'
```

Fixtures are public pages. Tests never submit the demo form or send account messages. Research
consumes model quota. Fixture outages can fail acceptance without indicating a security failure.

## Firewall and runtime

`firewall.sh` installs `ALFIE-FORWARD` in Docker's `DOCKER-USER` chain and `ALFIE-HOST` in INPUT.
Workers may initiate only to proxy port 3128. Proxy outbound traffic is public TCP 80/443 only;
private/reserved destinations and the VPS public address are denied independently of Squid.
Docker's embedded resolver supplies DNS; this is not a DNS exfiltration-proof boundary.
Gateway retains trusted network access for Telegram, Google and inference.

The script persists br_netfilter and bridge filtering, and the existing
`alfie-docker-firewall.service` is enabled. Re-run the firewall after network changes. No reboot
was performed during acceptance. Do not flush unrelated firewall chains or expose service ports.

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

A full pre-cutover restore also restores the old Google credential exposure. Use only when
that regression is explicitly intended: stop gateway and worker, restore the backup's Compose,
config and archived plugin/skill files to their original paths, map service images to
`images.json`, and reconcile the saved firewall with the restored network addresses before
recreating services. The new dedicated ALFIE chains must not be blindly left attached to a
different network layout or flushed without replacement filtering. Backups from before this
build do not contain the newly created plugin directories. Review restored plugin discovery.
Never use `terminal.backend: local` as a rollback.

Find backup locations in private operator records. Backups include managed
Google/browser/research plugin paths and both credential guards for repeat deployments.
