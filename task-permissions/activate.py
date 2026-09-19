"""Host-side activation preparation. Existing images, read-only mounts, no task execution."""
import json
import os
from pathlib import Path
import subprocess
import yaml

ROOT = Path('/opt/alfie')
PERMISSIONS = ROOT / 'task-permissions'


def prepare():
    manifest = json.loads((PERMISSIONS / 'runtime/manifest.json').read_text())
    # Refuse source drift before modifying Compose or stopping the gateway.
    for relative, hashes in manifest.items():
        digest = subprocess.check_output(['docker', 'exec', 'alfie', 'sha256sum',
                                          '/opt/hermes/' + relative], text=True).split()[0]
        if digest not in (hashes['baseline'], hashes['patched']):
            raise ValueError('Runtime source differs from the reviewed baseline: ' + relative)
    compose_path = ROOT / 'docker-compose.alfie.yml'
    compose = yaml.safe_load(compose_path.read_text())
    gateway = compose['services']['gateway']
    volumes = gateway.setdefault('volumes', [])
    mounts = [(str(PERMISSIONS / 'alfie_permissions.py'), '/opt/hermes/alfie_permissions.py'),
              (str(PERMISSIONS / 'cron-policy.json'), '/opt/alfie-permissions/cron-policy.json')]
    mounts += [(str(PERMISSIONS / 'runtime' / relative), '/opt/hermes/' + relative) for relative in manifest]
    for source, target in mounts:
        if not Path(source).is_file():
            raise ValueError('Missing staged policy source')
        volumes[:] = [v for v in volumes if not (isinstance(v, str) and v.split(':')[1] == target)]
        volumes.append(source + ':' + target + ':ro')
    next_path = compose_path.with_suffix('.yml.permissions-next')
    next_path.write_text(yaml.safe_dump(compose, sort_keys=False))
    next_path.chmod(0o600)
    subprocess.run(['docker', 'compose', '-f', str(next_path), 'config', '--quiet'], check=True)
    print('Task permission mounts and Compose configuration validated.')


if __name__ == '__main__':
    prepare()
