#!/usr/bin/env python3
"""Run on VPS: memory samples around a public browser session; no account data."""
import subprocess

CODE = """
import importlib.util,json
s=importlib.util.spec_from_file_location('b','/opt/data/plugins/web_browser/__init__.py')
p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
r=json.loads(p.browse(action='open',url='https://example.com'))
assert r['type']=='result'
print('OPEN',flush=True)
try: input()
finally:
 r=json.loads(p.browse(action='close',session_id=r['browser']['session_id']))
 assert r['browser']['closed']
 print('CLOSED',flush=True)
"""

def sample():
    subprocess.run(['docker','stats','--no-stream','--format','{{.Name}} {{.MemUsage}}'],check=True)

if __name__=='__main__':
    p=subprocess.Popen(['docker','exec','-i','-u','10000:10000','alfie',
                        '/opt/hermes/.venv/bin/python','-c',CODE],
                       stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        assert p.stdout.readline().strip()=='OPEN'
        print('Browser open sample',flush=True)
        sample()
    finally:
        if p.poll() is None:
            p.stdin.write('\n');p.stdin.flush()
            print(p.stdout.readline().strip(),flush=True)
        p.wait(timeout=60)
    assert p.returncode==0
    print('Browser closed sample',flush=True)
    sample()
