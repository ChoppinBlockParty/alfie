#!/usr/bin/env bash
# Stage immutable gateway code. deployment/deploy.sh owns activation.
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
DEST=/opt/alfie/google-workspace
python3 "$DIR/render_approval_policy.py" --check
ssh "$ALFIE_VPS_HOST" "mkdir -p $DEST/gateway-plugin $DEST/scripts"
scp -q "$DIR/gateway-plugin/__init__.py" "$DIR/gateway-plugin/approval_store.py" "$DIR/gateway-plugin/telegram_approvals.py" "$DIR/gateway-plugin/validation.py" "$DIR/gateway-plugin/plugin.yaml" "$ALFIE_VPS_HOST:$DEST/gateway-plugin/"
scp -q "$DIR/scripts/google_api.py" "$DIR/scripts/_hermes_home.py" "$DIR/scripts/review_context.py" "$ALFIE_VPS_HOST:$DEST/scripts/"
scp -q "$DIR/SKILL.md" "$ALFIE_VPS_HOST:$DEST/SKILL.md"
scp -q "$DIR/LICENSE" "$ALFIE_VPS_HOST:$DEST/LICENSE"
ssh "$ALFIE_VPS_HOST" "chmod 755 $DEST $DEST/gateway-plugin $DEST/scripts && chmod 644 $DEST/gateway-plugin/* $DEST/scripts/* $DEST/SKILL.md"
# Policy is generated only on the VPS and read-only inside the gateway. Never print it.
python3 "$DIR/render_approval_policy.py" | ssh "$ALFIE_VPS_HOST" "python3 -c 'import sys,pathlib,os; p=pathlib.Path(\"$DEST/gateway-plugin/approval-policy.json\"); p.write_bytes(sys.stdin.buffer.read()); os.chown(p,10000,10000); p.chmod(0o600)'"
