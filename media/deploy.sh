#!/usr/bin/env bash
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
ssh "$ALFIE_VPS_HOST" 'mkdir -p /opt/alfie/media'
scp -q "$DIR/alfie_media.py" "$DIR/activate.py" \
  "$ALFIE_VPS_HOST:/opt/alfie/media/"
scp -q "$DIR/../task-permissions/alfie_permissions.py" \
  "$ALFIE_VPS_HOST:/opt/alfie/media/alfie_permissions.py"
ssh "$ALFIE_VPS_HOST" 'python3 /opt/alfie/media/activate.py'
