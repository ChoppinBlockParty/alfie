"""Gateway-only cutover for the effect-oriented task policy.

Stage the reviewed files under ``deployment/effect-policy-next`` first. The gateway is
stopped before any mounted policy or connector file is replaced.
"""
from pathlib import Path
import shutil
import subprocess


ROOT = Path('/opt/alfie')
FILES = (
    ('task-permissions/alfie_permissions.py', '/opt/hermes/alfie_permissions.py'),
    ('google-workspace/gateway-plugin/read_scope.py',
     '/opt/data/plugins/google_workspace/read_scope.py'),
    ('google-workspace/gateway-plugin/telegram_approvals.py',
     '/opt/data/plugins/google_workspace/telegram_approvals.py'),
    ('reminders/gateway-plugin/__init__.py', '/opt/data/plugins/reminders/__init__.py'),
)


def activate():
    staged_root = ROOT / 'deployment/effect-policy-next'
    for relative, live_path in FILES:
        staged = staged_root / relative
        host = ROOT / relative
        if not staged.is_file() or not host.is_file():
            raise ValueError('Missing staged or installed policy file: ' + relative)
        live = subprocess.check_output(['docker', 'exec', 'alfie', 'cat', live_path])
        if live != host.read_bytes():
            raise ValueError('Live mounted code drift: ' + relative)
        compile(staged.read_text(), relative, 'exec')

    subprocess.run(['python3', str(ROOT / 'deployment/prepare.py')], check=True)
    lock = ROOT / 'deployment/maintenance.lock'
    with lock.open('x') as output:
        output.write('Effect-policy maintenance; failed cutover requires operator review.\n')
    subprocess.run(['docker', 'stop', 'alfie'], check=True, stdout=subprocess.DEVNULL)
    for relative, _ in FILES:
        destination = ROOT / relative
        shutil.copyfile(staged_root / relative, destination)
        destination.chmod(0o644)
    subprocess.run(['docker', 'compose', '-f', str(ROOT / 'docker-compose.alfie.yml'),
                    'up', '-d', '--no-build', '--force-recreate', 'gateway'], check=True)
    lock.unlink()
    print('PASS effect-oriented task policy activated')


if __name__ == '__main__':
    activate()
