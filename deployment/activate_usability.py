"""Coordinated gateway cutover for natural routing and safe restored use cases.

Stage repository files and a freshly generated runtime overlay under
``/opt/alfie/deployment/usability-next``. Existing containers and images only.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import yaml

ROOT = Path('/opt/alfie')
STAGE = ROOT / 'deployment/usability-next'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def activate():
    old_root = ROOT / 'task-permissions/runtime'
    new_root = STAGE / 'task-permissions/runtime'
    old = json.loads((old_root / 'manifest.json').read_text())
    new = json.loads((new_root / 'manifest.json').read_text())
    if old.keys() != new.keys():
        raise ValueError('Runtime overlay target set changed')
    for name, hashes in old.items():
        if hashes['baseline'] != new[name]['baseline']:
            raise ValueError('Pinned Hermes source changed')
        if digest(old_root / name) != hashes['patched']:
            raise ValueError('Installed overlay file drift: ' + name)
        live = subprocess.check_output(['docker', 'exec', 'alfie', 'sha256sum',
                                        '/opt/hermes/' + name], text=True).split()[0]
        if live != hashes['patched']:
            raise ValueError('Live overlay drift: ' + name)
        if digest(new_root / name) != new[name]['patched']:
            raise ValueError('Staged overlay digest mismatch: ' + name)
        compile((new_root / name).read_text(), name, 'exec')

    replacements = (
        ('task-permissions/alfie_permissions.py', ROOT / 'task-permissions/alfie_permissions.py',
         '/opt/hermes/alfie_permissions.py'),
        ('task-permissions/live_acceptance.py', ROOT / 'task-permissions/live_acceptance.py', None),
        ('task-permissions/verify_runtime.py', ROOT / 'task-permissions/verify_runtime.py', None),
        ('task-permissions/verify_tool_surface.py', ROOT / 'task-permissions/verify_tool_surface.py', None),
        ('google-workspace/gateway-plugin/__init__.py', ROOT / 'google-workspace/gateway-plugin/__init__.py',
         '/opt/data/plugins/google_workspace/__init__.py'),
        ('google-workspace/gateway-plugin/read_scope.py', ROOT / 'google-workspace/gateway-plugin/read_scope.py',
         '/opt/data/plugins/google_workspace/read_scope.py'),
    )
    for relative, host, live in replacements:
        staged = STAGE / relative
        compile(staged.read_text(), relative, 'exec')
        if live and host.read_bytes() != subprocess.check_output(['docker', 'exec', 'alfie', 'cat', live]):
            raise ValueError('Live mounted code drift: ' + relative)
    reminder_stage = STAGE / 'reminders/gateway-plugin'
    compile((reminder_stage / '__init__.py').read_text(), 'reminders', 'exec')

    compose_path = ROOT / 'docker-compose.alfie.yml'
    compose = yaml.safe_load(compose_path.read_text())
    volumes = compose['services']['gateway'].setdefault('volumes', [])
    reminder_mount = '/opt/alfie/reminders/gateway-plugin:/opt/data/plugins/reminders:ro'
    volumes[:] = [item for item in volumes if not (isinstance(item, str)
                 and item.split(':')[1] == '/opt/data/plugins/reminders')]
    volumes.append(reminder_mount)
    compose_next = ROOT / 'docker-compose.alfie.yml.usability-next'
    compose_next.write_text(yaml.safe_dump(compose, sort_keys=False))
    compose_next.chmod(0o600)
    subprocess.run(['docker', 'compose', '-f', str(compose_next), 'config', '--quiet'], check=True)

    config_path = ROOT / 'data/config.yaml'
    config = yaml.safe_load(config_path.read_text())
    plugins = config.setdefault('plugins', {})
    if 'reminders' not in plugins.setdefault('enabled', []):
        plugins['enabled'].append('reminders')
    plugins['disabled'] = [name for name in plugins.get('disabled', []) if name != 'reminders']
    plugins.setdefault('entries', {})['reminders'] = {'allow_tool_override': False}
    for toolsets in config.get('platform_toolsets', {}).values():
        if isinstance(toolsets, list) and 'reminders' not in toolsets:
            toolsets.append('reminders')
    config_next = ROOT / 'data/config.yaml.usability-next'
    config_next.write_text(yaml.safe_dump(config, sort_keys=False))
    os.chown(config_next, 10000, 10000)
    config_next.chmod(0o600)

    subprocess.run(['python3', str(ROOT / 'deployment/prepare.py')], check=True)
    lock = ROOT / 'deployment/maintenance.lock'
    with lock.open('x') as output:
        output.write('Usability maintenance; failed cutover requires operator review.\n')
    subprocess.run(['docker', 'stop', 'alfie'], check=True, stdout=subprocess.DEVNULL)

    for relative, host, _ in replacements:
        host.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STAGE / relative, host)
        host.chmod(0o644)
    for name in new:
        shutil.copyfile(new_root / name, old_root / name)
        (old_root / name).chmod(0o644)
    shutil.copyfile(new_root / 'manifest.json', old_root / 'manifest.json')
    reminder_host = ROOT / 'reminders/gateway-plugin'
    reminder_host.mkdir(parents=True, exist_ok=True)
    for name in ('__init__.py', 'plugin.yaml'):
        shutil.copyfile(reminder_stage / name, reminder_host / name)
        (reminder_host / name).chmod(0o644)
    compose_next.replace(compose_path)
    config_next.replace(config_path)
    subprocess.run(['docker', 'compose', '-f', str(compose_path), 'up', '-d', '--no-build',
                    '--force-recreate', 'gateway'], check=True)
    lock.unlink()
    print('PASS natural routing, safe browser, private reads, memory, reminders and media activated')


if __name__ == '__main__':
    activate()
