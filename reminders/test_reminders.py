import importlib.util
import json
from dataclasses import replace
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'task-permissions'))
import alfie_permissions as policy

spec = importlib.util.spec_from_file_location('reminders_plugin', Path(__file__).parent / 'gateway-plugin/__init__.py')
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.grant = policy.Grant('task', 'reminder-write', '123', '-1001',
                                  'telegram', '1', 'Remind me', 99999999999)
        self.token = policy.CURRENT.set(self.grant)
        self.addCleanup(policy.CURRENT.reset, self.token)

    @staticmethod
    def job(**changes):
        value = {'id': 'job-1', 'name': policy.REMINDER_NAME + 'test',
                 'prompt': policy.REMINDER_PROMPT + 'test', 'deliver': 'origin',
                 'origin': {'platform': 'telegram', 'user_id': '123', 'chat_id': '-1001'},
                 'schedule': {'kind': 'at'}, 'schedule_display': 'in 1h', 'state': 'scheduled'}
        value.update(changes)
        return value

    def test_safe_shape_rejects_privileged_fields_and_other_owners(self):
        self.assertEqual(set(plugin.SCHEMA['parameters']['properties']['action']['enum']),
                         {'create', 'list', 'pause', 'resume'})
        self.assertTrue(policy.safe_reminder_job(self.job(), {'user': '123', 'chat': '-1001'}))
        for changes in ({'script': 'x.py'}, {'deliver': 'all'}, {'enabled_toolsets': ['web']},
                        {'origin': {'platform': 'telegram', 'user_id': '999', 'chat_id': '-1001'}},
                        {'prompt': 'web-read: do something'}):
            self.assertFalse(policy.safe_reminder_job(self.job(**changes), {'user': '123', 'chat': '-1001'}))

    def test_create_forces_tool_free_owner_delivery(self):
        cron = ModuleType('tools.cronjob_tools')
        calls = []
        cron.cronjob = lambda **kwargs: calls.append(kwargs) or json.dumps({'success': True})
        with patch.dict(sys.modules, {'tools.cronjob_tools': cron}):
            result = json.loads(plugin.reminder(action='create', text='Stretch', schedule='in 30m'))
        self.assertTrue(result['success'])
        self.assertEqual(calls[0]['deliver'], 'origin')
        self.assertEqual(calls[0]['enabled_toolsets'], [])
        self.assertTrue(calls[0]['prompt'].startswith(policy.REMINDER_PROMPT))

    def test_list_filters_and_mutations_require_exact_owned_id(self):
        jobs = ModuleType('cron.jobs')
        jobs.list_jobs = lambda include_disabled=True: [self.job(), self.job(id='foreign', deliver='all')]
        cron = ModuleType('tools.cronjob_tools')
        calls = []
        cron.cronjob = lambda **kwargs: calls.append(kwargs) or json.dumps({'success': True})
        with patch.dict(sys.modules, {'cron.jobs': jobs, 'tools.cronjob_tools': cron}):
            policy.CURRENT.set(replace(self.grant, mode='reminder-read'))
            listed = json.loads(plugin.reminder(action='list'))
            self.assertEqual([r['id'] for r in listed['reminders']], ['job-1'])
            policy.CURRENT.set(self.grant)
            self.assertIn('outside', json.loads(plugin.reminder(action='remove', job_id='job-1'))['error'])
            self.assertIn('not found', json.loads(plugin.reminder(action='pause', job_id='foreign'))['error'])
            self.assertTrue(json.loads(plugin.reminder(action='pause', job_id='job-1'))['success'])
        self.assertEqual(calls, [{'action': 'pause', 'job_id': 'job-1'}])


if __name__ == '__main__':
    unittest.main()
