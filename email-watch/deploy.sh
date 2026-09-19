#!/usr/bin/env bash
# Deploy email-watch to the box and register its cron job. Idempotent; safe to re-run.
set -euo pipefail

DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
DATA=/opt/alfie/data          # $HERMES_HOME on the host; /opt/data in the container

# Validate locally before staging. Values travel over SSH stdin, never command arguments.
origin_json() {
  python3 -c 'import json,os,re,sys
names=("EMAIL_WATCH_CHAT_ID","EMAIL_WATCH_THREAD_ID","ALFIE_OWNER_TELEGRAM_USER_ID")
values={name:os.environ.get(name, "") for name in names}
for name,value in values.items():
 if not re.fullmatch(r"-?[0-9]+" if name==names[0] else r"[0-9]+",value):
  sys.exit("Missing or invalid " + name)
print(json.dumps(values))'
}
origin_json >/dev/null
bash "$DIR/stage.sh"

scp -q "$DIR/email_watch.py" "$ALFIE_VPS_HOST:$DATA/scripts/email_watch.py"
scp -q "$DIR/email_watch_validation.py" "$ALFIE_VPS_HOST:$DATA/scripts/email_watch_validation.py"
scp -q "$DIR/SKILL.md" "$ALFIE_VPS_HOST:/root/email-watch-SKILL.md"
scp -q "$DIR/register_job.py" "$ALFIE_VPS_HOST:/root/email-watch-register.py"

ssh "$ALFIE_VPS_HOST" "set -euo pipefail
  chown 10000:10000 $DATA/scripts/email_watch.py && chmod 700 $DATA/scripts/email_watch.py
  chown 10000:10000 $DATA/scripts/email_watch_validation.py && chmod 600 $DATA/scripts/email_watch_validation.py
  mkdir -p $DATA/skills/personal/email-watch
  cp /root/email-watch-SKILL.md $DATA/skills/personal/email-watch/SKILL.md
  chown -R 10000:10000 $DATA/skills/personal/email-watch   # uid 10000 has no host passwd entry
  chmod 644 $DATA/skills/personal/email-watch/SKILL.md
  docker cp /root/email-watch-register.py alfie:/tmp/email-watch-register.py
"
origin_json | ssh "$ALFIE_VPS_HOST" "docker exec -i -u 10000:10000 alfie /usr/bin/bash -lc 'python /tmp/email-watch-register.py --origin-stdin'"
ssh "$ALFIE_VPS_HOST" "set -euo pipefail
  docker exec -u 0 alfie rm -f /tmp/email-watch-register.py
  rm -f /root/email-watch-SKILL.md /root/email-watch-register.py"
