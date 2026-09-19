"""One-time host migration: inspected job definitions and unchanged grants, no job execution."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/opt/alfie')


def activate():
    stage = ROOT / 'task-permissions/cron-next'
    target = ROOT / 'task-permissions/alfie_permissions.py'
    policy = ROOT / 'task-permissions/cron-policy.json'
    if 'repeat_times' in target.read_text():
        raise ValueError('Fingerprint release already present')
    if target.read_bytes() != subprocess.check_output(
            ['docker', 'exec', 'alfie', 'cat', '/opt/hermes/alfie_permissions.py']):
        raise ValueError('Mounted policy code drift')
    compile((stage / 'alfie_permissions.py').read_text(), '<staged-policy>', 'exec')
    jobs_path = ROOT / 'data/cron/jobs.json'
    jobs_digest = hashlib.sha256(jobs_path.read_bytes()).digest()
    subprocess.run(['docker', 'cp', str(stage), 'alfie:/tmp/alfie-cron-next'], check=True)
    raw = subprocess.check_output(['docker', 'exec', '-e',
        'PYTHONPATH=/tmp/alfie-cron-next:/opt/hermes', 'alfie', '/opt/hermes/.venv/bin/python',
        '/tmp/alfie-cron-next/migrate_cron_policy.py'])
    updated = json.loads(raw)
    if updated.get('version') != 2:
        raise ValueError('Invalid migrated policy')
    staged_policy = stage / 'cron-policy.json'
    with staged_policy.open('xb') as output:
        os.chmod(staged_policy, 0o600)
        output.write(raw)
    subprocess.run(['python3', str(ROOT / 'deployment/prepare.py')], check=True)
    subprocess.run(['docker', 'stop', 'alfie'], check=True, stdout=subprocess.DEVNULL)
    # Fail closed even for a counter-only race; the operator must inspect and restage.
    if hashlib.sha256(jobs_path.read_bytes()).digest() != jobs_digest:
        raise ValueError('Job file changed during migration; gateway remains stopped for review')
    shutil.copyfile(stage / 'alfie_permissions.py', target)
    shutil.copyfile(staged_policy, policy)
    os.chown(policy, 10000, 10000)
    os.chmod(policy, 0o600)
    subprocess.run(['docker', 'compose', '-f', str(ROOT / 'docker-compose.alfie.yml'),
                    'up', '-d', '--no-build', '--force-recreate', 'gateway'], check=True)
    print('PASS cron fingerprint migration activated; grants and schedules unchanged')


if __name__ == '__main__':
    activate()
