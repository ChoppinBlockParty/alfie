"""Worker process and protocol tests; no network/provider calls."""
import asyncio
import importlib.util
import json
import multiprocessing
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'worker'))
sys.path.insert(0, str(ROOT.parent / 'web-browser/worker'))


def stalled_child(connection, question, depth):
    time.sleep(30)


def synthetic_child(connection, question, depth):
    import research
    connection.send({'kind': 'inference', 'model': research.MODEL,
                     'instructions': research._PLAN_INSTRUCTIONS, 'user': question})
    response = connection.recv()
    assert response['data'] == {'queries': []}
    connection.send({'kind': 'result', 'brief': {'synthetic': True}, 'text': 'Synthetic result'})
    connection.close()


class Socket:
    close_code = None
    def __init__(self):
        self.sent = []
    async def send(self, text):
        self.sent.append(json.loads(text))
    async def recv(self):
        previous = self.sent[-1]
        return json.dumps({'type': 'inference_result', 'id': previous['id'], 'call': previous['call'],
                           'data': {'queries': []}, 'tokens': 1})


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        try:
            import websockets
        except ImportError:
            self.skipTest('Run in installed worker for websockets dependency')
        # Import by normal name so multiprocessing spawn can resolve the target module.
        import server
        self.server = server

    async def test_legacy_token_frames_are_rejected_before_process_creation(self):
        socket = Socket()
        with patch.object(self.server.multiprocessing, 'get_context') as spawn:
            await self.server.Worker()._ask(socket, {'type': 'ask', 'id': 'synthetic',
                                                    'question': 'Synthetic', 'access_token': 'synthetic-secret'})
        spawn.assert_not_called()
        self.assertEqual(socket.sent[0]['code'], 'bad_protocol')
        self.assertNotIn('synthetic-secret', str(socket.sent))

    async def test_deadline_kills_child_and_releases_busy_slot(self):
        before = {p.pid for p in multiprocessing.active_children()}
        worker, socket = self.server.Worker(), Socket()
        started = time.monotonic()
        with patch.object(self.server, '_research_child', stalled_child), \
                patch.object(self.server.research, 'DEADLINE_S', .1):
            await worker._ask(socket, {'type': 'ask', 'id': 'synthetic', 'question': 'Synthetic',
                                      'depth': 'quick', 'protocol': 2})
        self.assertLess(time.monotonic() - started, 5)
        self.assertFalse(worker._busy)
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)
        self.assertEqual(socket.sent[-1]['type'], 'error')

    async def test_child_uses_bound_inference_without_credentials(self):
        worker, socket = self.server.Worker(), Socket()
        with patch.object(self.server, '_research_child', synthetic_child):
            await worker._ask(socket, {'type': 'ask', 'id': 'synthetic', 'question': 'Synthetic',
                                      'depth': 'quick', 'protocol': 2})
        self.assertEqual([m['type'] for m in socket.sent], ['inference', 'result'])
        self.assertEqual(socket.sent[0]['call'], 1)
        self.assertNotIn('access_token', str(socket.sent))
        self.assertFalse(worker._busy)
