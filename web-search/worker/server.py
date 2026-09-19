"""WebSocket server: one job at a time, mutual TLS, no credential on disk.

The gateway is the client and connects to wss://websearch:8770. The access token
rides every ask and is dropped when the job ends — nothing is retained between jobs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import resource
import ssl
import sys
import time
from typing import Any, Dict, Optional

import websockets

import codex
import research
import browser

LOG = logging.getLogger("websearch")

PORT = int(os.environ.get("WEBSEARCH_PORT", "8770"))
CERT = os.environ.get("WEBSEARCH_CERT", "/etc/websearch/server.crt")
KEY = os.environ.get("WEBSEARCH_KEY", "/etc/websearch/server.key")
CA = os.environ.get("WEBSEARCH_CA", "/etc/websearch/ca.crt")
HEARTBEAT_S = 60


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
                elif kind == "token":
                    pass  # belt-and-braces; the token rides every ask
                else:
                    await self._error(ws, msg.get("id", ""), "bad_type", f"unknown type {kind!r}")
        except websockets.ConnectionClosed:
            LOG.info("client disconnected")

    async def _ask(self, ws, msg: Dict[str, Any]) -> None:
        job_id = str(msg.get("id", ""))
        if self._busy or self.browser.active:
            await self._error(ws, job_id, "busy", "a job is already in flight")
            return
        question = str(msg.get("question", "")).strip()
        if not question:
            await self._error(ws, job_id, "bad_request", "question was empty")
            return

        # bytearray so this module controls the one copy it owns and can zeroize it.
        # Copies made inside the OpenAI SDK are released to the garbage collector, not
        # overwritten — wiping is best-effort and the README says so plainly.
        token = bytearray((msg.get("access_token") or "").encode())
        if not token:
            await self._error(ws, job_id, "no_token", "ask carried no access token")
            return
        expires_at = msg.get("expires_at")
        if isinstance(expires_at, (int, float)) and expires_at <= time.time():
            _zero(token)
            await self._error(ws, job_id, "token_expired", "access token already expired")
            return

        depth = msg.get("depth") if msg.get("depth") in research.DEPTHS else "quick"
        self._busy = True
        beat: Optional[asyncio.Task] = None
        client = None
        state: Dict[str, Any] = {"stage": "start", "round": 0, "pages": 0, "tokens": 0}
        try:
            client = codex.make_client(token.decode())
            beat = asyncio.create_task(self._heartbeat(ws, job_id, state))

            def on_progress(stage: str, info: Dict[str, Any]) -> None:
                state["stage"] = stage
                state.update({k: v for k, v in info.items() if k in ("round", "pages")})

            brief = await asyncio.to_thread(
                research.run, question, depth, client, on_progress=on_progress)
            if job_id in self._cancelled:
                self._cancelled.discard(job_id)
                return
            await ws.send(json.dumps({"type": "result", "id": job_id, "brief": brief,
                                      "text": research.render(brief)}))
        except codex.RefusedBaseURL as exc:
            await self._error(ws, job_id, "refused_base_url", str(exc))
        except research.VendorFailed as exc:
            await self._error(ws, job_id, "vendor_failed", str(exc))
        except Exception as exc:  # noqa: BLE001 — every failure is an error frame
            LOG.exception("job failed")
            await self._error(ws, job_id, "failed", f"{type(exc).__name__}: {exc}")
        finally:
            if beat:
                beat.cancel()
            _zero(token)
            if client is not None:
                try:
                    client.close()
                except Exception:  # noqa: BLE001 — closing must not mask the real error
                    pass
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
