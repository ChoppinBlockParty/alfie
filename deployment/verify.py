#!/usr/bin/env python3
"""Run on VPS. Public fixtures and status/counts only; never print credentials/mail."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(container, code, *, gateway=False, timeout=120):
    command=['docker','exec','-i','-u','10000:10000',container]
    command += (['/usr/bin/bash','-lc','python -'] if gateway else
                ['python3','-'] if container=='alfie-sandbox' else ['/opt/venv/bin/python3','-'])
    result=subprocess.run(command,input=code,text=True,capture_output=True,timeout=timeout)
    if result.returncode:
        # Tracebacks from API libraries may include private details. Print only a controlled marker.
        print('FAIL',container,'verification process exit',result.returncode)
        for line in result.stdout.splitlines():
            if line.startswith(('PASS ', 'FAIL ', 'STATUS ')): print(line)
        return False
    for line in result.stdout.splitlines():
        if line.startswith(('PASS ', 'FAIL ', 'STATUS ')): print(line)
    return True

GATEWAY = r'''
import importlib.util,json,os,pathlib,socket,threading
from hermes_cli.plugins import discover_plugins
from tools.registry import registry

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def check(name,condition):
 print(('PASS ' if condition else 'FAIL ')+name,flush=True)
 if not condition: raise RuntimeError(name)

discover_plugins()
for toolset,tool in [('google_workspace','google_workspace'),('web_browser','browse'),
                     ('websearch','research'),('reminders','reminder')]:
 check('registered '+tool,tool in registry.get_tool_names_for_toolset(toolset))
from agent.file_safety import get_read_block_error
from tools.credential_files import register_credential_file,get_credential_file_mounts
for name in ('google_token.json','google_client_secret.json','auth.json','.env'):
 check('read guard '+name,bool(get_read_block_error('/opt/data/'+name)))
 check('sync refused '+name,not register_credential_file(name))
check('credential forwarding disabled',get_credential_file_mounts()==[])
from tools.code_execution_tool import _get_or_create_env
env,kind=_get_or_create_env('four-container-acceptance')
check('real Hermes backend SSH',kind=='ssh' and type(env).__name__=='SSHEnvironment')
result=env.execute("python3 -c 'from pathlib import Path; paths=[Path(\"/opt/data/.env\"),Path(\"/opt/data/auth.json\"),Path.home()/\".hermes/google_token.json\",Path.home()/\".hermes/google_client_secret.json\",Path(\"/var/run/docker.sock\")]; print(\"CLEAN\" if not any(p.exists() for p in paths) else \"EXPOSED\")'")
check('sandbox credentials absent through Hermes', 'CLEAN' in str(result) and 'EXPOSED' not in str(result))
google=load('google_acceptance','/opt/data/plugins/google_workspace/__init__.py')
from unittest.mock import patch
with patch.object(google, 'bounded_run', side_effect=AssertionError('write attempted execution')), \
     patch.object(google._approvals, 'propose', return_value={'status':'pending_approval'}):
 result=json.loads(google.google_workspace('calendar.delete', {'event_id':'synthetic-fixture'}, approved=True))
 check('Google mutations cannot bypass pending review',result.get('status')=='pending_approval')
result=json.loads(google.google_workspace('gmail.labels',{}))
check('Google private read denied without owner scope',bool(result.get('error')))
# Explicit operator health probe of the fixed CLI, not a model task or scope bypass.
result=google.run_google(['gmail','labels'])
try: payload=json.loads(result)
except ValueError: payload={}
if isinstance(payload,dict) and payload.get('error'):
 check('Operator Google labels health read succeeds',False)
else:
 check('Operator Google labels health read succeeds',bool(payload))
# Native web/browser must be disabled while custom plugin toolsets remain enabled.
import yaml
config=yaml.safe_load(pathlib.Path('/opt/data/config.yaml').read_text())
check('native gateway web/browser disabled',{'web','browser'} <= set(config['agent']['disabled_toolsets']))
from cron.jobs import list_jobs
jobs=[j for j in list_jobs(include_disabled=True) if j.get('name')=='email-watch']
check('email-watch remains no_agent',len(jobs)==1 and jobs[0].get('no_agent') is True)
# Import the actual deployed script and ensure its legacy timezone command has no effect.
import sys
sys.path.insert(0,'/opt/data/scripts')
watch=load('watch_acceptance','/opt/data/scripts/email_watch.py')
check('email-watch report-only implementation installed',
      hasattr(watch,'validate_results') and not hasattr(watch,'ensure_event'))
before=watch.USER_MD.read_bytes() if watch.USER_MD.exists() else None
check('email-watch automatic timezone updates disabled',watch.update_zone() is None)
after=watch.USER_MD.read_bytes() if watch.USER_MD.exists() else None
check('email-watch preserves owner context',before==after)
'''

SANDBOX = r'''
import socket,urllib.request,urllib.error
def check(name,condition):
 print(('PASS ' if condition else 'FAIL ')+name,flush=True)
 if not condition: raise RuntimeError(name)
opener=urllib.request.build_opener(urllib.request.ProxyHandler({'http':'http://172.31.240.5:3128'}))
for url in ('http://example.com','http://google.com','http://169.254.169.254'):
 try: response=opener.open(url,timeout=15); status=response.status
 except urllib.error.HTTPError as exc: status=exc.code
 check('sandbox proxy refuses '+url,status==403)
# CONNECT response proves proxy policy permits the model endpoint; no token is sent.
with socket.create_connection(('172.31.240.5',3128),timeout=15) as s:
 s.sendall(b'CONNECT chatgpt.com:443 HTTP/1.1\r\nHost: chatgpt.com:443\r\n\r\n')
 check('sandbox proxy permits model endpoint',b' 200 ' in s.recv(1024).split(b'\r\n')[0])
for host,port in [('172.31.240.4',8770),('172.31.240.1',22),('1.1.1.1',443)]:
 try: s=socket.create_connection((host,port),timeout=1);s.close();blocked=False
 except OSError: blocked=True
 check('sandbox direct blocked '+host+':'+str(port),blocked)
'''

WORKER = r'''
import httpx,socket,ssl,os,pathlib

def check(name,condition):
 print(('PASS ' if condition else 'FAIL ')+name,flush=True)
 if not condition: raise RuntimeError(name)
proxy='http://172.31.240.5:3128'
with httpx.Client(proxy=proxy,trust_env=False,timeout=15) as c:
 r=c.get('https://example.com');check('public HTTPS via proxy',r.status_code==200)
 for url in ('http://127.0.0.1','http://169.254.169.254/latest/meta-data/',
             'http://172.31.240.2','http://@@ALFIE_PUBLIC_IPV4@@','http://localtest.me'):
  r=c.get(url);check('proxy refuses '+url,r.status_code==403)
for host,port in [('172.31.240.2',18888),('172.31.240.3',2222),('172.31.240.1',22),('@@ALFIE_PUBLIC_IPV4@@',22),('1.1.1.1',443)]:
 try:
  s=socket.create_connection((host,port),timeout=1);s.close();blocked=False
 except OSError: blocked=True
 check('direct blocked '+host+':'+str(port),blocked)
check('no gateway home or Docker socket',not pathlib.Path('/opt/data').exists() and not pathlib.Path('/var/run/docker.sock').exists())
# Proxy proves reachability separately; local TLS handshake without a client identity must fail.
ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.load_verify_locations('/etc/websearch/ca.crt')
try:
 with ctx.wrap_socket(socket.create_connection(('127.0.0.1',8770),timeout=3),server_hostname='websearch') as s:
  s.sendall(b'GET / HTTP/1.1\r\nHost: websearch\r\n\r\n');data=s.recv(100)
  refused=not data
except (ssl.SSLError,OSError): refused=True
check('worker refuses caller without mTLS certificate',refused)
'''

BROWSER = r'''
import importlib.util,json
spec=importlib.util.spec_from_file_location('browser_acceptance','/opt/data/plugins/web_browser/__init__.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
print('STATUS browser script started',flush=True)
def call(**args):
 raw=p.browse(**args)
 try: return json.loads(raw)
 except Exception as exc:
  print('STATUS browser decode: '+type(exc).__name__+' output_type='+type(raw).__name__,flush=True)
  raise
def check(name,value):
 print(('PASS ' if value else 'FAIL ')+name,flush=True)
 if not value: raise RuntimeError(name)
try: r=call(action='open',url='https://example.com')
except Exception as exc:
 print('STATUS browser open exception: '+type(exc).__name__+' '+str(exc)[:200],flush=True)
 raise
if r.get('type')!='result':
 print('STATUS browser open: '+str({k:r.get(k) for k in ('type','code','detail','error','kind')}),flush=True)
check('browser open public page',r.get('type')=='result' and 'Example Domain' in r.get('browser',{}).get('text',''))
sid=r['browser']['session_id']
try:
 foreign=call(action='close',session_id='foreign')
 check('foreign session cannot close browser',foreign.get('code')=='busy')
 snap=call(action='snapshot',session_id=sid)
 check('owner session survives foreign call',snap.get('type')=='result')
 import asyncio,ssl,uuid,websockets
 async def busy():
  ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);ctx.minimum_version=ssl.TLSVersion.TLSv1_2
  ctx.load_verify_locations(p.CA);ctx.load_cert_chain(p.CERT,p.KEY)
  ctx.check_hostname=True;ctx.verify_mode=ssl.CERT_REQUIRED
  async with websockets.connect('wss://172.31.240.4:8770',ssl=ctx,server_hostname='websearch') as ws:
   await ws.send(json.dumps({'type':'ask','id':uuid.uuid4().hex,'question':'test'}))
   return json.loads(await ws.recv())
 check('research refused while browser owns worker',asyncio.run(busy()).get('code')=='busy')
finally:
 check('browser close',call(action='close',session_id=sid).get('browser',{}).get('closed') is True)
r=call(action='open',url='https://books.toscrape.com/')
check('public book catalogue',r.get('type')=='result' and 'Books to Scrape' in r['browser']['title'])
sid=r['browser']['session_id']
try:
 link=next(e for e in r['browser']['elements'] if e.get('href','').endswith('travel_2/index.html'))
 clicked=call(action='click',session_id=sid,ref=link['ref'])
 check('browser click navigates',clicked.get('type')=='result' and 'travel_2' in clicked['browser']['url'])
 back=call(action='back',session_id=sid)
 check('browser back',back.get('type')=='result' and 'travel_2' not in back['browser']['url'])
finally: call(action='close',session_id=sid)
r=call(action='open',url='http://169.254.169.254/latest/meta-data/')
check('browser metadata URL refused',r.get('type')=='error')
r=call(action='open',url='https://httpbin.org/redirect-to?url=http%3A%2F%2F169.254.169.254%2Flatest%2Fmeta-data%2F')
if r.get('type')=='result': call(action='close',session_id=r['browser']['session_id'])
check('browser public-to-metadata redirect refused',r.get('type')=='error')
# Harmless public demonstration form: fill only, never submit or enter personal data.
r=call(action='open',url='https://httpbin.org/forms/post')
check('public demo form opens',r.get('type')=='result')
sid=r['browser']['session_id']
try:
 element=next(e for e in r['browser']['elements'] if e.get('tag')=='textarea')
 result=call(action='fill',session_id=sid,ref=element['ref'],value='Public browser test; no order requested')
 check('browser fill',result.get('type')=='result')
finally: call(action='close',session_id=sid)
'''

RESEARCH = r'''
import importlib.util
spec=importlib.util.spec_from_file_location('research_acceptance','/opt/data/plugins/websearch/__init__.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
text=p._research('What is the purpose of the example.com domain? Cite IANA.', 'quick')
failed=text.startswith(('research:', 'research failed'))
print(('FAIL ' if failed else 'PASS ')+'research end-to-end; output_chars='+str(len(text)),flush=True)
if failed: raise RuntimeError('research unavailable')
'''

def main():
    if '@@' in '@@ALFIE_PUBLIC_IPV4@@':
        raise SystemExit('Run the rendered verify.py installed by deployment/deploy.sh')
    parser=argparse.ArgumentParser();parser.add_argument('--research',action='store_true');args=parser.parse_args()
    inspections=json.loads(subprocess.check_output(['docker','inspect','alfie','alfie-sandbox','alfie-websearch','alfie-egress']))
    for item in inspections:
        mounts=item['Mounts'];assert all('docker.sock' not in m['Source'] for m in mounts)
        assert not item['HostConfig']['Privileged']
        assert item['State']['Running']
    worker=next(x for x in inspections if x['Name']=='/alfie-websearch')
    assert worker['HostConfig']['Memory']==worker['HostConfig']['MemorySwap']==1280*1024*1024
    assert worker['HostConfig']['ReadonlyRootfs']
    print('PASS four running containers; no Docker socket; worker RAM/no-swap/read-only controls')
    if Path('/etc/systemd/system/alfie-boot-gate.service').exists():
        from boot_gate import check_policies
        check_policies(inspections)
        for unit in ('alfie-docker-firewall.service', 'alfie-boot-gate.service'):
            subprocess.run(['systemctl', 'is-active', '--quiet', unit], check=True)
        def timestamp(unit, field):
            return int(subprocess.check_output(['systemctl', 'show', unit, '-p', field, '--value'], text=True).strip())
        firewall_done=timestamp('alfie-docker-firewall.service', 'ExecMainExitTimestampMonotonic')
        gate_started=timestamp('alfie-boot-gate.service', 'ExecMainStartTimestampMonotonic')
        assert 0 < firewall_done <= gate_started, 'Firewall must complete before boot gate starts containers'
        print('PASS bounded crash retries and verified firewall-before-container boot ordering')
    from sandbox_mounts import restricted_mounts
    sandbox=next(item for item in inspections if item['Name']=='/alfie-sandbox')
    mounts=[{'source':m['Source'],'target':m['Destination'],'read_only':not m['RW']}
            for m in sandbox['Mounts']]
    assert restricted_mounts(mounts)==mounts, 'Sandbox still exposes personal data or writable code'
    print('PASS sandbox personal-data mounts removed and code mounts read-only')
    ok=run('alfie',GATEWAY,gateway=True)
    ok=run('alfie-sandbox',SANDBOX) and ok
    # Listener proves worker denial is a filter, not merely absence of a listening service.
    listener=subprocess.Popen(['docker','exec','-u','10000','alfie','/opt/hermes/.venv/bin/python','-c',
      'import socket,time,os; s=socket.socket(); s.bind(("0.0.0.0",18888)); s.listen(); print(os.getpid(),flush=True); time.sleep(90)'],stdout=subprocess.PIPE,text=True)
    pid=listener.stdout.readline().strip()
    try:
        assert pid.isdigit()
        ok=run('alfie-websearch',WORKER) and ok
    finally:
        if pid.isdigit():
            subprocess.run(['docker','exec','alfie','kill','-TERM',pid],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        listener.wait(timeout=10)
    ok=run('alfie',BROWSER,gateway=True,timeout=240) and ok
    if args.research: ok=run('alfie',RESEARCH,gateway=True,timeout=350) and ok
    return 0 if ok else 1
if __name__=='__main__':sys.exit(main())
