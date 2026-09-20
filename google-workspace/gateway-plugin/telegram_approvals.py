"""Deterministic owner-only Telegram reviews in the existing Hermes poller.

This is not a model tool. Hermes's authenticated session ContextVars, never model-supplied
identity or tool arguments, bind proposals. Private policy is staged read-only with the plugin.
"""
import asyncio
import json
from pathlib import Path
import uuid

POLICY = Path(__file__).with_name('approval-policy.json')
MAX_REVIEW = 3000  # ASCII JSON: below Telegram's 4096 UTF-16-unit ceiling.


def load_policy():
    policy = json.loads(POLICY.read_text())
    if set(policy) != {'user', 'chat', 'thread'}:
        raise ValueError('Invalid approval policy')
    if not all(isinstance(v, str) for v in policy.values()):
        raise ValueError('Invalid approval identifiers')
    if not policy['user'].isdigit() or int(policy['user']) <= 0:
        raise ValueError('Approval owner required')
    if not policy['chat'].lstrip('-').isdigit() or int(policy['chat']) == 0:
        raise ValueError('Approval destination required')
    if policy['thread'] and (not policy['thread'].isdigit() or int(policy['thread']) <= 0):
        raise ValueError('Invalid approval topic')
    return policy


def trusted_binding(policy):
    from gateway import session_context as context
    # Deliberately bypass get_session_env's process-environment fallback.
    def value(name):
        result = getattr(context, name).get()
        return result if isinstance(result, str) else ''
    if value('_SESSION_PLATFORM') != 'telegram' or context._CRON_SESSION.get() != '':
        raise ValueError('An authenticated owner Telegram task is required')
    source = {key: value(name) for key, name in (
        ('user', '_SESSION_USER_ID'), ('chat', '_SESSION_CHAT_ID'),
        ('thread', '_SESSION_THREAD_ID'), ('session', '_SESSION_KEY'),
        ('source_message', '_SESSION_MESSAGE_ID'))}
    # Owner requests may originate in any topic of the configured forum. The
    # stored callback authority is still the dedicated approval topic.
    if source['user'] != policy['user'] or source['chat'] != policy['chat'] \
            or not source['session'] or not source['source_message']:
        raise ValueError('An authenticated owner Telegram task is required')
    return dict(policy, source_thread=source['thread'], session=source['session'],
                source_message=source['source_message'])


class TelegramApprovals:
    def __init__(self, native, adapter, store, execute, prepare, review_context=None):
        from telegram.ext import CallbackQueryHandler, CommandHandler
        self.native, self.adapter, self.store = native, adapter, store
        self.execute, self.prepare = execute, prepare
        self.review_context = review_context
        self.policy = load_policy()
        self.loop = asyncio.get_running_loop()
        self.epoch = uuid.uuid4().hex
        self.lock = asyncio.Lock()
        store.restart()
        native.add_handler(CallbackQueryHandler(self.callback, pattern=r'^alfie:[ar]:[0-9a-f]{32}$'), group=-100)
        native.add_handler(CommandHandler('alfie_approval_test', self.self_test), group=-100)

    async def self_test(self, update, context):
        from telegram.ext import ApplicationHandlerStop
        try:
            message, user = update.effective_message, update.effective_user
            origin = {'user': str(user.id), 'chat': str(message.chat.id),
                      'thread': str(message.message_thread_id or '')}
            if user.is_bot or origin != self.policy or not self.adapter._is_callback_user_authorized(
                    origin['user'], chat_id=origin['chat'], chat_type=message.chat.type,
                    thread_id=origin['thread'] or None):
                return
            binding = dict(origin, session='owner-self-test', source_message=str(message.message_id))
            await self.present('security.self-test', {'notice': 'No Google API call or account change.'}, binding)
        finally:
            raise ApplicationHandlerStop

    def propose(self, operation, arguments):
        binding = trusted_binding(self.policy)
        operation, arguments = self.prepare(operation, arguments)
        if self.review_context is None:
            raise ValueError('Target review resolver unavailable')
        binding['review_context'] = self.review_context(operation, arguments)
        payload, _ = self.store.canonical_action(operation, arguments)
        # Reject oversized actions; never truncate the data being approved.
        if len(payload) + len(json.dumps(binding['review_context'], ensure_ascii=True)) > MAX_REVIEW:
            raise ValueError('Action is too large for a complete Telegram review; split it into smaller actions')
        try:
            if asyncio.get_running_loop() is self.loop:
                raise ValueError('Proposal must run in a gateway tool worker')
        except RuntimeError:
            pass
        future = asyncio.run_coroutine_threadsafe(self.present(operation, arguments, binding), self.loop)
        try:
            return future.result(timeout=30)
        except TimeoutError:
            future.cancel()
            # Sending might have completed. No mutation occurs without the button.
            return {'status': 'review_delivery_unknown', 'notice': 'No change made. Check Telegram before proposing again.'}

    async def present(self, operation, arguments, binding):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        payload, _ = self.store.canonical_action(operation, arguments)
        context = json.dumps(binding.get('review_context', {}), ensure_ascii=True, sort_keys=True)
        if len(payload) + len(context) > MAX_REVIEW:
            raise ValueError('Action and target context exceed the complete-review budget')
        request_id, payload, digest = self.store.enqueue(operation, arguments, binding, self.epoch)
        text = ('Google action review (untrusted content below).\n'
                'Approve executes exactly this JSON once; Reject makes no change.\n'
                'Target metadata is rechecked before execution; concurrent provider changes remain possible.\n'
                'Task approvals expire within 30 minutes or on restart. Request: ' + request_id +
                '\n\nTarget/effects (untrusted metadata):\n' + context + '\n\nExact action:\n' + payload)
        message = await self.native.bot.send_message(
            chat_id=self.policy['chat'], message_thread_id=self.policy['thread'] or None,
            text=text, parse_mode=None, disable_web_page_preview=True)
        # No live buttons until the entire immutable review is delivered and bound.
        self.store.bind_message(request_id, message.message_id, self.epoch)
        await self.native.bot.edit_message_reply_markup(
            chat_id=self.policy['chat'], message_id=message.message_id,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('Approve exact action', callback_data='alfie:a:' + request_id),
                InlineKeyboardButton('Reject', callback_data='alfie:r:' + request_id)]]))
        return {'status': 'pending_approval', 'request_id': request_id, 'digest': digest,
                'notice': 'No change made. Use the authenticated Telegram review buttons; chat text is not approval.'}

    async def callback(self, update, context):
        from telegram.ext import ApplicationHandlerStop
        query = update.callback_query
        try:
            await self.decide(query)
        except Exception:
            # Never log Telegram objects, payloads, identifiers, or API errors.
            try:
                await query.answer('Approval unavailable. No automatic retry; check the action outcome.', show_alert=True)
            except Exception:
                pass
        finally:
            raise ApplicationHandlerStop

    async def decide(self, query):
        user, message = query.from_user, query.message
        if not user or user.is_bot or not message or not getattr(message, 'chat', None):
            raise ValueError('Missing authenticated callback')
        origin = {'user': str(user.id), 'chat': str(message.chat.id),
                  'thread': str(message.message_thread_id or '')}
        if origin != self.policy or not self.adapter._is_callback_user_authorized(
                origin['user'], chat_id=origin['chat'], chat_type=message.chat.type,
                thread_id=origin['thread'] or None):
            raise ValueError('Unauthorized callback')
        _, choice, request_id = query.data.split(':')
        if choice not in ('a', 'r'):
            raise ValueError('Invalid choice')
        await query.answer('Processing review')
        async with self.lock:
            def validate(binding, action):
                if action == {'operation': 'security.self-test', 'arguments': {'notice': 'No Google API call or account change.'}}:
                    return
                if any(binding.get(key) != self.policy[key] for key in ('user', 'chat', 'thread')) \
                        or not binding.get('session') or not binding.get('source_message') \
                        or not isinstance(binding.get('review_context'), dict) \
                        or not isinstance(action, dict) or set(action) != {'operation', 'arguments'}:
                    raise ValueError('Exact-action review binding is invalid')
            action = self.store.consume(request_id, origin, message.message_id, self.epoch, choice == 'a', validate=validate)
            if action is None:
                status = 'rejected'
            else:
                status = 'unknown'
                try:
                    result = await asyncio.to_thread(self.execute, action['operation'], action['arguments'], action['authorization'])
                    if isinstance(result, dict) and 'error' not in result:
                        status = 'succeeded'
                finally:
                    self.store.finish(request_id, status)
            # Preserve the exact review, remove authority, report only a bounded status.
            await query.edit_message_reply_markup(reply_markup=None)
            await self.native.bot.send_message(
                chat_id=origin['chat'], message_thread_id=origin['thread'] or None,
                text='Google action ' + request_id + ': ' + status +
                     ('. Do not retry; reconcile the remote account first.' if status == 'unknown' else '.'),
                parse_mode=None, disable_web_page_preview=True)
