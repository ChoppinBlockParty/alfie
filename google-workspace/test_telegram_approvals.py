"""No network or account writes. Runs with real PTB when installed, stubs otherwise."""
import asyncio
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import AsyncMock, Mock, patch

from test_approvals import plugin, store

spec = importlib.util.spec_from_file_location('telegram_reviews', Path(__file__).parent / 'gateway-plugin/telegram_approvals.py')
reviews = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviews)
ORIGIN = {'user': '123', 'chat': '123', 'thread': ''}
BINDING = dict(ORIGIN, session='synthetic-session', source_message='10')
SOURCE_BINDING = dict(BINDING, source_thread='99')


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'private' / 'actions.sqlite'
        self.addCleanup(patch.stopall)
        patch.object(store, 'STORE', self.path).start()

    def pending(self):
        rid, _, _ = store.enqueue('gmail.send', {'body': 'synthetic'}, BINDING, 'epoch', now=10)
        store.bind_message(rid, 20, 'epoch')
        return rid

    def consume(self, rid, **overrides):
        kwargs = dict(origin=ORIGIN, message=20, epoch='epoch', accept=True, now=11)
        kwargs.update(overrides)
        return store.consume(rid, **kwargs)

    def test_one_use_and_rejected_requests(self):
        for accept in (True, False):
            rid = self.pending()
            self.consume(rid, accept=accept)
            with self.assertRaises(ValueError):
                self.consume(rid)

    def test_every_origin_field_and_message_and_epoch(self):
        rid = self.pending()
        for field in ORIGIN:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.consume(rid, origin=dict(ORIGIN, **{field: '999'}))
        for kwargs in ({'message': 21}, {'epoch': 'new'}, {'now': 10 + store.TTL_S}):
            with self.assertRaises(ValueError):
                self.consume(rid, **kwargs)
        self.assertEqual(self.consume(rid)['operation'], 'gmail.send')

    def test_tamper_and_forgery(self):
        rid = self.pending()
        with closing(sqlite3.connect(self.path)) as con, con:
            con.execute('UPDATE telegram_actions SET payload=? WHERE id=?', ('{}', rid))
        for key in (rid, '0' * 32):
            with self.assertRaises(ValueError):
                self.consume(key)

    def test_concurrent_confirmations_execute_once(self):
        rid = self.pending()
        def attempt(_):
            try:
                self.consume(rid)
                return 1
            except ValueError:
                return 0
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(8))), 1)

    def test_restart_invalidates_buttons_and_never_retries_executing(self):
        pending, executing = self.pending(), self.pending()
        self.consume(executing)
        store.restart()
        for key in (pending, executing):
            with self.assertRaises(ValueError):
                self.consume(key)
        with closing(sqlite3.connect(self.path)) as con:
            statuses = dict(con.execute('SELECT id,status FROM telegram_actions'))
        self.assertEqual(statuses[executing], 'unknown')
        self.assertEqual(statuses[pending], 'expired')

    def test_legacy_queue_never_authorizes(self):
        old = store.propose('gmail.send', {}, now=10)
        with self.assertRaises(ValueError):
            self.consume(old['request_id'])


class TelegramTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'private' / 'actions.sqlite'
        self.addCleanup(patch.stopall)
        patch.object(store, 'STORE', self.path).start()
        patch.object(reviews, 'load_policy', return_value=ORIGIN).start()
        try:
            import telegram.ext
        except ImportError:
            tg, ext = ModuleType('telegram'), ModuleType('telegram.ext')
            tg.InlineKeyboardButton = lambda *a, **kw: (a, kw)
            tg.InlineKeyboardMarkup = lambda value: value
            ext.CallbackQueryHandler = lambda callback, **kw: SimpleNamespace(callback=callback, **kw)
            ext.CommandHandler = lambda command, callback, **kw: SimpleNamespace(callback=callback, command=command, **kw)
            ext.ApplicationHandlerStop = type('ApplicationHandlerStop', (Exception,), {})
            patch.dict(sys.modules, {'telegram': tg, 'telegram.ext': ext}).start()
        self.native = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=20)),
                                     edit_message_reply_markup=AsyncMock()), add_handler=Mock())
        self.adapter = SimpleNamespace(_is_callback_user_authorized=Mock(return_value=True))
        self.execute = Mock(return_value={'status': 'sent'})
        self.bridge = reviews.TelegramApprovals(self.native, self.adapter, store, self.execute, plugin.prepare_action)

    async def pending(self):
        return (await self.bridge.present('gmail.send', {'to': 'recipient@example.com', 'subject': 'Synthetic',
                                          'body': 'Synthetic body'},
                                          dict(BINDING, review_context={'effect': 'synthetic'})))['request_id']

    def query(self, rid, choice='a'):
        return SimpleNamespace(from_user=SimpleNamespace(id=123, is_bot=False),
            message=SimpleNamespace(chat=SimpleNamespace(id=123, type='private'), message_thread_id=None, message_id=20),
            data='alfie:' + choice + ':' + rid, answer=AsyncMock(), edit_message_reply_markup=AsyncMock())

    async def test_registered_scoped_handler_and_exact_review(self):
        self.assertEqual(self.native.add_handler.call_args.kwargs['group'], -100)
        rid = await self.pending()
        text = self.native.bot.send_message.call_args.kwargs['text']
        self.assertIn('Synthetic body', text)
        self.assertIn(rid, text)
        self.assertIsNone(self.native.bot.send_message.call_args.kwargs['parse_mode'])
        await self.bridge.decide(self.query(rid))
        self.execute.assert_called_once_with('gmail.send', {'to': 'recipient@example.com', 'subject': 'Synthetic', 'body': 'Synthetic body'},
            dict(BINDING, review_context={'effect': 'synthetic'}))
        with self.assertRaises(ValueError):
            await self.bridge.decide(self.query(rid))

    async def test_wrong_user_chat_topic_message_bot_and_revoked_auth(self):
        for change in ('user', 'chat', 'topic', 'message', 'bot', 'auth'):
            rid = await self.pending()
            q = self.query(rid)
            if change == 'user': q.from_user.id = 999
            if change == 'chat': q.message.chat.id = 999
            if change == 'topic': q.message.message_thread_id = 99
            if change == 'message': q.message.message_id = 99
            if change == 'bot': q.from_user.is_bot = True
            self.adapter._is_callback_user_authorized.return_value = change != 'auth'
            with self.subTest(change=change), self.assertRaises(ValueError):
                await self.bridge.decide(q)
        self.execute.assert_not_called()

    async def test_reject_does_not_execute(self):
        await self.bridge.decide(self.query(await self.pending(), 'r'))
        self.execute.assert_not_called()

    async def test_failure_and_timeout_remain_unknown(self):
        for exception in (False, True):
            rid = await self.pending()
            self.execute.return_value = {'error': 'synthetic failure'}
            self.execute.side_effect = TimeoutError() if exception else None
            try:
                await self.bridge.decide(self.query(rid))
            except TimeoutError:
                pass
            with closing(sqlite3.connect(self.path)) as con:
                self.assertEqual(con.execute('SELECT status FROM telegram_actions WHERE id=?', (rid,)).fetchone()[0], 'unknown')
            with self.assertRaises(ValueError):
                await self.bridge.decide(self.query(rid))

    async def test_delivery_failure_never_exposes_buttons_or_executes(self):
        self.native.bot.send_message.side_effect = RuntimeError('synthetic')
        with self.assertRaises(RuntimeError):
            await self.pending()
        self.native.bot.edit_message_reply_markup.assert_not_called()
        self.execute.assert_not_called()

    async def test_tool_context_cannot_be_supplied_as_arguments(self):
        with patch.object(plugin, '_bridge', self.bridge), patch.object(reviews, 'trusted_binding', side_effect=ValueError('Owner task required')):
            result = plugin.google_workspace('gmail.send', {'to': 'recipient@example.com', 'subject': 'Synthetic', 'body': 'x'},
                                             approved=True, user='123', chat='123')
        self.assertIn('error', json.loads(result))
        self.execute.assert_not_called()

    async def test_callback_always_stops_core_dispatch(self):
        from telegram.ext import ApplicationHandlerStop
        callback = self.native.add_handler.call_args_list[0].args[0].callback
        query = self.query('0' * 32)
        with self.assertRaises(ApplicationHandlerStop):
            await callback(SimpleNamespace(callback_query=query), None)
        self.execute.assert_not_called()


class PreparationTests(unittest.TestCase):
    def test_dedicated_policy_is_separate_from_email_delivery(self):
        policy_spec = importlib.util.spec_from_file_location(
            'render_approval_policy', Path(__file__).parent / 'render_approval_policy.py')
        renderer = importlib.util.module_from_spec(policy_spec)
        policy_spec.loader.exec_module(renderer)
        env = {'ALFIE_OWNER_TELEGRAM_USER_ID': '123', 'EMAIL_WATCH_CHAT_ID': '-1001',
               'EMAIL_WATCH_THREAD_ID': '17', 'ALFIE_APPROVAL_CHAT_ID': '-1002',
               'ALFIE_APPROVAL_THREAD_ID': '1287'}
        with patch.dict('os.environ', env, clear=True):
            self.assertEqual(renderer.policy(), {'user': '123', 'chat': '-1002', 'thread': '1287'})

    def test_self_test_cannot_call_google_or_be_requested_as_a_tool(self):
        with patch.object(plugin, 'run_google') as execute:
            self.assertNotIn('error', plugin.execute_approved('security.self-test', {'notice': 'No Google API call or account change.'}))
            self.assertIn('error', json.loads(plugin.google_workspace('security.self-test', {})))
            execute.assert_not_called()

    def test_real_runtime_context_and_no_environment_fallback(self):
        try:
            from gateway import session_context as context
        except ImportError:
            self.skipTest('Run inside installed Hermes for real ContextVars')
        context.reset_session_vars()
        with patch.dict('os.environ', {'HERMES_SESSION_PLATFORM': 'telegram', 'HERMES_SESSION_USER_ID': '123'}):
            with self.assertRaises(ValueError):
                reviews.trusted_binding(ORIGIN)
        tokens = context.set_session_vars(platform='telegram', user_id='123', chat_id='123', thread_id='99',
                                          session_key='synthetic-session', message_id='10', cron_session='')
        try:
            self.assertEqual(reviews.trusted_binding(ORIGIN), SOURCE_BINDING)
            token = context._CRON_SESSION.set('cron-task')
            try:
                with self.assertRaises(ValueError):
                    reviews.trusted_binding(ORIGIN)
            finally:
                context._CRON_SESSION.reset(token)
        finally:
            context.clear_session_vars(tokens)

    def test_real_hermes_plugin_registration(self):
        try:
            from hermes_cli.plugins import PluginContext, PluginManifest, PluginManager
        except ImportError:
            self.skipTest('Run inside installed Hermes for plugin SDK')
        manager = PluginManager()
        ctx = PluginContext(manifest=PluginManifest(name='synthetic_approval_test', version='0.1.0', description='test'), manager=manager)
        from tools.registry import ToolRegistry
        registry = ToolRegistry()
        with patch('tools.registry.registry', registry):
            plugin.register(ctx)
        self.assertEqual(manager.get_platform_handler_factories('telegram')[0][0], plugin.telegram_factory)
        bridge = SimpleNamespace(propose=Mock(return_value={'status': 'pending_approval'}))
        with patch.object(plugin, '_bridge', bridge), patch.object(plugin, 'run_google') as execute:
            result = json.loads(registry.dispatch('google_workspace',
                {'operation': 'drive.create-folder', 'arguments': {'name': 'Synthetic approval test'}},
                scope=manager.scope_key, task_id='synthetic-task'))
            self.assertEqual(result['status'], 'pending_approval')
            bridge.propose.assert_called_once_with('drive.create-folder', {'name': 'Synthetic approval test'})
            execute.assert_not_called()
        with patch.object(plugin, 'run_google', return_value='[]') as execute, \
                patch.object(plugin, '_bridge', Mock(confirm_read=Mock(return_value=True))):
            self.assertEqual(registry.dispatch('google_workspace',
                {'operation': 'gmail.labels', 'arguments': {}}, scope=manager.scope_key), '[]')
            execute.assert_called_once_with(['gmail', 'labels'])

    def test_reply_is_frozen_before_review(self):
        target = {'from': 'recipient@example.com', 'subject': 'Synthetic', 'threadId': 'thread-fixture', 'message_id_header': '<fixture@example.com>'}
        with patch.object(plugin, 'run_google', return_value=json.dumps(target)) as read:
            operation, args = plugin.prepare_action('gmail.reply', {'message_id': 'fixture', 'body': 'Synthetic reply'})
            self.assertEqual(operation, 'gmail.send')
            self.assertEqual(args['to'], target['from'])
            self.assertEqual(args['subject'], 'Re: Synthetic')
            read.assert_called_once()
        with patch.object(plugin, 'run_google', return_value='{"status":"sent"}') as execute:
            with patch.object(plugin, 'review_context', return_value={'effect': 'synthetic'}):
                plugin.execute_approved(operation, args, dict(BINDING, review_context={'effect': 'synthetic'},
                    source_thread=''))
            self.assertEqual(execute.call_args.args[0][0:2], ['gmail', 'send'])

    def test_header_injection_rejected(self):
        with self.assertRaises(ValueError):
            plugin.build_args('gmail.send', {'to': 'recipient@example.com\nBcc: other@example.com', 'subject': 'x', 'body': 'x'})


if __name__ == '__main__':
    unittest.main()
