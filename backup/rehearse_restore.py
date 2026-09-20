"""Offline recovery rehearsal on the Mac. Never starts services or calls account APIs.

Input is an authenticated, decrypted archive. Extract only regular SQLite/config/manifest
files into a NEW private directory; ignore symlinks and executable content. Exercise
approval invalidation against the recovered COPY, never the live VPS database.
"""
import argparse
import importlib.util
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tarfile

LIMIT = 5 * 1024 ** 3


def rehearse(archive, destination):
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    count, total = 0, 0
    with tarfile.open(archive, 'r|gz') as stream:
        for item in stream:
            total += max(item.size, 0)
            if total > LIMIT:
                raise ValueError('Recovery archive size limit exceeded')
            relative = PurePosixPath(item.name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe archive path')
            selected = item.name == 'recovery-manifest.json' or item.name in (
                'project/data/config.yaml', 'project/docker-compose.alfie.yml',
                'project/retired-cron-policy.json') or item.name.endswith(
                ('.db', '.db-wal', '.db-shm', '.sqlite', '.sqlite-wal', '.sqlite-shm', '.sqlite3'))
            if not selected:
                continue
            if not item.isfile() or item.size > 1024 ** 3:
                raise ValueError('Unexpected recovery artifact type/size')
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            source = stream.extractfile(item)
            with target.open('xb') as output:
                target.chmod(0o600)
                shutil.copyfileobj(source, output, length=1024 * 1024)
            count += 1
    manifest = json.loads((destination / 'recovery-manifest.json').read_text())
    assert manifest['version'] == 1 and len(manifest['services']) == 4
    databases = [p for p in destination.rglob('*') if p.suffix in ('.db', '.sqlite', '.sqlite3')]
    for path in databases:
        # Writable *offline copy* allows SQLite to recover committed WAL records.
        con = sqlite3.connect(path)
        try:
            if con.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise ValueError('Restored SQLite integrity check failed')
        finally:
            con.close()
    approval = destination / 'project/data/security/pending-actions.sqlite'
    if not approval.is_file():
        raise ValueError('Approval database missing')
    module_path = Path(__file__).resolve().parent.parent / 'google-workspace/gateway-plugin/approval_store.py'
    spec = importlib.util.spec_from_file_location('recovered_approval_store', module_path)
    store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(store)
    # Sentinel rows prove restored pending/executing actions cannot regain authority.
    with sqlite3.connect(approval) as con:
        for name, state in (('recovery-pending-fixture', 'pending'), ('recovery-executing-fixture', 'executing')):
            con.execute('INSERT INTO telegram_actions VALUES (?,?,?,?,?,?,?,?,?)',
                        (name, '{}', 'synthetic', '{}', 'synthetic', 'synthetic', 0, 1, state))
    store.restart(path=approval)
    with sqlite3.connect(approval) as con:
        assert con.execute("SELECT count(*) FROM telegram_actions WHERE status IN ('pending','presenting','executing')").fetchone()[0] == 0
        assert con.execute("SELECT status FROM telegram_actions WHERE id='recovery-pending-fixture'").fetchone()[0] == 'expired'
        assert con.execute("SELECT status FROM telegram_actions WHERE id='recovery-executing-fixture'").fetchone()[0] == 'unknown'
    return {'restored_artifacts': count, 'sqlite_databases': len(databases), 'approval_invalidation': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    parser.add_argument('destination')
    args = parser.parse_args()
    print('PASS offline restore rehearsal', rehearse(args.archive, args.destination))
    print('STATUS services not started; this is data recovery, not a replacement-host rebuild')
