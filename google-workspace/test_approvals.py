import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import time
import uuid
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location('approval_plugin', Path(__file__).parent / 'gateway-plugin/__init__.py')
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)
store = plugin._approvals


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'private' / 'requests.sqlite'

    def test_writes_cannot_execute_even_with_forged_confirmation(self):
        with patch.object(store, 'STORE', self.path), patch.object(plugin, 'bounded_run') as execute:
            result = json.loads(plugin.google_workspace('gmail.send',
                {'to': 'recipient@example.com', 'subject': 'Review', 'body': 'Synthetic body'},
                approved=True, confirmed=True))
            self.assertEqual(result['status'], 'pending_approval')
            execute.assert_not_called()

    def test_every_write_operation_uses_the_queue(self):
        for operation, (positions, required, _) in plugin.OPERATIONS.items():
            if operation in plugin.READ_OPERATIONS:
                continue
            with self.subTest(operation=operation), patch.object(store, 'propose', return_value={}) as queue, \
                 patch.object(plugin, 'bounded_run') as execute:
                args = {key: 'fixture' for key in positions + required}
                if 'to' in args: args['to'] = 'recipient@example.com'
                if 'range' in args: args['range'] = 'A1:B2'
                if 'values' in args: args['values'] = '[["synthetic"]]'
                plugin.google_workspace(operation, args)
                queue.assert_called_once_with(operation, args)
                execute.assert_not_called()

    def test_identical_pending_action_is_deduplicated_but_not_changed_action(self):
        a = store.propose('gmail.send', {'body': 'a'}, path=self.path, now=10)
        b = store.propose('gmail.send', {'body': 'a'}, path=self.path, now=11)
        c = store.propose('gmail.send', {'body': 'b'}, path=self.path, now=11)
        self.assertEqual(a['request_id'], b['request_id'])
        self.assertNotEqual(a['digest'], c['digest'])
        self.assertEqual(a['expires_at'], b['expires_at'])

    def test_expiry_releases_capacity_and_does_not_reuse_request(self):
        with patch.object(store, 'MAX_PENDING', 1):
            first = store.propose('gmail.send', {'body': 'a'}, path=self.path, now=10)
            with self.assertRaises(ValueError):
                store.propose('gmail.send', {'body': 'b'}, path=self.path, now=11)
            second = store.propose('gmail.send', {'body': 'a'}, path=self.path, now=10 + store.TTL_S)
            self.assertNotEqual(first['request_id'], second['request_id'])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_storage_failure_never_falls_back_to_execution(self):
        with patch.object(store, 'propose', side_effect=sqlite3.OperationalError('fixture')), \
             patch.object(plugin, 'bounded_run') as execute:
            result = json.loads(plugin.google_workspace('calendar.delete', {'event_id': 'fixture'}))
            self.assertIn('error', result)
            execute.assert_not_called()

    def test_read_operations_require_authenticated_task_before_execution(self):
        import alfie_permissions as permissions
        token = permissions.CURRENT.set(permissions.Grant(uuid.uuid4().hex, 'email-read', '123', '123',
            'telegram', '10', 'Synthetic labels', time.time() + 60))
        self.addCleanup(permissions.CURRENT.reset, token)
        bridge = Mock()
        with patch.object(plugin, '_bridge', bridge), patch.object(plugin, 'bounded_run') as execute, patch.object(store, 'propose') as queue:
            execute.return_value.returncode = 0
            execute.return_value.stdout = '[]'
            self.assertEqual(plugin.google_workspace('gmail.labels', {}), '[]')
            queue.assert_not_called()
            execute.assert_called_once()


if __name__ == '__main__':
    unittest.main()
