"""One-time host cutover for the tested bounded Google subprocess executor."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/opt/alfie')


def activate():
    staged = ROOT / 'task-permissions/scope-next/google-plugin-next.py'
    target = ROOT / 'google-workspace/gateway-plugin/__init__.py'
    live = '/opt/data/plugins/google_workspace/__init__.py'
    if 'def bounded_run(' in target.read_text():
        raise ValueError('Executor release already present; inspect before updating')
    if subprocess.check_output(['docker', 'exec', 'alfie', 'cat', live]) != target.read_bytes():
        raise ValueError('Live mounted code drift')
    compile(staged.read_text(), '<staged-google-executor>', 'exec')
    subprocess.run(['python3', str(ROOT / 'deployment/prepare.py')], check=True)
    subprocess.run(['docker', 'stop', 'alfie'], check=True, stdout=subprocess.DEVNULL)
    shutil.copyfile(staged, target)
    subprocess.run(['docker', 'compose', '-f', str(ROOT / 'docker-compose.alfie.yml'),
                    'up', '-d', '--no-build', '--force-recreate', 'gateway'], check=True)
    print('PASS bounded Google executor activated')


if __name__ == '__main__':
    activate()
