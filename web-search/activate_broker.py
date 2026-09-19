"""Host-side coordinated credential-free research cutover, using existing images."""
from pathlib import Path
import shutil
import subprocess
import yaml

ROOT = Path('/opt/alfie')


def activate():
    staged = ROOT / 'websearch/broker-next'
    for name in ('__init__.py', 'inference_broker.py', 'server.py'):
        compile((staged / name).read_text(), name, 'exec')
    live = subprocess.check_output(['docker', 'exec', 'alfie', 'cat', '/opt/data/plugins/websearch/__init__.py'])
    if live != (ROOT / 'websearch/gateway-plugin/__init__.py').read_bytes():
        raise ValueError('Gateway connector drift')
    if b'inference_broker.py' in live:
        raise ValueError('Broker already installed; inspect before replacing')
    compose_path = ROOT / 'docker-compose.alfie.yml'
    compose = yaml.safe_load(compose_path.read_text())
    runtime = ROOT / 'websearch/runtime'
    runtime.mkdir(exist_ok=True)
    volumes = compose['services']['websearch'].setdefault('volumes', [])
    if any(isinstance(v, str) and v.split(':')[1] == '/opt/websearch/server.py' for v in volumes):
        raise ValueError('Worker source already overridden')
    # Staging a new, not-yet-mounted path cannot modify the running worker.
    shutil.copyfile(staged / 'server.py', runtime / 'server.py')
    volumes.append(str(runtime / 'server.py') + ':/opt/websearch/server.py:ro')
    candidate = ROOT / 'docker-compose.alfie.yml.broker-next'
    candidate.write_text(yaml.safe_dump(compose, sort_keys=False))
    candidate.chmod(0o600)
    subprocess.run(['docker', 'compose', '-f', str(candidate), 'config', '--quiet'], check=True)
    subprocess.run(['python3', str(ROOT / 'deployment/prepare.py')], check=True)
    subprocess.run(['docker', 'stop', 'alfie', 'alfie-websearch'], check=True, stdout=subprocess.DEVNULL)
    for name in ('__init__.py', 'inference_broker.py'):
        shutil.copyfile(staged / name, ROOT / 'websearch/gateway-plugin' / name)
    candidate.replace(compose_path)
    subprocess.run(['docker', 'compose', '-f', str(compose_path), 'up', '-d', '--no-build',
                    '--force-recreate', 'websearch', 'gateway'], check=True)
    print('PASS credential-free research broker activated; no new container or listener')


if __name__ == '__main__':
    activate()
