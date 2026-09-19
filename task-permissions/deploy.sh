#!/usr/bin/env bash
# Prerequisite: validated overlay generated from the inspected pinned source tree.
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
OVERLAY="$DIR/../.private/task-permissions-runtime"
test -f "$OVERLAY/manifest.json"
# Initial activation only: never overwrite files already mounted in a live gateway.
ssh "$ALFIE_VPS_HOST" 'test ! -f /opt/alfie/task-permissions/runtime/manifest.json' || {
  printf '%s\n' 'Existing permission release found. Use a reviewed maintenance cutover; refusing live overlay replacement.' >&2
  exit 1
}
scp -q "$DIR/../deployment/prepare.py" "$ALFIE_VPS_HOST:/opt/alfie/deployment/prepare.py"
ssh "$ALFIE_VPS_HOST" 'python3 /opt/alfie/deployment/prepare.py'
ssh "$ALFIE_VPS_HOST" 'mkdir -p /opt/alfie/task-permissions/runtime'
scp -q "$DIR/alfie_permissions.py" "$DIR/activate.py" "$DIR/build_cron_policy.py" "$DIR/live_acceptance.py" "$ALFIE_VPS_HOST:/opt/alfie/task-permissions/"
COPYFILE_DISABLE=1 tar --no-xattrs -C "$OVERLAY" -cf - . | ssh "$ALFIE_VPS_HOST" 'tar -xf - -C /opt/alfie/task-permissions/runtime'
# Policy is rendered inside a disposable operator process using the already validated code.
ssh "$ALFIE_VPS_HOST" 'set -eu; docker cp /opt/alfie/task-permissions/alfie_permissions.py alfie:/tmp/alfie-task-validation/task-permissions/alfie_permissions.py; docker cp /opt/alfie/task-permissions/build_cron_policy.py alfie:/tmp/alfie-task-validation/task-permissions/build_cron_policy.py; umask 077; docker exec -w /opt/hermes -e PYTHONPATH=/tmp/alfie-task-validation/task-permissions:/opt/hermes alfie python /tmp/alfie-task-validation/task-permissions/build_cron_policy.py > /opt/alfie/task-permissions/cron-policy.json; chown 10000:10000 /opt/alfie/task-permissions/cron-policy.json; chmod 600 /opt/alfie/task-permissions/cron-policy.json; python3 /opt/alfie/task-permissions/activate.py'
ssh "$ALFIE_VPS_HOST" 'docker stop alfie >/dev/null'
# Replace credentialed connectors only while the gateway is stopped.
bash "$DIR/../google-workspace/deploy.sh"
scp -q "$DIR/../web-search/gateway-plugin/__init__.py" "$ALFIE_VPS_HOST:/opt/alfie/websearch/gateway-plugin/__init__.py"
scp -q "$DIR/../web-browser/gateway-plugin/__init__.py" "$ALFIE_VPS_HOST:/opt/alfie/web-browser/gateway-plugin/__init__.py"
ssh "$ALFIE_VPS_HOST" 'mv /opt/alfie/docker-compose.alfie.yml.permissions-next /opt/alfie/docker-compose.alfie.yml && docker compose -f /opt/alfie/docker-compose.alfie.yml up -d --no-build gateway'
printf '%s\n' 'Task policy activated. Run the permission-specific acceptance checks.'
