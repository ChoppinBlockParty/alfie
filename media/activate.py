"""Host-side activation of the media preprocessing subsystem."""
from pathlib import Path
import os
import shutil
import subprocess
import yaml
from alfie_media import configure_stt


ROOT = Path('/opt/alfie')


def mount_destination(item):
    if not isinstance(item, str):
        return None
    fields = item.split(':')
    return fields[1] if len(fields) >= 2 else None


def activate():
    source = ROOT / 'media/alfie_media.py'
    staged_policy = ROOT / 'media/alfie_permissions.py'
    installed_policy = ROOT / 'task-permissions/alfie_permissions.py'
    compile(source.read_text(), 'alfie_media.py', 'exec')
    compile(staged_policy.read_text(), 'alfie_permissions.py', 'exec')
    live_policy = subprocess.check_output(
        ['docker', 'exec', 'alfie', 'cat', '/opt/hermes/alfie_permissions.py'])
    if live_policy != installed_policy.read_bytes():
        raise ValueError('Live task policy drift')
    subprocess.run(['python3', str(ROOT / 'deployment/prepare.py')], check=True)

    # Install the pinned, allowlisted STT dependency into Hermes's durable optional-package target.
    install = ('from tools.lazy_deps import ensure; '
               'ensure("stt.faster_whisper", prompt=False); '
               'import faster_whisper')
    subprocess.run(['docker', 'exec', '-u', '10000:10000', '-w', '/opt/hermes', 'alfie',
                    '/usr/bin/bash', '-lc', 'python -c ' + repr(install)], check=True)

    compose_path = ROOT / 'docker-compose.alfie.yml'
    compose = yaml.safe_load(compose_path.read_text())
    volumes = compose['services']['gateway'].setdefault('volumes', [])
    destination = '/opt/hermes/alfie_media.py'
    volumes[:] = [item for item in volumes if mount_destination(item) != destination]
    volumes.append(str(source) + ':' + destination + ':ro')
    volumes[:] = [item for item in volumes if mount_destination(item) != '/opt/alfie-media']
    staged = compose_path.with_suffix('.yml.media-next')
    staged.write_text(yaml.safe_dump(compose, sort_keys=False))
    staged.chmod(0o600)
    subprocess.run(['docker', 'compose', '-f', str(staged), 'config', '--quiet'], check=True)

    config_path = ROOT / 'data/config.yaml'
    config = configure_stt(yaml.safe_load(config_path.read_text()))
    staged_config = config_path.with_suffix('.yaml.media-next')
    staged_config.write_text(yaml.safe_dump(config, sort_keys=False))
    os.chown(staged_config, 10000, 10000)
    staged_config.chmod(0o600)

    lock = ROOT / 'deployment/maintenance.lock'
    with lock.open('x') as output:
        output.write('Media subsystem maintenance; failed cutover requires operator review.\n')
    subprocess.run(['docker', 'stop', 'alfie'], check=True, stdout=subprocess.DEVNULL)
    shutil.copyfile(staged_policy, installed_policy)
    installed_policy.chmod(0o644)
    shutil.move(staged, compose_path)
    shutil.move(staged_config, config_path)
    subprocess.run(['docker', 'compose', '-f', str(compose_path), 'up', '-d', '--no-build',
                    '--force-recreate', 'gateway'], check=True)
    # Remove the early WIP synthetic harness; real Telegram use is the integration signal.
    for obsolete in (ROOT / 'media/verify.py', ROOT / 'media/fixtures/spoken.wav.b64'):
        obsolete.unlink(missing_ok=True)
    lock.unlink()
    print('PASS media subsystem activated')


if __name__ == '__main__':
    activate()
