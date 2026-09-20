import asyncio
import hashlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'worker'))
import research
spec = importlib.util.spec_from_file_location('test_inference_broker', ROOT / 'gateway-plugin/inference_broker.py')
broker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(broker)


def frame(**overrides):
    return dict({'type': 'inference', 'id': 'synthetic-job', 'call': 1,
                 'model': research.MODEL, 'instructions': research._PLAN_INSTRUCTIONS,
                 'user': 'Public synthetic question'}, **overrides)


class BrokerValidationTests(unittest.TestCase):
    def test_reviewed_prompt_hashes_and_binding(self):
        self.assertEqual(broker.PROMPTS, {hashlib.sha256(x.encode()).hexdigest() for x in
            (research._PLAN_INSTRUCTIONS, research._ANALYSE_INSTRUCTIONS, research._SYNTH_INSTRUCTIONS)})
        broker.validate_request(frame(), 'synthetic-job', 1)
        for change in ({'id': 'foreign'}, {'call': True}, {'call': 2}, {'model': 'other'},
                       {'base_url': 'https://example.com'}, {'tools': []},
                       {'instructions': 'Unreviewed'}, {'user': 'x' * (broker.MAX_INPUT + 1)}):
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                broker.validate_request(frame(**change), 'synthetic-job', 1)

    def test_json_object_only(self):
        self.assertEqual(broker.parse_object('```json\n{"queries": []}\n```'), {'queries': []})
        with self.assertRaises(ValueError):
            broker.parse_object('[]')


class BrokerExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixed_transport_no_tools_and_bounded_result(self):
        class Stream:
            close = AsyncMock()
            def __aiter__(self):
                async def events():
                    yield SimpleNamespace(type='response.output_text.delta', delta='{"queries": []}')
                    yield SimpleNamespace(type='response.completed', response=SimpleNamespace(usage=SimpleNamespace(total_tokens=10)))
                return events()
        stream = Stream()
        client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=stream)), close=AsyncMock())
        factory = Mock(return_value=client)
        with patch.dict(sys.modules, {'openai': SimpleNamespace(AsyncOpenAI=factory)}):
            result = await broker.Broker('synthetic-token', 'synthetic-job', 'quick').infer(frame())
        self.assertEqual(result['data'], {'queries': []})
        self.assertNotIn('synthetic-token', str(result))
        self.assertEqual(factory.call_args.kwargs['base_url'], broker.BASE_URL)
        self.assertEqual(factory.call_args.kwargs['max_retries'], 0)
        self.assertNotIn('tools', client.responses.create.call_args.kwargs)
        stream.close.assert_awaited_once()
        client.close.assert_awaited_once()

    async def test_spent_budget_never_constructs_client(self):
        instance = broker.Broker('synthetic-token', 'synthetic-job', 'quick')
        instance.calls = 3
        with self.assertRaises(ValueError):
            await instance.infer(frame(call=4))
