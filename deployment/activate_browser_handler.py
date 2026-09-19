"""Gateway-only maintenance cutover for the browser registry argument adapter."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/opt/alfie')


def activate():
    staged = ROOT / 'deployment/usability-next/web-browser/gateway-plugin/__init__.py'
    host = ROOT / 'web-browser/gateway-plugin/__init__.py'
    live = subprocess.check_output(['docker', 'exec', 'alfie', 'cat',
                                    '/opt/data/plugins/web_browser/__init__.py'])
    if host.read_bytes() != live:
        raise ValueError('Live browser plugin drift')
    compile(staged.read_text(), 'web_browser/__init__.py', 'exec')
    subprocess.run(['python3', str(ROOT / 'deployment/prepare.py')], check=True)
    lock = ROOT / 'deployment/maintenance.lock'
    with lock.open('x') as output:
        output.write('Browser handler maintenance; failed cutover requires operator review.\n')
    subprocess.run(['docker', 'stop', 'alfie'], check=True, stdout=subprocess.DEVNULL)
    shutil.copyfile(staged, host)
    host.chmod(0o644)
    subprocess.run(['docker', 'compose', '-f', str(ROOT / 'docker-compose.alfie.yml'),
                    'up', '-d', '--no-build', '--force-recreate', 'gateway'], check=True)
    lock.unlink()
    print('PASS browser registry argument adapter activated')


if __name__ == '__main__':
    activate()
