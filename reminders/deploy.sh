#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
ssh "$ALFIE_VPS_HOST" 'mkdir -p /opt/alfie/reminders/gateway-plugin'
scp -q "$DIR/gateway-plugin/__init__.py" "$DIR/gateway-plugin/plugin.yaml" \
  "$ALFIE_VPS_HOST:/opt/alfie/reminders/gateway-plugin/"
