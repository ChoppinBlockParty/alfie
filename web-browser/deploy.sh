#!/usr/bin/env bash
# Shared worker build is owned by web-search; browser has no separate container.
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
DEST=/opt/alfie/web-browser
ssh "$HOST" "mkdir -p $DEST/gateway-plugin"
scp -q "$DIR/gateway-plugin/__init__.py" "$DIR/gateway-plugin/plugin.yaml" "$HOST:$DEST/gateway-plugin/"
scp -q "$DIR/SKILL.md" "$HOST:$DEST/SKILL.md"
ssh "$HOST" "chmod 755 $DEST $DEST/gateway-plugin && chmod 644 $DEST/gateway-plugin/* $DEST/SKILL.md"
"$DIR/../web-search/deploy.sh"
