"""Host operator: continuous worker-to-gateway deny probes across a firewall update.

Uses a temporary synthetic listener, no private data. Exercises the installed transactional
ruleset, not a permissive alternate policy. A passing sample is not proof of zero possible gap.
"""
import json
import subprocess
import time


def verify():
    listener_code = ('import socket,os,time; s=socket.socket(); '
                     's.bind(("0.0.0.0",18888)); s.listen(); print(os.getpid(),flush=True); time.sleep(25)')
    listener = subprocess.Popen(['docker', 'exec', '-u', '10000', 'alfie', 'python', '-c', listener_code],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    pid = listener.stdout.readline().strip()
    if not pid.isdigit():
        raise ValueError('Synthetic listener failed')
    probe_code = '''import socket,time,json
attempts=success=0
end=time.monotonic()+8
while time.monotonic()<end:
 attempts+=1
 try:
  s=socket.create_connection(('172.31.240.2',18888),timeout=.15);s.close();success+=1
 except OSError:pass
 time.sleep(.01)
print(json.dumps({'attempts':attempts,'unexpected_connections':success}))
'''
    probe = None
    try:
        subprocess.run(['docker', 'exec', 'alfie', 'python', '-c',
                        'import socket; socket.create_connection(("127.0.0.1",18888),timeout=2).close()'], check=True)
        probe = subprocess.Popen(['docker', 'exec', 'alfie-websearch', '/opt/venv/bin/python3', '-c', probe_code],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(1)
        subprocess.run(['/usr/local/sbin/alfie-docker-firewall.sh'], check=True, stdout=subprocess.DEVNULL)
        output, _ = probe.communicate(timeout=15)
        result = json.loads(output)
        if probe.returncode or result['attempts'] < 10 or result['unexpected_connections']:
            raise ValueError('Continuous deny probe failed')
        print('PASS worker-to-gateway denied across firewall update', result)
    finally:
        subprocess.run(['docker', 'exec', 'alfie', 'kill', '-TERM', pid],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        listener.wait(timeout=10)
        if probe and probe.poll() is None:
            probe.terminate()
            probe.wait(timeout=10)


if __name__ == '__main__':
    verify()
