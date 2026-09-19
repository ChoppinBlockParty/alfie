"""Register or update the email-watch cron job. Idempotent.

Runs inside the alfie container as uid 10000 (deploy.sh does this). `hermes cron create` has no
flag for `no_agent`, so the job is written through the cron.jobs API.
"""
from cron.jobs import create_job, list_jobs, update_job
import json
import re
import sys

NAME = "email-watch"
SCRIPT = "email_watch.py"          # resolved against $HERMES_HOME/scripts/
SCHEDULE = "every 30m"
existing = [j for j in list_jobs(include_disabled=True) if j.get("name") == NAME]
if '--origin-stdin' in sys.argv:
    values = json.load(sys.stdin)
    for name in ('EMAIL_WATCH_CHAT_ID', 'EMAIL_WATCH_THREAD_ID', 'EMAIL_WATCH_USER_ID'):
        pattern = r'-?[0-9]+' if name == 'EMAIL_WATCH_CHAT_ID' else r'[0-9]+'
        if not re.fullmatch(pattern, values.get(name, '')):
            raise SystemExit('Missing or invalid ' + name)
    ORIGIN = {'platform': 'telegram', 'chat_id': values['EMAIL_WATCH_CHAT_ID'],
              'thread_id': values['EMAIL_WATCH_THREAD_ID'],
              'user_id': values['EMAIL_WATCH_USER_ID'], 'scope_id': None}
elif existing and existing[0].get('origin'):
    ORIGIN = existing[0]['origin']
else:
    raise SystemExit('New registration requires --origin-stdin; use deploy.sh with .env.local')
if existing:
    # prompt=None is explicit: a previous agent-driven edit left a stale wrapper prompt on the
    # record, which is dead weight under no_agent but misleads anyone reading the job.
    job = update_job(existing[0]["id"], {"script": SCRIPT, "no_agent": True, "schedule": SCHEDULE,
                                         "deliver": "origin", "origin": ORIGIN, "prompt": None,
                                         "failure_deliver": "origin"})
    print(f"updated {job['id']} {NAME} enabled={job.get('enabled')} next={job.get('next_run_at')}")
else:
    job = create_job(prompt=None, schedule=SCHEDULE, name=NAME, deliver="origin", origin=ORIGIN,
                     script=SCRIPT, no_agent=True, failure_deliver="origin")
    print(f"created {job['id']} {NAME} next={job.get('next_run_at')}")
