"""Host operator recovery snapshot. Briefly stops only the gateway; never runs via agent tools.

Includes persistent project state and the sandbox host-key volume; excludes rebuildable
caches and existing backups. Container images are recorded, not exported. Plaintext archive
remains root-only until encryption succeeds; no automatic deletion on encryption failure.
"""
import datetime
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time

from crypto import transform

ROOT = Path('/opt/alfie')
EXCLUDED = ('backups', 'hermes-agent/.git', 'data/cache', 'data/.cache',
            'data/.npm', 'data/lazy-packages', 'data/lsp', 'data/logs', 'data/backups',
            'data/tmp', 'data/tmp_email_watch')
MAX_INPUT = 5 * 1024 ** 3


def snapshot():
    if os.geteuid() != 0:
        raise ValueError('Host root operator required')
    if shutil.disk_usage(ROOT).free < 7 * 1024 ** 3:
        raise ValueError('Insufficient recovery snapshot headroom')
    state = json.loads(subprocess.check_output(['docker', 'inspect', 'alfie', 'alfie-sandbox',
                                               'alfie-websearch', 'alfie-egress'], text=True))
    if not all(item['State']['Running'] for item in state):
        raise ValueError('Expected all services running before maintenance')
    external = [mount for item in state for mount in item['Mounts']
                if not Path(mount['Source']).is_relative_to(ROOT)]
    if len(external) != 1 or external[0]['Type'] != 'volume' or external[0]['Destination'] != '/etc/ssh/keys':
        raise ValueError('Unexpected external mount; inspect before snapshot')
    certificate = ROOT / 'backup/recipient.cert.pem'
    if not certificate.is_file():
        raise ValueError('Public recovery certificate missing')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = ROOT / 'backups' / ('encrypted-recovery-' + stamp)
    target.mkdir(mode=0o700, parents=True)
    source, encrypted = target / 'snapshot.tar.gz', target / 'snapshot.cms'
    manifest = {'version': 1, 'created': stamp, 'excluded': EXCLUDED,
                'services': [{'name': item['Name'], 'image': item['Image'],
                              'mounts': item['Mounts']} for item in state],
                'warning': 'Container images and excluded caches require re-provisioning. Invalidate approvals before any restored writer starts.'}
    started, total = time.monotonic(), 0

    def include(info):
        nonlocal total
        if info.name.startswith('project/'):
            relative = info.name[len('project/'):]
            if any(relative == name or relative.startswith(name + '/') for name in EXCLUDED):
                return None
        if info.isdev() or info.isfifo():
            return None
        total += info.size
        if total > MAX_INPUT or time.monotonic() - started > 600:
            raise ValueError('Snapshot size/time budget exceeded')
        return info

    subprocess.run(['docker', 'stop', 'alfie'], check=True, stdout=subprocess.DEVNULL)
    try:
        with source.open('xb') as output:
            source.chmod(0o600)
            with tarfile.open(fileobj=output, mode='w|gz', compresslevel=1) as archive:
                data = json.dumps(manifest, sort_keys=True).encode()
                header = tarfile.TarInfo('recovery-manifest.json')
                header.size, header.mode = len(data), 0o600
                archive.addfile(header, io.BytesIO(data))
                archive.add(ROOT, arcname='project', filter=include)
                archive.add(external[0]['Source'], arcname='sandbox-hostkeys', filter=include)
                archive.add('/usr/local/sbin/alfie-docker-firewall.sh', arcname='host/alfie-docker-firewall.sh', filter=include)
    finally:
        subprocess.run(['docker', 'start', 'alfie'], check=True, stdout=subprocess.DEVNULL)
    transform(source, encrypted, certificate)
    # Only the task-created plaintext is removed, after authenticated encryption succeeds.
    source.unlink()
    (ROOT / 'backup/last-snapshot').write_text(str(encrypted))
    (ROOT / 'backup/last-snapshot').chmod(0o600)
    print('PASS encrypted recovery snapshot created; gateway restarted; plaintext staging removed')


if __name__ == '__main__':
    snapshot()
