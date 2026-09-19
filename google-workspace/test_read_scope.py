import json
import sys
from pathlib import Path
import time
import unittest
import uuid
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'task-permissions'))
import alfie_permissions as permissions
from test_approvals import plugin


class ReadScopeTests(unittest.TestCase):
    def setUp(self):
        self.gate = plugin._reads
        self.gate._states.clear()
        token = permissions.CURRENT.set(permissions.Grant(uuid.uuid4().hex, 'email-read', '123', '123',
            'telegram', '10', 'Find synthetic booking', time.time() + 60))
        self.addCleanup(permissions.CURRENT.reset, token)
        self.confirm = Mock(return_value=True)
        self.execute = Mock(return_value='[{"id":"selected"}]')

    def run_read(self, op='gmail.search', args=None):
        return self.gate.run(op, args if args is not None else {'query': 'booking'}, self.confirm, self.execute)

    def test_query_pinned_results_cached_and_only_returned_ids_readable(self):
        self.run_read()
        self.run_read()
        self.execute.assert_called_once_with('gmail.search', {'query': 'booking', 'max': 20})
        for op, args in [('gmail.search', {'query': 'password'}), ('gmail.get', {'message_id': 'unselected'}),
                         ('gmail.labels', {}), ('gmail.search', {'query': 'booking', 'max': 1})]:
            with self.assertRaises(ValueError): self.run_read(op, args)
        self.execute.return_value = '{"body":"synthetic"}'
        self.run_read('gmail.get', {'message_id': 'selected'})
        self.confirm.assert_called_once()

    def test_rejection_never_executes_or_represents(self):
        self.confirm.return_value = False
        for _ in range(2):
            with self.assertRaises(ValueError): self.run_read()
        self.execute.assert_not_called()
        self.confirm.assert_called_once()

    def test_malformed_results_do_not_grant_ids_and_cannot_retry(self):
        self.execute.return_value = '{"id":"selected"}'
        with self.assertRaises(ValueError): self.run_read()
        with self.assertRaises(ValueError): self.run_read('gmail.get', {'message_id': 'selected'})
        self.assertIn('error', self.run_read())
        self.execute.assert_called_once()

    def test_budget_expiry_and_cross_task(self):
        with self.assertRaises(ValueError): self.run_read(args={'query': 'booking', 'max': 100})
        self.run_read()
        with patch.object(self.gate, 'MAX_BYTES', 1), self.assertRaises(ValueError):
            self.run_read('gmail.get', {'message_id': 'selected'})
        old = permissions.current()
        token = permissions.CURRENT.set(permissions.Grant('different', 'email-read', old.owner, old.chat,
            'telegram', '11', 'Another task', time.time()+60))
        try:
            self.run_read('gmail.get', {'message_id': 'selected'})
            self.assertEqual(self.confirm.call_count, 2)
        finally:
            permissions.CURRENT.reset(token)

    def test_confirm_expiry_rechecked_before_fetch(self):
        self.confirm.side_effect = lambda *args: (setattr(self, 'expired', True) or True)
        with patch.object(permissions, 'current', side_effect=[permissions.current(), permissions.current(), permissions.Denied('expired')]):
            with self.assertRaises(permissions.Denied): self.run_read()
        self.execute.assert_not_called()


class ValidationTests(unittest.TestCase):
    def test_nested_sheet_values_and_bounded_ranges(self):
        for values in ('{}', '[[]]', '[[{}]]', '[[null]]', '[[NaN]]', '[[1e999]]', '[true]'):
            with self.subTest(values=values), self.assertRaises(ValueError):
                plugin.build_args('sheets.update', {'sheet_id':'fixture', 'range':'A1:B2','values':values})
        plugin.build_args('sheets.update', {'sheet_id':'fixture','range':'A1:B2','values':'[["=IMPORTXML(1)",true],[1,2]]'})
        for value in ('A:A', 'A1:Z1000', 'named_range', 'B2:A1'):
            with self.assertRaises(ValueError): plugin._validation.bounded_range(value)

    def test_invalid_addresses_and_changed_review_context_deny_execution(self):
        for value in ('not-an-address', 'a@example.com\nBcc:b@example.com', 'a@example.com, broken'):
            with self.assertRaises(ValueError): plugin._validation.addresses(value)
        with patch.object(plugin, 'review_context', return_value={'target':'changed'}), \
             patch.object(plugin, 'run_google') as execute, \
             patch.object(permissions, 'validate_approval'):
            with self.assertRaises(ValueError):
                plugin.execute_approved('docs.append', {'doc_id':'fixture','text':'synthetic'},
                    {'review_context': {'target':'reviewed'}})
            execute.assert_not_called()
