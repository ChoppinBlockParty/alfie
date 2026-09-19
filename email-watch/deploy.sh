#!/usr/bin/env bash
# Deploy email-watch to the box and register its cron job. Idempotent; safe to re-run.
set -euo pipefail

DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
DATA=/opt/alfie/data          # $HERMES_HOME on the host; /opt/data in the container

# Validate locally before staging. Values travel over SSH stdin, never command arguments.
origin_json() {
  python3 -c 'import json,os,re,sys
names=("EMAIL_WATCH_CHAT_ID","EMAIL_WATCH_THREAD_ID","EMAIL_WATCH_USER_ID")
values={name:os.environ.get(name, "") for name in names}
for name,value in values.items():
 if not re.fullmatch(r"-?[0-9]+" if name==names[0] else r"[0-9]+",value):
  sys.exit("Missing or invalid " + name)
print(json.dumps(values))'
}
origin_json >/dev/null

scp -q "$DIR/email_watch.py" "$HOST:$DATA/scripts/email_watch.py"
scp -q "$DIR/SKILL.md" "$HOST:/root/email-watch-SKILL.md"
scp -q "$DIR/register_job.py" "$HOST:/root/email-watch-register.py"

ssh "$HOST" "set -euo pipefail
  chown 10000:10000 $DATA/scripts/email_watch.py && chmod 700 $DATA/scripts/email_watch.py
  mkdir -p $DATA/skills/personal/email-watch
  cp /root/email-watch-SKILL.md $DATA/skills/personal/email-watch/SKILL.md
  chown -R 10000:10000 $DATA/skills/personal/email-watch   # uid 10000 has no host passwd entry
  chmod 644 $DATA/skills/personal/email-watch/SKILL.md
  docker cp /root/email-watch-register.py alfie:/tmp/email-watch-register.py
"
origin_json | ssh "$HOST" "docker exec -i -u 10000:10000 alfie /usr/bin/bash -lc 'python /tmp/email-watch-register.py --origin-stdin'"
ssh "$HOST" "set -euo pipefail
  docker exec -u 0 alfie rm -f /tmp/email-watch-register.py
  rm -f /root/email-watch-SKILL.md /root/email-watch-register.py"
