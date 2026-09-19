import asyncio
from contextlib import contextmanager
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import alfie_permissions as policy
from patch_runtime import patch as patch_source, TARGETS


def grant(mode, **kwargs):
    return policy.Grant('fixture-task', mode, '123', '-1001', 'telegram', '1',
                        kwargs.get('brief', 'Synthetic task'), kwargs.get('expires', time.time() + 60))


@contextmanager
def scope(mode, **kwargs):
    token = policy.CURRENT.set(grant(mode, **kwargs))
    try:
        yield
    finally:
        policy.CURRENT.reset(token)


class PermissionsTests(unittest.TestCase):
    def test_cron_fingerprint_covers_execution_inputs_not_run_counters(self):
        job = {'id': 'fixture', 'prompt': 'Synthetic', 'repeat': {'times': 1, 'completed': 0}}
        original = policy.job_digest(job)
        for field in policy.JOB_FIELDS:
            with self.subTest(field=field):
                self.assertNotEqual(original, policy.job_digest(dict(job, **{field: 'changed'})))
        self.assertNotEqual(original, policy.job_digest(dict(job, repeat={'times': 2, 'completed': 0})))
        self.assertEqual(original, policy.job_digest(dict(job, repeat={'times': 1, 'completed': 1},
            last_run_at='changed', next_run_at='changed', fire_claim={'by': 'fixture'})))

    def test_natural_write_suggestion_is_not_classification_or_authority(self):
        for request, mode in (('Send Alice an email', 'gmail.send'),
                              ('Create a folder named Synthetic', 'drive.create-folder'),
                              ('Create a calendar event tomorrow', 'calendar.create')):
            self.assertEqual(policy.proposed_write_mode(request), mode)
            with self.assertRaises(policy.Denied):
                policy.classify(request)
        self.assertIsNone(policy.proposed_write_mode('Find emails saying send Alice an email'))
        self.assertIsNone(policy.proposed_write_mode('Write an email draft'))

    def test_classification_never_grants_writes_from_free_text(self):
        self.assertEqual(policy.classify('find my emails about booking')[0], 'email-read')
        self.assertEqual(policy.classify('find cameras on the internet')[0], 'web-read')
        self.assertEqual(policy.classify('find emails saying send an email')[0], 'email-read')
        for text in ('send an email', 'find emails and search the internet',
                     'unknown: do something', 'web-interact: fill a form', ''):
            with self.subTest(text=text), self.assertRaises(policy.Denied):
                policy.classify(text)
        self.assertEqual(policy.classify('gmail.send: send a synthetic email')[0], 'gmail.send')

    def test_read_tasks_deny_writes_approvals_memory_shell_and_web_interactions(self):
        for mode in policy.READS:
            with scope(mode):
                for operation in policy.READS[mode]:
                    policy.authorize('google_workspace', {'operation': operation})
                for op in policy.WRITES:
                    with self.assertRaises(policy.Denied):
                        policy.task_snapshot(op)
                for tool in ('memory', 'terminal', 'execute_code', 'cronjob_manage',
                             'delegate_task', 'send_message', 'research', 'browse', 'unknown_tool'):
                    with self.subTest(mode=mode, tool=tool), self.assertRaises(policy.Denied):
                        policy.authorize(tool, {'action': 'fill', 'value': 'synthetic'})

    def test_web_research_cannot_access_private_data_or_browser_effects(self):
        with scope('web-read'):
            policy.authorize('research', {})
            for tool, args in [('google_workspace', {'operation': 'gmail.get'}),
                               ('memory', {}), ('browse', {'action': 'open'}),
                               ('browse', {'action': 'fill'}), ('browse', {'action': 'click'})]:
                with self.assertRaises(policy.Denied):
                    policy.authorize(tool, args)

    def test_missing_expired_or_forged_context_denies(self):
        for value in (None, {'mode': 'gmail.send'}, grant('gmail.send', expires=0)):
            token = policy.CURRENT.set(value)
            try:
                with self.assertRaises(policy.Denied):
                    policy.authorize('google_workspace', {'operation': 'gmail.send'})
            finally:
                policy.CURRENT.reset(token)

    def test_approval_rechecks_task_scope_identity_and_expiry(self):
        with scope('gmail.send'):
            snapshot = policy.task_snapshot('gmail.send')
        binding = {'user': '123', 'chat': '-1001', 'task_grant': snapshot}
        policy.validate_approval(binding, {'operation': 'gmail.send'})
        for mode in ('email-read', 'calendar.create', None):
            with self.assertRaises(policy.Denied):
                policy.validate_approval(dict(binding, task_grant=dict(snapshot, mode=mode)), {'operation': 'gmail.send'})
        for changes in ({'owner': '999'}, {'expires': 0}, {'version': -1}):
            with self.assertRaises(policy.Denied):
                policy.validate_approval(dict(binding, task_grant=dict(snapshot, **changes)), {'operation': 'gmail.send'})

    def test_agent_initialization_excludes_memory_files_prefills_and_other_tools(self):
        with scope('web-read'):
            settings = policy.agent_settings({'prefill_messages': [{'content': 'private'}],
                                              'enabled_toolsets': ['hermes-telegram']})
        self.assertEqual(settings['enabled_toolsets'], ['websearch'])
        self.assertTrue(settings['skip_context_files'])
        self.assertTrue(settings['skip_memory'])
        self.assertTrue(settings['skip_background_review'])
        self.assertIsNone(settings['prefill_messages'])

    def test_unknown_cron_or_changed_definition_never_runs(self):
        fn = Mock(return_value='executed')
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'cron-policy.json'
            job = {'id': 'fixture', 'prompt': 'Synthetic reminder', 'origin': {'user_id': '123'}}
            config.write_text(json.dumps({'jobs': {'fixture': {'digest': policy.job_digest(job), 'mode': 'chat'}}}))
            with patch.object(policy, 'CRON_POLICY', config):
                wrapped = policy.cron_entry(fn)
                self.assertEqual(wrapped(job), 'executed')
                fn.reset_mock()
                self.assertFalse(wrapped(dict(job, prompt='Changed task'))[0])
                self.assertFalse(wrapped(job, extra_prompt='Added instruction')[0])
                fn.assert_not_called()
        self.assertIsNone(policy.CURRENT.get())


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_natural_write_waits_for_scope_confirmation_before_grant(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'policy.json'
            config.write_text(json.dumps({'user': '123', 'chat': '-1001', 'thread': '9'}))
            event = SimpleNamespace(message_id='1', internal=False,
                raw_message=SimpleNamespace(text='Create a folder named Synthetic',
                    from_user=SimpleNamespace(id='123', is_bot=False), chat=SimpleNamespace(id='-1001')),
                source=SimpleNamespace(platform='telegram', user_id='123', chat_id='-1001'))
            runner = SimpleNamespace(_is_user_authorized_for_source=lambda source: True)
            calls = []
            async def execute(self, event):
                calls.append(policy.current().mode)
                return 'ran'
            async def confirm(mode, brief):
                self.assertIsNone(policy.CURRENT.get())
                self.assertEqual(mode, 'drive.create-folder')
                return True
            with patch.object(policy, 'POLICY', config), patch.object(policy, 'SCOPE_CONFIRM', confirm):
                self.assertEqual(await policy.gateway_entry(execute)(runner, event), 'ran')
            self.assertEqual(calls, ['drive.create-folder'])
            calls.clear()
            with patch.object(policy, 'POLICY', config), patch.object(policy, 'SCOPE_CONFIRM', AsyncMock(return_value=False)):
                self.assertIn('not confirmed', await policy.gateway_entry(execute)(runner, event))
            self.assertEqual(calls, [])
            self.assertIsNone(policy.CURRENT.get())

    async def test_owner_binding_concurrent_modes_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'policy.json'
            config.write_text(json.dumps({'user': '123', 'chat': '-1001', 'thread': '9'}))
            runner = SimpleNamespace(_is_user_authorized_for_source=lambda source: True)
            def event(text, owner='123', internal=False):
                return SimpleNamespace(text=text, message_id='1', internal=internal,
                    raw_message=SimpleNamespace(text=text, from_user=SimpleNamespace(id=owner, is_bot=False),
                                                chat=SimpleNamespace(id='-1001')),
                    source=SimpleNamespace(platform='telegram', user_id=owner, chat_id='-1001'))
            async def run(self, message):
                first = policy.current()
                await asyncio.sleep(0)
                self.assertion = first == policy.current()
                return first.mode
            wrapped = policy.gateway_entry(run)
            with patch.object(policy, 'POLICY', config):
                results = await asyncio.gather(wrapped(runner, event('email-read: booking')),
                                               wrapped(runner, event('web-read: cameras')))
                self.assertEqual(results, ['email-read', 'web-read'])
                self.assertTrue(runner.assertion)
                self.assertIsNone(await wrapped(runner, event('gmail.send: send', owner='999')))
                self.assertIsNone(await wrapped(runner, event('gmail.send: send', internal=True)))
                self.assertIn('scope is unclear', await wrapped(runner, event('/cron create')))
                forwarded = event('gmail.send: forward this')
                forwarded.raw_message.forward_origin = object()
                self.assertIn('forwarded content', await wrapped(runner, forwarded))
            self.assertIsNone(policy.CURRENT.get())


class RuntimePatchTests(unittest.TestCase):
    def test_tool_definitions_do_not_hide_schemas_behind_discovery(self):
        source = '''def get_tool_definitions(enabled_toolsets=None, disabled_toolsets=None,
                         quiet_mode=False, skip_tool_search_assembly=False):
    return enabled_toolsets, disabled_toolsets, skip_tool_search_assembly
def handle_function_call(function_name, function_args):
    return 'called'
'''
        namespace = {}
        exec(patch_source('model_tools.py', source), namespace)
        self.assertEqual(namespace['get_tool_definitions'](['google_workspace'], ['terminal']),
                         (['google_workspace'], ['terminal'], True))
        for mode in ('email-read', 'web-read', 'gmail.send', 'chat'):
            with scope(mode):
                for name in ('tool_search', 'tool_describe', 'tool_call'):
                    with self.assertRaises(policy.Denied):
                        policy.authorize(name, {})

    def test_registry_enforces_before_handler_and_denies_unknown_tools(self):
        source = '''class ToolRegistry:
    def dispatch(self, name, args, **kwargs):
        return dangerous(name, args)
'''
        calls = Mock(return_value='allowed')
        namespace = {'dangerous': calls, 'tool_error': lambda s: {'error': s}}
        exec(patch_source('tools/registry.py', source), namespace)
        dispatch = namespace['ToolRegistry']().dispatch
        self.assertIn('error', dispatch('memory', {}))
        with scope('email-read'):
            self.assertIn('error', dispatch('google_workspace', {'operation': 'gmail.send'}))
            calls.assert_not_called()
            self.assertEqual(dispatch('google_workspace', {'operation': 'gmail.get'}), 'allowed')

    def test_conversation_patch_discards_private_history_and_rewritten_brief(self):
        source = '''def run_conversation(agent, user_message, system_message=None, conversation_history=None, moa_config=None):
    return user_message, conversation_history, system_message, moa_config
'''
        namespace = {}
        exec(patch_source('agent/conversation_loop.py', source), namespace)
        with scope('web-read', brief='Public question'):
            result = namespace['run_conversation'](SimpleNamespace(), 'Private injected sidecar',
                                                   conversation_history=[{'content': 'Private email'}])
        self.assertEqual(result[0], 'Public question')
        self.assertEqual(result[1], [])
        self.assertNotIn('Private', result[2])


if __name__ == '__main__':
    unittest.main()
