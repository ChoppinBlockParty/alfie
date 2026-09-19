#!/usr/bin/env bash
# Push the egress build context to the box and rebuild the image.
# Idempotent. Does not restart anything; compose owns that.
set -euo pipefail

DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
DEST=/opt/alfie/egress

python3 "$DIR/../deployment/render.py" "$DIR/squid.conf" >/dev/null
ssh "$ALFIE_VPS_HOST" "mkdir -p $DEST"
scp -q "$DIR/Dockerfile" "$DIR/entrypoint.sh" "$ALFIE_VPS_HOST:$DEST/"
python3 "$DIR/../deployment/render.py" "$DIR/squid.conf" | ssh "$ALFIE_VPS_HOST" "umask 077; cat > $DEST/squid.conf"
ssh "$ALFIE_VPS_HOST" "chmod 644 $DEST/Dockerfile $DEST/squid.conf && chmod 755 $DEST/entrypoint.sh"
ssh "$ALFIE_VPS_HOST" "docker build -t alfie-egress:latest $DEST"
