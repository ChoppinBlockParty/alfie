"""Host boot gate, not a process supervisor. Docker handles bounded crash retries.

on-failure:5 does not auto-start containers on daemon restart. The oneshot starts them
only after the firewall unit has succeeded. Existing containers/images are retained.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

NAMES = ('alfie-egress', 'alfie-sandbox', 'alfie-websearch', 'alfie')


def call(args):
    return subprocess.check_output(args, text=True)


def check_policies(items):
    if {item['Name'].lstrip('/') for item in items} != set(NAMES):
        raise ValueError('Unexpected container set')
    for item in items:
        if item['HostConfig']['RestartPolicy'] != {'Name': 'on-failure', 'MaximumRetryCount': 5}:
            raise ValueError('Unsafe boot restart policy')


def start():
    root = Path('/opt/alfie')
    if (root / 'deployment/maintenance.lock').exists():
        raise ValueError('Operator maintenance lock: automatic startup denied')
    subprocess.run(['systemctl', 'is-active', '--quiet', 'alfie-docker-firewall.service'], check=True)
    items = json.loads(call(['docker', 'inspect', *NAMES]))
    check_policies(items)
    gateway = next(item for item in items if item['Name'] == '/alfie')
    mounts = {m['Destination']: m for m in gateway['Mounts']}
    runtime = root / 'task-permissions/runtime'
    manifest = json.loads((runtime / 'manifest.json').read_text())
    for name, hashes in manifest.items():
        mount = mounts.get('/opt/hermes/' + name)
        if not mount or mount['RW'] or Path(mount['Source']) != runtime / name \
                or hashlib.sha256((runtime / name).read_bytes()).hexdigest() != hashes['patched']:
            raise ValueError('Task overlay drift: automatic startup denied')
    for destination in ('/opt/hermes/alfie_permissions.py', '/opt/alfie-permissions/cron-policy.json'):
        if destination not in mounts or mounts[destination]['RW']:
            raise ValueError('Task policy mount missing or writable')
    subprocess.run(['docker', 'start', *NAMES], check=True, stdout=subprocess.DEVNULL)
    print('PASS Alfie started after firewall policy')


def install():
    import yaml
    root = Path('/opt/alfie')
    compose_path = root / 'docker-compose.alfie.yml'
    compose = yaml.safe_load(compose_path.read_text())
    if set(compose['services']) != {'gateway', 'sandbox', 'websearch', 'egress'}:
        raise ValueError('Unexpected Compose services')
    for service in compose['services'].values():
        service['restart'] = 'on-failure:5'
    candidate = root / 'docker-compose.alfie.yml.boot-next'
    candidate.write_text(yaml.safe_dump(compose, sort_keys=False))
    candidate.chmod(0o600)
    subprocess.run(['docker', 'compose', '-f', str(candidate), 'config', '--quiet'], check=True)
    unit = root / 'deployment/alfie-boot-gate.service'
    subprocess.run(['systemd-analyze', 'verify', str(unit)], check=True)
    subprocess.run(['python3', str(root / 'deployment/prepare.py')], check=True)
    subprocess.run(['docker', 'update', '--restart=on-failure:5', *NAMES], check=True, stdout=subprocess.DEVNULL)
    candidate.replace(compose_path)
    subprocess.run(['install', '-m', '644', str(unit), '/etc/systemd/system/alfie-boot-gate.service'], check=True)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', 'alfie-boot-gate.service'], check=True)
    check_policies(json.loads(call(['docker', 'inspect', *NAMES])))
    print('PASS boot gate installed; no service restart performed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'start'))
    args = parser.parse_args()
    (install if args.action == 'install' else start)()
