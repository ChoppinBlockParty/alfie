#!/usr/bin/env bash
# Stage reviewed code only; preserve the existing cron identity and destination.
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
DEST=/opt/alfie/email-watch
ssh "$ALFIE_VPS_HOST" "mkdir -p $DEST"
scp -q "$DIR/email_watch.py" "$DIR/email_watch_validation.py" "$DIR/SKILL.md" "$ALFIE_VPS_HOST:$DEST/"
ssh "$ALFIE_VPS_HOST" "chmod 755 $DEST && chmod 644 $DEST/email_watch.py $DEST/email_watch_validation.py $DEST/SKILL.md"
