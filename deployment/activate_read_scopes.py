"""Coordinated host cutover: private read scopes, reviewed targets and bounded retrieval.

Existing images and four containers only. Stage under deployment/read-scope-next first.
Never invoke generic staging scripts against active mounts for this upgrade.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import yaml

ROOT = Path('/opt/alfie')


def activate():
    stage = ROOT / 'deployment/read-scope-next'
    pairs = [
        ('google-workspace/gateway-plugin/__init__.py', 'alfie', '/opt/data/plugins/google_workspace/__init__.py'),
        ('google-workspace/gateway-plugin/telegram_approvals.py', 'alfie', '/opt/data/plugins/google_workspace/telegram_approvals.py'),
        ('google-workspace/scripts/google_api.py', 'alfie', '/opt/alfie-google/scripts/google_api.py'),
        ('task-permissions/alfie_permissions.py', 'alfie', '/opt/hermes/alfie_permissions.py'),
    ]
    if (ROOT / 'google-workspace/gateway-plugin/read_scope.py').exists():
        raise ValueError('Read-scope release already present; inspect before updating')
    for name, container, live in pairs:
        if (ROOT / name).read_bytes() != subprocess.check_output(['docker', 'exec', container, 'cat', live]):
            raise ValueError('Live source drift')
    for name in ('read_scope.py', 'validation.py'):
        pairs.append(('google-workspace/gateway-plugin/' + name, None, None))
    pairs.append(('google-workspace/scripts/review_context.py', None, None))
    pairs.append(('google-workspace/reconcile.py', None, None))
    for name, _, _ in pairs:
        compile((stage / name).read_text(), '<staged-read-scope>', 'exec')
    retrieval = stage / 'web-search/worker/retrieval.py'
    compile(retrieval.read_text(), '<staged-retrieval>', 'exec')
    live_retrieval = subprocess.check_output(['docker', 'exec', 'alfie-websearch', 'cat', '/opt/websearch/retrieval.py'])
    if live_retrieval != (ROOT / 'websearch/worker/retrieval.py').read_bytes():
        raise ValueError('Worker retrieval source drift')
    policy_path = ROOT / 'task-permissions/cron-policy.json'
    policy_bytes = policy_path.read_bytes()
    if policy_bytes != subprocess.check_output(['docker', 'exec', 'alfie', 'cat', '/opt/alfie-permissions/cron-policy.json']):
        raise ValueError('Cron policy drift')
    policy = json.loads(policy_bytes)
    old = hashlib.sha256((ROOT / 'google-workspace/scripts/google_api.py').read_bytes()).hexdigest()
    new = hashlib.sha256((stage / 'google-workspace/scripts/google_api.py').read_bytes()).hexdigest()
    updated = 0
    for record in policy['jobs'].values():
        files = record.get('files', {})
        key = '/opt/alfie-google/scripts/google_api.py'
        if key in files:
            if files[key] != old:
                raise ValueError('Scheduled Google dependency drift')
            files[key] = new
            updated += 1
    if updated != 1:
        raise ValueError('Unexpected reviewed Google dependency inventory')
    compose_path = ROOT / 'docker-compose.alfie.yml'
    compose = yaml.safe_load(compose_path.read_text())
    volumes = compose['services']['websearch'].setdefault('volumes', [])
    if any(isinstance(v, str) and v.split(':')[1] == '/opt/websearch/retrieval.py' for v in volumes):
        raise ValueError('Retrieval overlay already exists')
    runtime = ROOT / 'websearch/runtime'
    next_retrieval = runtime / 'retrieval.py'
    if next_retrieval.exists():
        raise ValueError('Inspect existing retrieval candidate')
    shutil.copyfile(retrieval, next_retrieval)
    next_retrieval.chmod(0o644)
    volumes.append(str(next_retrieval) + ':/opt/websearch/retrieval.py:ro')
    candidate = ROOT / 'docker-compose.alfie.yml.read-scope-next'
    candidate.write_text(yaml.safe_dump(compose, sort_keys=False))
    candidate.chmod(0o600)
    subprocess.run(['docker', 'compose', '-f', str(candidate), 'config', '--quiet'], check=True)
    subprocess.run(['python3', str(ROOT / 'deployment/prepare.py')], check=True)
    lock = ROOT / 'deployment/maintenance.lock'
    with lock.open('x') as output:
        output.write('Read-scope maintenance; failed cutover requires operator review.\n')
    subprocess.run(['docker', 'stop', 'alfie', 'alfie-websearch'], check=True, stdout=subprocess.DEVNULL)
    if policy_path.read_bytes() != policy_bytes:
        raise ValueError('Cron policy changed during staging; keep gateway stopped')
    for name, _, _ in pairs:
        shutil.copyfile(stage / name, ROOT / name)
        (ROOT / name).chmod(0o644)
    policy_path.write_text(json.dumps(policy, sort_keys=True))
    os.chown(policy_path, 10000, 10000)
    policy_path.chmod(0o600)
    candidate.replace(compose_path)
    subprocess.run(['docker', 'compose', '-f', str(compose_path), 'up', '-d', '--no-build',
                    '--force-recreate', 'websearch', 'gateway'], check=True)
    lock.unlink()  # Only the task-created startup guard, after a successful recreation.
    print('PASS read scopes, target reviews and bounded retrieval activated; existing cron grants preserved')


def activate_retrieval_dns():
    target = ROOT / 'websearch/runtime/retrieval.py'
    staged = ROOT / 'deployment/read-scope-next/web-search/worker/retrieval.py'
    if 'def public_addresses(' in target.read_text():
        raise ValueError('HTTPS DNS release already present')
    if target.read_bytes() != subprocess.check_output(['docker', 'exec', 'alfie-websearch',
                                                       'cat', '/opt/websearch/retrieval.py']):
        raise ValueError('Live retrieval drift')
    compile(staged.read_text(), '<staged-dns-retrieval>', 'exec')
    subprocess.run(['python3', str(ROOT / 'deployment/prepare.py')], check=True)
    lock = ROOT / 'deployment/maintenance.lock'
    with lock.open('x') as output:
        output.write('Worker retrieval maintenance; failed cutover requires operator review.\n')
    subprocess.run(['docker', 'stop', 'alfie-websearch'], check=True, stdout=subprocess.DEVNULL)
    shutil.copyfile(staged, target)
    subprocess.run(['docker', 'compose', '-f', str(ROOT / 'docker-compose.alfie.yml'),
                    'up', '-d', '--no-build', '--force-recreate', 'websearch'], check=True)
    lock.unlink()
    print('PASS proxy-compatible public DNS preflight activated; direct DNS remains blocked')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retrieval-dns', action='store_true')
    args = parser.parse_args()
    (activate_retrieval_dns if args.retrieval_dns else activate)()
