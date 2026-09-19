import importlib.util,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('google_preflight','/opt/data/plugins/google_workspace/__init__.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
p.SCRIPT=Path('/opt/data/skills/productivity/google-workspace/scripts/google_api.py')
# Operator-only connector health probe. Model reads must use authenticated scope review.
result=p.run_google(['gmail','labels'])
try: payload=json.loads(result)
except ValueError: payload=None
if isinstance(payload,dict) and payload.get('error'):
 print('STATUS '+payload['error'])
elif payload:
 print('PASS fixed Google tool read-only labels; response contains',len(payload),'items')
else:
 print('FAIL Google tool returned no usable result')
 raise SystemExit(1)
