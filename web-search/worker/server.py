"""Public worker: mutual TLS, one killable research process, no model credentials.

Inference is brokered over the existing gateway connection. Legacy token-bearing asks fail
closed. Public retrieval credentials remain in this worker; model tokens never enter it.
"""
from __future__ import annotations

import asyncio
import json
import logging
import multiprocessing
import os
import resource
import ssl
import sys
import time
from typing import Any, Dict, Optional

import websockets

import research
import browser

LOG = logging.getLogger("websearch")

PORT = int(os.environ.get("WEBSEARCH_PORT", "8770"))
CERT = os.environ.get("WEBSEARCH_CERT", "/etc/websearch/server.crt")
KEY = os.environ.get("WEBSEARCH_KEY", "/etc/websearch/server.key")
CA = os.environ.get("WEBSEARCH_CA", "/etc/websearch/ca.crt")
HEARTBEAT_S = 60


def _research_child(connection, question, depth):
    """Spawned process, no inherited gateway secrets. Parent enforces the wall deadline."""
    def ask(client, model, instructions, user, timeout):
        connection.send({'kind': 'inference', 'model': model, 'instructions': instructions, 'user': user})
        if not connection.poll(min(125, timeout + 5)):
            raise TimeoutError('Inference broker unavailable')
        response = connection.recv()
        if not isinstance(response, dict) or not isinstance(response.get('data'), dict):
            raise ValueError('Invalid broker response')
        return response['data'], response['tokens']

    def progress(stage, info):
        connection.send({'kind': 'progress', 'stage': stage,
                         **{key: value for key, value in info.items() if key in ('round', 'pages')}})
    try:
        result = research.run(question, depth, None, on_progress=progress, ask_fn=ask)
        connection.send({'kind': 'result', 'brief': result, 'text': research.render(result)})
    except Exception:
        connection.send({'kind': 'error'})
    finally:
        connection.close()


class _Redactor(logging.Filter):
    """Nothing that looks like a JWT reaches a log line. The token is never passed to
    a logger deliberately; this is the backstop for a traceback that formats a frame."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        if "eyJ" in msg:
            record.msg = "".join("<redacted>" if part.startswith("eyJ") else part
                                 for part in msg.split(" "))
            record.args = ()
        return True


class Worker:
    """One job in flight. A second ask is refused with `busy` rather than queued: it
    bounds memory in a cgroup where exceeding mem_limit is an OOM kill, not a
    slowdown, and it stops two jobs racing through the plan quota."""

    def __init__(self) -> None:
        self._busy = False
        self._lock = asyncio.Lock()
        self._cancelled: set = set()
        self.browser = browser.Browser()

    async def handle(self, ws) -> None:
        LOG.info("client connected")
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await self._error(ws, "", "bad_json", "message was not JSON")
                    continue
                if not isinstance(msg, dict):
                    await self._error(ws, "", "bad_request", "object required")
                    continue
                kind = msg.get("type")
                if kind == "ask":
                    await self._ask(ws, msg)
                elif kind == "browser":
                    await self._browser(ws, msg)
                elif kind == "cancel":
                    self._cancelled.add(msg.get("id", ""))
                else:
                    await self._error(ws, msg.get("id", ""), "bad_type", f"unknown type {kind!r}")
        except websockets.ConnectionClosed:
            LOG.info("client disconnected")

    async def _ask(self, ws, msg: Dict[str, Any]) -> None:
        job_id = str(msg.get("id", ""))
        if self._busy or self.browser.active:
            await self._error(ws, job_id, "busy", "a job is already in flight")
            return
        if set(msg) != {'type', 'id', 'question', 'depth', 'protocol'} or msg.get('protocol') != 2:
            await self._error(ws, job_id, 'bad_protocol', 'credential-free protocol required')
            return
        question = msg.get('question')
        if not isinstance(question, str) or not question.strip() or len(question.encode()) > 16000:
            await self._error(ws, job_id, "bad_request", "question was empty")
            return

        depth = msg.get("depth") if msg.get("depth") in research.DEPTHS else "quick"
        self._busy = True
        context = multiprocessing.get_context('spawn')
        parent, child = context.Pipe()
        process = context.Process(target=_research_child, args=(child, question, depth), daemon=True)
        deadline = time.monotonic() + research.DEADLINE_S
        call = 0
        try:
            process.start()
            child.close()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or getattr(ws, 'close_code', None) is not None:
                    raise TimeoutError('Research deadline or disconnect')
                if not await asyncio.to_thread(parent.poll, min(.2, remaining)):
                    if not process.is_alive():
                        raise ValueError('Research process stopped')
                    continue
                frame = parent.recv()
                kind = frame.get('kind')
                if kind == 'inference':
                    call += 1
                    if call > (3 if depth == 'quick' else 5):
                        raise ValueError('Inference request budget exceeded')
                    await ws.send(json.dumps({'type': 'inference', 'id': job_id, 'call': call,
                        'model': frame['model'], 'instructions': frame['instructions'], 'user': frame['user']}))
                    response = json.loads(await asyncio.wait_for(ws.recv(), timeout=min(125, remaining)))
                    if not isinstance(response, dict) or response.get('type') != 'inference_result' \
                            or response.get('id') != job_id or response.get('call') != call:
                        raise ValueError('Inference response binding mismatch')
                    parent.send(response)
                elif kind == 'progress':
                    await ws.send(json.dumps({'type': 'progress', 'id': job_id,
                        **{key: frame[key] for key in ('stage', 'round', 'pages') if key in frame}}))
                elif kind == 'result':
                    await ws.send(json.dumps({'type': 'result', 'id': job_id,
                                              'brief': frame['brief'], 'text': frame['text']}))
                    return
                else:
                    raise ValueError('Research process failed')
        except Exception:
            await self._error(ws, job_id, 'failed', 'Research stopped; no automatic retry')
        finally:
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                await asyncio.to_thread(process.join, 2)
                if process.is_alive():
                    process.kill()
                    await asyncio.to_thread(process.join, 2)
            parent.close()
            child.close()
            self._busy = False

    async def _browser(self, ws, msg):
        job_id = str(msg.get("id", ""))
        if self._busy:
            await self._error(ws, job_id, "busy", "worker already processing a request")
            return
        # A foreign/stale session must not close another session through error cleanup.
        if self.browser.active and (msg.get("action") == "open" or
                                    msg.get("session_id") != self.browser.session):
            await self._error(ws, job_id, "busy", "another browser session owns the worker")
            return
        self._busy = True
        try:
            result = await asyncio.wait_for(self.browser.perform(msg), browser.ACTION_TIMEOUT_S)
            await ws.send(json.dumps({"type": "result", "id": job_id, "browser": result}))
        except ValueError as exc:
            await self.browser.close()
            await self._error(ws, job_id, "bad_request", str(exc))
        except Exception as exc:
            await self.browser.close()
            await self._error(ws, job_id, "browser_failed", type(exc).__name__ + "; session closed")
        finally:
            self._busy = False

    async def reap_browser(self):
        while True:
            await asyncio.sleep(5)
            if not self._busy:
                self._busy = True
                try:
                    await self.browser.expire()
                finally:
                    self._busy = False

    async def _heartbeat(self, ws, job_id: str, state: Dict[str, Any]) -> None:
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_S)
                await ws.send(json.dumps({"type": "progress", "id": job_id, **state}))
        except (asyncio.CancelledError, websockets.ConnectionClosed):
            pass

    @staticmethod
    async def _error(ws, job_id: str, code: str, detail: str) -> None:
        await ws.send(json.dumps({"type": "error", "id": job_id, "code": code, "detail": detail}))


def _zero(buf: bytearray) -> None:
    for i in range(len(buf)):
        buf[i] = 0


def _ssl_context() -> ssl.SSLContext:
    """Mutual TLS. CERT_REQUIRED is the real control: on an internal network TLS alone
    would be defence-in-depth, but without a client certificate any container on that
    network could open the socket and spend plan quota."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(CERT, KEY)
    ctx.load_verify_locations(CA)
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


async def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger().addFilter(_Redactor())
    for handler in logging.getLogger().handlers:
        handler.addFilter(_Redactor())

    # A crash cannot spill the token to disk.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    worker = Worker()
    reaper = asyncio.create_task(worker.reap_browser())
    async with websockets.serve(worker.handle, "0.0.0.0", PORT, ssl=_ssl_context(),
                                ping_interval=30, ping_timeout=30, max_size=2 ** 20):
        LOG.info("listening on %d (mutual TLS, client cert required)", PORT)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
