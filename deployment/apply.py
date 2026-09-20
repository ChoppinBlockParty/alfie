#!/usr/bin/env python3
"""Prepare declarative cutover files; no credential values printed."""
from pathlib import Path
import os
import shutil
import subprocess
import yaml
from sandbox_mounts import restricted_mounts

root=Path('/opt/alfie')
compose=root/'docker-compose.alfie.yml'
d=yaml.safe_load(compose.read_text())
s=d['services']
gateway=s['gateway']; sandbox=s['sandbox']; worker=s['websearch']; proxy=s['egress']
# Remove personal data from arbitrary execution; preserve the files on the host.
sandbox['volumes']=restricted_mounts(sandbox.get('volumes', []))
sandbox['mem_limit']='512m'
sandbox['memswap_limit']='512m'
worker.update(mem_limit='1280m',memswap_limit='1280m',pids_limit=256,shm_size='128m',cpus=1.5,
              tmpfs=['/tmp:rw,nosuid,nodev,size=384m,mode=1777'])
worker['security_opt']=['no-new-privileges:true','seccomp=/opt/alfie/web-browser/seccomp_profile.json']
# Allocate a distinct fixed bridge for the proxy's outward interface.
d['networks'].pop('alfie-egress', None)
d['networks']['alfie-egress-public']={'driver':'bridge','ipam':{'config':[{'subnet':'172.31.241.0/28'}]}}
proxy['networks'].pop('alfie-egress', None)
proxy['networks']['alfie-egress-public']={'ipv4_address':'172.31.241.2'}
mounts=[
 '/opt/alfie/email-watch/email_watch.py:/opt/data/scripts/email_watch.py:ro',
 '/opt/alfie/email-watch/email_watch_validation.py:/opt/data/scripts/email_watch_validation.py:ro',
 '/opt/alfie/email-watch/SKILL.md:/opt/data/skills/personal/email-watch/SKILL.md:ro',
 '/opt/alfie/google-workspace/scripts:/opt/alfie-google/scripts:ro',
 '/opt/alfie/google-workspace/scripts:/opt/data/skills/productivity/google-workspace/scripts:ro',
 '/opt/alfie/google-workspace/gateway-plugin:/opt/data/plugins/google_workspace:ro',
 '/opt/alfie/web-browser/gateway-plugin:/opt/data/plugins/web_browser:ro',
 '/opt/alfie/deployment/file_safety.py:/opt/hermes/agent/file_safety.py:ro',
 '/opt/alfie/deployment/credential_files.py:/opt/hermes/tools/credential_files.py:ro',
 '/opt/alfie/websearch/gateway-plugin:/opt/data/plugins/websearch:ro',
 '/opt/alfie/google-workspace/SKILL.md:/opt/data/skills/productivity/google-workspace/SKILL.md:ro',
 '/opt/alfie/web-browser/SKILL.md:/opt/data/skills/personal/public-web-browser/SKILL.md:ro',
]
vol=gateway.setdefault('volumes',[])
obsolete_destinations={'/opt/hermes/alfie_permissions.py','/opt/alfie-permissions/cron-policy.json',
                       '/opt/hermes/alfie_media.py','/opt/data/plugins/reminders'}
vol[:]=[v for v in vol if not (isinstance(v,str) and len(v.split(':')) >= 2 and
    (v.split(':')[0].startswith('/opt/alfie/task-permissions/') or
     v.split(':')[1] in obsolete_destinations))]
for relative in ('scripts/email_watch.py', 'scripts/email_watch_validation.py',
                 'skills/personal/email-watch/SKILL.md'):
    target=root/'data'/relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch(exist_ok=True)
    os.chown(target,10000,10000)
for mount in mounts:
    target=mount.split(':')[1]
    vol[:]=[v for v in vol if not (isinstance(v,str) and v.split(':')[1]==target)]
    vol.append(mount)
for path in ('plugins/google_workspace','plugins/web_browser','skills/personal/public-web-browser'):
    p=root/'data'/path;p.mkdir(parents=True,exist_ok=True);os.chown(p,10000,10000)
# An actual file target is needed for the single-file mount.
p=root/'data/skills/personal/public-web-browser/SKILL.md'
p.touch(exist_ok=True);os.chown(p,10000,10000)
# Base source comes from the running image, not a potentially different upstream checkout.
patched=root/'deployment/file_safety.py'
if not patched.exists():
    subprocess.run(['docker','cp','alfie:/opt/hermes/agent/file_safety.py',str(patched)],check=True)
text=patched.read_text()
marker='_CREDENTIAL_FILE_NAMES = ('
assert marker in text
if '"google_token.json", "google_client_secret.json", "google_oauth_pending.json",' not in text:
    text=text.replace(marker,marker+'\n    "google_token.json", "google_client_secret.json", "google_oauth_pending.json",',1)
patched.write_text(text);patched.chmod(0o644)
# All credential forwarding is forbidden, including future skill declarations/config.
# The source file is mounted read-only; skills/cache sync remains available.
forwarding=root/'deployment/credential_files.py'
if not forwarding.exists():
    subprocess.run(['docker','cp','alfie:/opt/hermes/tools/credential_files.py',str(forwarding)],check=True)
source=forwarding.read_text()
if '# Alfie: no credential forwarding' not in source:
    source += '\n\n# Alfie: no credential forwarding to agent execution environments.\n'
    source += 'def register_credential_file(relative_path, container_base="/root/.hermes"):\n    return False\n'
    source += 'def get_credential_file_mounts():\n    return []\n'
forwarding.write_text(source);forwarding.chmod(0o644)

config=root/'data/config.yaml'
c=yaml.safe_load(config.read_text())
c.setdefault('cron',{})['wrap_response']=False
c.setdefault('terminal',{})['credential_files']=[]
stt=c.setdefault('stt',{})
stt['enabled']=True
stt.setdefault('local',{}).update(model='base',language='en',vad=False,
                                  no_speech_prob_threshold=0.75,logprob_threshold=-1.3)
plugins=c.setdefault('plugins',{})
plugins.setdefault('enabled',[])[:]=[name for name in plugins.get('enabled',[]) if name!='reminders']
plugins.setdefault('disabled',[])[:]=[name for name in plugins.get('disabled',[]) if name!='reminders']
plugins.setdefault('entries',{}).pop('reminders',None)
for name in ('websearch','google_workspace','web_browser'):
    if name not in plugins.setdefault('enabled',[]): plugins['enabled'].append(name)
    plugins['disabled']=[x for x in plugins.get('disabled',[]) if x!=name]
    plugins.setdefault('entries',{})[name]={'allow_tool_override':False}
agent=c.setdefault('agent',{})
for name in ('browser','web'):
    if name not in agent.setdefault('disabled_toolsets',[]): agent['disabled_toolsets'].append(name)
for platform,toolsets in c.get('platform_toolsets',{}).items():
    if isinstance(toolsets,list):
        toolsets[:]=[name for name in toolsets if name!='reminders']
        for name in ('websearch','google_workspace','web_browser'):
            if name not in toolsets: toolsets.append(name)
# Replace on-host skill file as well; file_sync reads host-backed content inside gateway.
shutil.copyfile(root/'google-workspace/SKILL.md',root/'data/skills/productivity/google-workspace/SKILL.md')
os.chown(root/'data/skills/productivity/google-workspace/SKILL.md',10000,10000)
compose.with_suffix('.yml.next').write_text(yaml.safe_dump(d,sort_keys=False))
config.with_suffix('.yaml.next').write_text(yaml.safe_dump(c,sort_keys=False))
os.chown(config.with_suffix('.yaml.next'),10000,10000)
config.with_suffix('.yaml.next').chmod(0o600)
print('Prepared Compose/config and credential guard; activation is the next step.')
