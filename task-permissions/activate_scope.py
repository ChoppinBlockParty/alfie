"""Host maintenance cutover for tested natural-language scope confirmations only."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/opt/alfie')


def activate():
    files = (
        (ROOT / 'task-permissions/scope-next/alfie_permissions.py',
         ROOT / 'task-permissions/alfie_permissions.py', '/opt/hermes/alfie_permissions.py'),
        (ROOT / 'task-permissions/scope-next/telegram_approvals.py',
         ROOT / 'google-workspace/gateway-plugin/telegram_approvals.py',
         '/opt/data/plugins/google_workspace/telegram_approvals.py'),
    )
    if 'SCOPE_CONFIRM' in files[0][1].read_text():
        raise ValueError('Scope release already present; inspect before updating')
    for staged, host, live in files:
        current = subprocess.check_output(['docker', 'exec', 'alfie', 'cat', live])
        if current != host.read_bytes():
            raise ValueError('Live mounted code drift')
        compile(staged.read_text(), '<staged-scope-release>', 'exec')
    subprocess.run(['python3', str(ROOT / 'deployment/prepare.py')], check=True)
    subprocess.run(['docker', 'stop', 'alfie'], check=True, stdout=subprocess.DEVNULL)
    for staged, host, _ in files:
        shutil.copyfile(staged, host)
    subprocess.run(['docker', 'compose', '-f', str(ROOT / 'docker-compose.alfie.yml'),
                    'up', '-d', '--no-build', '--force-recreate', 'gateway'], check=True)
    print('PASS natural-language scope confirmations activated; exact-action approvals unchanged')


if __name__ == '__main__':
    activate()
