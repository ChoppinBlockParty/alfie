import importlib.util
from pathlib import Path
import unittest
import json
import sys
import time
import os
import subprocess
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'task-permissions'))
import alfie_permissions as permissions
spec = importlib.util.spec_from_file_location('google_plugin', Path(__file__).parent/'gateway-plugin/__init__.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
class BoundaryTests(unittest.TestCase):
    def test_bounded_process_success_timeout_and_output_limit(self):
        env = {'PATH': '/usr/bin:/bin'}
        result = p.bounded_run([sys.executable, '-c', 'print("synthetic")'], env)
        self.assertEqual(result.stdout.strip(), 'synthetic')
        with self.assertRaises(ValueError):
            p.bounded_run([sys.executable, '-c', 'print("x" * 100000)'], env, limit=1024)
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            p.bounded_run([sys.executable, '-c', 'import time; time.sleep(30)'], env, timeout=.1)
        self.assertLess(time.monotonic() - started, 3)

    @unittest.skipUnless(hasattr(os, 'fork'), 'POSIX process groups required')
    def test_timeout_kills_descendant_holding_output_pipe(self):
        started = time.monotonic()
        code = 'import os,time; pid=os.fork(); time.sleep(30) if pid==0 else None'
        with self.assertRaises(subprocess.TimeoutExpired):
            p.bounded_run([sys.executable, '-c', code], {'PATH': '/usr/bin:/bin'}, timeout=.1)
        self.assertLess(time.monotonic() - started, 3)

    def setUp(self):
        token = permissions.CURRENT.set(permissions.Grant('fixture', 'drive.create-folder', '123', '123',
                                                        'telegram', '10', 'Synthetic task', time.time() + 60))
        self.addCleanup(permissions.CURRENT.reset, token)
    def test_registered_handler_accepts_runtime_argument_envelope(self):
        ctx = Mock()
        p.register(ctx)
        handler = ctx.register_tool.call_args.kwargs['handler']
        bridge = Mock()
        bridge.propose.return_value = {'status': 'pending_approval'}
        with patch.object(p, '_bridge', bridge), patch.object(p, 'run_google') as execute:
            result = json.loads(handler({'operation': 'drive.create-folder',
                                        'arguments': {'name': 'Synthetic approval test'}}, task_id='fixture'))
            self.assertEqual(result['status'], 'pending_approval')
            bridge.propose.assert_called_once_with('drive.create-folder', {'name': 'Synthetic approval test'})
            execute.assert_not_called()

    def test_invalid_envelopes_fail_closed(self):
        for args in (None, [], {}, {'operation': {}, 'arguments': {}},
                     {'operation': 'gmail.labels', 'arguments': {}, 'approved': True}):
            with self.subTest(args=args), patch.object(p, 'run_google') as execute:
                self.assertIn('error', json.loads(p.tool_handler(args)))
                execute.assert_not_called()

    def test_no_arbitrary_file_or_command(self):
        for op,args in [('drive.upload', {'path':'/opt/data/auth.json'}), ('gmail.get',{'message_id':'--help'}),
                        ('gmail.search',{'query':'x','path':'/opt/data/.env'}), ('gmail.search',{'query':'x','max':True})]:
            with self.assertRaises(ValueError): p.build_args(op,args)
    def test_option_value_cannot_inject(self):
        self.assertEqual(p.build_args('gmail.send',{'to':'a@example.com','subject':'--help','body':'$(id)'}),
                         ['gmail','send','--to=a@example.com','--subject=--help','--body=$(id)'])
    def test_read_and_boolean(self):
        self.assertEqual(p.build_args('gmail.search',{'query':'booking','max':5}),['gmail','search','booking','--max=5'])
        with self.assertRaises(ValueError): p.build_args('gmail.send', {'to':'x','subject':'x','body':'x','html':'false'})
if __name__ == '__main__': unittest.main()
