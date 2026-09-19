#!/usr/bin/env python3
"""Run on VPS before staging. Back up config without sending its contents off-host."""
from pathlib import Path
import datetime
import json
import shutil
import subprocess
import sqlite3
from contextlib import closing

root=Path('/opt/alfie')
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup=root/'backups'/('four-container-'+stamp)
backup.mkdir(parents=True,mode=0o700)
backup.chmod(0o700)
paths=['/opt/alfie/docker-compose.alfie.yml','/opt/alfie/data/config.yaml',
       '/opt/alfie/data/scripts/email_watch.py',
       '/opt/alfie/data/scripts/email_watch_validation.py',
       '/opt/alfie/data/skills/personal/email-watch/SKILL.md',
       '/opt/alfie/data/skills/productivity/google-workspace/SKILL.md',
       '/usr/local/sbin/alfie-docker-firewall.sh']
for path in paths:
    src=Path(path)
    if src.exists():
        dst=backup/src.relative_to('/')
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
for path in ('/opt/alfie/data/plugins/websearch', '/opt/alfie/data/skills/personal/public-web-browser',
             '/opt/alfie/email-watch',
             '/opt/alfie/task-permissions',
             '/opt/alfie/google-workspace', '/opt/alfie/web-browser',
             '/opt/alfie/reminders',
             '/opt/alfie/websearch/gateway-plugin', '/opt/alfie/websearch/runtime'):
    src=Path(path)
    if src.exists(): shutil.copytree(src,backup/src.relative_to('/'),dirs_exist_ok=True)
for name in ('file_safety.py', 'credential_files.py'):
    src=root/'deployment'/name
    if src.exists():
        dst=backup/'opt/alfie/deployment'/name
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
# Consistent online snapshots include WAL commits; never copy a live SQLite file alone.
for directory in (root/'data/shared', root/'data/security'):
    if not directory.exists():
        continue
    for src in directory.iterdir():
        if src.is_file() and src.suffix in ('.db', '.sqlite', '.sqlite3'):
            dst=backup/src.relative_to('/')
            dst.parent.mkdir(parents=True,exist_ok=True)
            with closing(sqlite3.connect(src.as_uri()+'?mode=ro',uri=True)) as source:
                with closing(sqlite3.connect(dst)) as target:
                    source.backup(target)
            dst.chmod(0o600)
images={}
for name in ('alfie','alfie-sandbox','alfie-websearch','alfie-egress'):
    image=subprocess.check_output(['docker','inspect',name,'--format','{{.Image}}'],text=True).strip()
    tag=f'{name}-rollback:{stamp}'
    subprocess.run(['docker','tag',image,tag],check=True)
    images[name]=tag
(backup/'images.json').write_text(json.dumps(images,indent=2))
(root/'deployment'/'last-backup').write_text(str(backup))
print('Backup saved privately; location recorded in deployment/last-backup.')
