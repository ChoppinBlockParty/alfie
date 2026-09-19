"""Host-side maintenance cutover for the schema-only overlay update.

Run after staging schema-next and its disposable-runtime verification. Stops the gateway
before replacing mounted files. Existing cron policy, grants and connector code are untouched.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/opt/alfie/task-permissions')


def activate():
    old = json.loads((ROOT / 'runtime/manifest.json').read_text())
    new = json.loads((ROOT / 'schema-next/manifest.json').read_text())
    if old.keys() != new.keys():
        raise ValueError('Overlay target set changed')
    changed = {name for name in old if old[name] != new[name]}
    if changed != {'model_tools.py'}:
        raise ValueError('Expected only the model-tools schema overlay to change')
    for name, hashes in old.items():
        if hashes['baseline'] != new[name]['baseline']:
            raise ValueError('Pinned source changed')
        disk = hashlib.sha256((ROOT / 'runtime' / name).read_bytes()).hexdigest()
        live = subprocess.check_output(['docker', 'exec', 'alfie', 'sha256sum',
                                        '/opt/hermes/' + name], text=True).split()[0]
        if disk != hashes['patched'] or live != disk:
            raise ValueError('Installed overlay drift')
    staged = ROOT / 'schema-next/model_tools.py'
    if hashlib.sha256(staged.read_bytes()).hexdigest() != new['model_tools.py']['patched']:
        raise ValueError('Staged overlay digest mismatch')
    compile(staged.read_text(), 'model_tools.py', 'exec')
    subprocess.run(['python3', '/opt/alfie/deployment/prepare.py'], check=True)
    subprocess.run(['docker', 'stop', 'alfie'], check=True, stdout=subprocess.DEVNULL)
    shutil.copyfile(staged, ROOT / 'runtime/model_tools.py')
    shutil.copyfile(ROOT / 'schema-next/manifest.json', ROOT / 'runtime/manifest.json')
    subprocess.run(['docker', 'compose', '-f', '/opt/alfie/docker-compose.alfie.yml',
                    'up', '-d', '--no-build', '--force-recreate', 'gateway'], check=True)
    print('PASS schema overlay activated; run post-cutover acceptance')


if __name__ == '__main__':
    activate()
