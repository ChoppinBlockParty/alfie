"""Gateway-only cutover for the final reviewed task-policy prompt/classifier catalogue."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/opt/alfie')


def activate():
    staged = ROOT / 'deployment/usability-next/task-permissions/alfie_permissions.py'
    host = ROOT / 'task-permissions/alfie_permissions.py'
    live = subprocess.check_output(['docker', 'exec', 'alfie', 'cat',
                                    '/opt/hermes/alfie_permissions.py'])
    if host.read_bytes() != live:
        raise ValueError('Live task policy drift')
    compile(staged.read_text(), 'alfie_permissions.py', 'exec')
    subprocess.run(['python3', str(ROOT / 'deployment/prepare.py')], check=True)
    lock = ROOT / 'deployment/maintenance.lock'
    with lock.open('x') as output:
        output.write('Task-policy maintenance; failed cutover requires operator review.\n')
    subprocess.run(['docker', 'stop', 'alfie'], check=True, stdout=subprocess.DEVNULL)
    shutil.copyfile(staged, host)
    host.chmod(0o644)
    subprocess.run(['docker', 'compose', '-f', str(ROOT / 'docker-compose.alfie.yml'),
                    'up', '-d', '--no-build', '--force-recreate', 'gateway'], check=True)
    lock.unlink()
    print('PASS final task-policy prompt and catalogue activated')


if __name__ == '__main__':
    activate()
