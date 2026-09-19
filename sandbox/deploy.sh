#!/usr/bin/env bash
# Push the sandbox build context to the box and rebuild the image.
# Idempotent; safe to re-run. Does not restart the gateway.
set -euo pipefail

DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
DEST=/opt/alfie/sandbox

ssh "$ALFIE_VPS_HOST" "mkdir -p $DEST"
scp -q "$DIR/Dockerfile" "$DIR/entrypoint.sh" "$DIR/sshd-alfie.conf" "$ALFIE_VPS_HOST:$DEST/"
ssh "$ALFIE_VPS_HOST" "chmod 755 $DEST/entrypoint.sh && chmod 644 $DEST/Dockerfile $DEST/sshd-alfie.conf"

# Build only. Starting it is compose's job, so this stays safe to run at any time.
ssh "$ALFIE_VPS_HOST" "docker build -t alfie-sandbox:latest $DEST"
