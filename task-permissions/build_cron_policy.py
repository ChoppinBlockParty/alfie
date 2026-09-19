"""Run inside gateway, pipe private output to a root-managed read-only policy file."""
import hashlib
import json
from pathlib import Path
from cron.jobs import list_jobs
from alfie_permissions import job_digest, classify_scheduled, Denied, READS

ALLOWED_SCRIPTS = {'email_watch.py', 'check_codex_subscription_quota.py'}


def build():
    owner = json.loads(Path('/opt/data/plugins/google_workspace/approval-policy.json').read_text())
    records = {}
    for job in list_jobs(include_disabled=True):
        origin = job.get('origin') or {}
        if origin.get('platform') != 'telegram' or str(origin.get('user_id') or '') != owner['user'] \
                or str(origin.get('chat_id') or '') not in (owner['chat'], owner['user']):
            raise ValueError('A scheduled task has an unreviewed destination')
        if job.get('deliver') != 'origin':
            raise ValueError('Only fixed owner-origin cron delivery is supported')
        files = {}
        if job.get('script'):
            script = Path(job['script'])
            if script.name not in ALLOWED_SCRIPTS or str(script) not in (script.name, '/opt/data/scripts/' + script.name):
                raise ValueError('Unreviewed scheduled script')
            if not job.get('no_agent'):
                raise ValueError('Mixed agent/script schedule needs review')
            paths = [Path('/opt/data/scripts') / script.name]
            if script.name == 'email_watch.py':
                paths += [Path('/opt/data/scripts/email_watch_validation.py'),
                          Path('/opt/alfie-google/scripts/google_api.py'),
                          Path('/opt/alfie-google/scripts/_hermes_home.py')]
            files = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        mode = 'reviewed-script'
        if not files:
            try:
                mode, _ = classify_scheduled(job.get('prompt') or '')
                if mode not in (*READS, 'web-read', 'chat'):
                    mode = 'blocked'
            except Denied:
                mode = 'blocked'
        records[str(job['id'])] = {'digest': job_digest(job), 'files': files, 'mode': mode}
    return {'version': 1, 'jobs': records}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
