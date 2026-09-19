#!/usr/bin/env bash
# Stage immutable gateway code. deployment/deploy.sh owns activation.
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
DEST=/opt/alfie/google-workspace
ssh "$HOST" "mkdir -p $DEST/gateway-plugin $DEST/scripts"
scp -q "$DIR/gateway-plugin/__init__.py" "$DIR/gateway-plugin/plugin.yaml" "$HOST:$DEST/gateway-plugin/"
scp -q "$DIR/scripts/google_api.py" "$DIR/scripts/_hermes_home.py" "$HOST:$DEST/scripts/"
scp -q "$DIR/SKILL.md" "$HOST:$DEST/SKILL.md"
scp -q "$DIR/LICENSE" "$HOST:$DEST/LICENSE"
ssh "$HOST" "chmod 755 $DEST $DEST/gateway-plugin $DEST/scripts && chmod 644 $DEST/gateway-plugin/* $DEST/scripts/* $DEST/SKILL.md"
