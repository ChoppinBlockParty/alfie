"""Host operator: transfer only the most recent encrypted snapshot to pinned Drive folder.

No model tool or scheduled trigger. Keeps receipt private. Download is a read-back check;
it does not decrypt. Interrupted transfers require reconciliation before rerunning.
"""
import json
from pathlib import Path
import subprocess

ROOT = Path('/opt/alfie/backup')


def transfer():
    source = Path((ROOT / 'last-snapshot').read_text().strip())
    if not source.resolve().is_relative_to(Path('/opt/alfie/backups')) or source.name != 'snapshot.cms':
        raise ValueError('Unexpected snapshot path')
    # Gateway staging contains ciphertext only, never recovery private keys/plaintext.
    for local, remote in ((source, '/tmp/alfie-backup-upload.cms'),
                          (ROOT / 'drive-config.json', '/tmp/alfie-backup-config.json'),
                          (ROOT / 'drive_backup.py', '/tmp/alfie-drive-backup.py')):
        subprocess.run(['docker', 'cp', str(local), 'alfie:' + remote], check=True)
    base = ['docker', 'exec', '-w', '/opt/hermes', 'alfie', 'python', '/tmp/alfie-drive-backup.py']
    receipt = subprocess.check_output(base + ['upload', '--config', '/tmp/alfie-backup-config.json',
                                             '--file', '/tmp/alfie-backup-upload.cms'], timeout=1800)
    metadata = json.loads(receipt)
    target = source.parent / 'drive-receipt.json'
    target.write_bytes(receipt)
    target.chmod(0o600)
    subprocess.run(['docker', 'cp', str(target), 'alfie:/tmp/alfie-backup-receipt.json'], check=True)
    result = subprocess.check_output(base + ['download', '--config', '/tmp/alfie-backup-config.json',
        '--receipt', '/tmp/alfie-backup-receipt.json', '--file', '/tmp/alfie-backup-readback.cms'], timeout=1800)
    assert json.loads(result)['verified'] is True
    subprocess.run(['docker', 'cp', 'alfie:/tmp/alfie-backup-readback.cms', str(source.parent / 'readback.cms')], check=True)
    # Remove only this tool's explicit staging files after verification. Host ciphertext retained.
    subprocess.run(['docker', 'exec', 'alfie', 'python', '-c',
        "from pathlib import Path; [Path(p).unlink(missing_ok=True) for p in "
        "('/tmp/alfie-backup-upload.cms','/tmp/alfie-backup-readback.cms',"
        "'/tmp/alfie-backup-config.json','/tmp/alfie-backup-receipt.json')]"], check=True)
    print('PASS encrypted backup uploaded and downloaded; size and digest verified; staging removed')
    print('STATUS encrypted_bytes', metadata['size'])


if __name__ == '__main__':
    transfer()
