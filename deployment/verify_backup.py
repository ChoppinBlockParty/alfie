"""Read-only rollback-backup checks. Does not restore, decrypt, upload or print content."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3


def verify(backup):
    backup = Path(backup)
    if backup.is_symlink() or not backup.is_dir() or backup.stat().st_mode & 0o077:
        raise ValueError('Backup must be a private directory')
    required = ('opt/alfie/docker-compose.alfie.yml', 'opt/alfie/data/config.yaml',
                'opt/alfie/task-permissions/alfie_permissions.py',
                'opt/alfie/task-permissions/cron-policy.json', 'images.json')
    for name in required:
        if not (backup / name).is_file():
            raise ValueError('Required rollback artifact missing')
    runtime = backup / 'opt/alfie/task-permissions/runtime'
    manifest = json.loads((runtime / 'manifest.json').read_text())
    for name, hashes in manifest.items():
        path = runtime / name
        if not path.resolve().is_relative_to(runtime.resolve()) or path.is_symlink():
            raise ValueError('Unsafe overlay artifact path')
        if hashlib.sha256(path.read_bytes()).hexdigest() != hashes['patched']:
            raise ValueError('Overlay artifact digest mismatch')
        compile(path.read_text(), '<backup-overlay>', 'exec')
    count = 0
    for directory in ('opt/alfie/data/shared', 'opt/alfie/data/security'):
        for path in (backup / directory).glob('*'):
            if path.suffix not in ('.db', '.sqlite', '.sqlite3'):
                continue
            if path.is_symlink():
                raise ValueError('Unsafe database artifact')
            connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
            try:
                if connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise ValueError('Database integrity check failed')
            finally:
                connection.close()
            count += 1
    if not (backup / 'opt/alfie/data/security/pending-actions.sqlite').is_file():
        raise ValueError('Approval database backup missing')
    return {'overlay_files': len(manifest), 'sqlite_databases': count}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--latest', action='store_true', required=True)
    parser.parse_args()
    root = Path('/opt/alfie/backups').resolve()
    path = Path('/opt/alfie/deployment/last-backup').read_text().strip()
    if not Path(path).resolve().is_relative_to(root):
        raise SystemExit('FAIL backup reference outside backup root')
    try:
        result = verify(Path(path))
    except Exception:
        raise SystemExit('FAIL rollback backup verification; inspect privately') from None
    print('PASS rollback backup readability, overlay hashes and SQLite integrity', result)
    print('STATUS not a full restore rehearsal or complete off-host backup')
