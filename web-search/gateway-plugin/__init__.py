"""Gateway plugin: the `research` tool.

Plugins run in the gateway process and stay there under D9 (the sandbox cutover moves
the agent's *shell*, not its plugins), so this path is identical before and after the
cutover. That is why it is a plugin and not a script the agent shells out to: after
cutover a shell-invoked client would be on the wrong side of the boundary.
"""
from __future__ import annotations

import asyncio
import json
import logging
import importlib.util
from pathlib import Path
import os
import ssl
import time
import uuid
from typing import Any, Dict

logger = logging.getLogger(__name__)

WS_URL = os.environ.get("WEBSEARCH_URL", "wss://172.31.240.4:8770")
CLIENT_CERT = os.environ.get("WEBSEARCH_CLIENT_CERT", "/opt/websearch-pki/client.crt")
CLIENT_KEY = os.environ.get("WEBSEARCH_CLIENT_KEY", "/opt/websearch-pki/client.key")
CA_CERT = os.environ.get("WEBSEARCH_CA", "/opt/websearch-pki/ca.crt")
SERVER_NAME = os.environ.get("WEBSEARCH_SERVER_NAME", "websearch")

DEADLINE_S = 300
# Derived, not picked: the token must outlive a worst-case job plus upstream's own
# margin (hermes_cli/auth_constants.py:91, CODEX_ACCESS_TOKEN_REFRESH_SKEW_SECONDS=120).
# Upstream's bare 120 is too small here — a token with 150 s left passes its check and
# then dies 150 s into a 300 s job.
#
# Safe only while it stays well under the access token's real lifetime, because Codex
# refresh tokens are single-use and rotate. MEASURED on the box 2026-09-13: the access
# token's exp - iat is 864000 s (10 days), so 420 s is 0.05% of the lifetime and this
# will not refresh on every ask. If that ever changes, lower DEADLINE_S rather than
# raise the skew (hermes_cli/auth_xai.py:181-192 documents the failure).
REFRESH_SKEW_S = DEADLINE_S + 120

_SCHEMA = {
    "name": "research",
    "description": (
        "Research a question on the web and return a brief: conclusion, findings with "
        "numbered sources, confidence, and open questions. Runs searches and reads pages "
        "in an isolated container — the page text never enters this conversation, so this "
        "costs a fraction of doing the same work with web_search/web_extract. Use it for "
        "questions needing more than one page; use browse for interactive public pages."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The research question, in full."},
            "depth": {
                "type": "string", "enum": ["quick", "deep"],
                "description": "quick: 1 round, <=4 pages (default). deep: up to 3 rounds, <=12 pages.",
            },
        },
        "required": ["question"],
    },
}


def _resolve_token() -> Dict[str, Any]:
    """Refresh before dispatch if the token could not outlive the job, through
    upstream's own entry point: it re-reads under _auth_store_lock so it cannot race
    another Hermes process, and it carries the single-use rotation self-heal."""
    from hermes_cli.auth_codex import resolve_codex_runtime_credentials
    return resolve_codex_runtime_credentials(
        refresh_if_expiring=True, refresh_skew_seconds=REFRESH_SKEW_S) or {}


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(CA_CERT)
    ctx.load_cert_chain(CLIENT_CERT, CLIENT_KEY)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


async def _ask_worker(question: str, depth: str, token: str) -> str:
    import websockets

    job_id = uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location('alfie_research_broker', Path(__file__).with_name('inference_broker.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    broker = module.Broker(token, job_id, depth)
    frame = json.dumps({"type": "ask", "id": job_id, "question": question,
                        "depth": depth, "protocol": 2})
    async with websockets.connect(WS_URL, ssl=_ssl_context(), server_hostname=SERVER_NAME,
                                  open_timeout=20, close_timeout=5,
                                  ping_interval=30, max_size=2 ** 20) as ws:
        await ws.send(frame)
        deadline = time.monotonic() + DEADLINE_S + 30
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return "research: the worker did not answer before the deadline."
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
            if not isinstance(msg, dict) or msg.get('id') != job_id:
                return 'research: invalid worker response binding'
            kind = msg.get("type")
            if kind == 'inference':
                try:
                    reply = await broker.infer(msg)
                except Exception:
                    return 'research: bounded inference refused or failed'
                await ws.send(json.dumps(reply))
                continue
            if kind == "progress":
                logger.info("research %s: %s round=%s pages=%s", job_id[:8],
                            msg.get("stage"), msg.get("round"), msg.get("pages"))
                continue
            if kind == "result":
                return msg.get("text") or json.dumps(msg.get("brief", {}))
            if kind == "error":
                return f"research failed ({msg.get('code')}): {msg.get('detail')}"


def _research(question: str = "", depth: str = "quick", **_: Any) -> str:
    question = (question or "").strip()
    if not question:
        return "research: question was empty."
    if depth not in ("quick", "deep"):
        depth = "quick"

    try:
        creds = _resolve_token()
    except Exception as exc:  # noqa: BLE001
        return f"research: could not resolve the model credential ({type(exc).__name__})."
    token = creds.get("api_key") or creds.get("access_token") or ""
    # Fail closed. There is no OPENAI_API_KEY fallback and no fallback chain at all:
    # spec §2.1 — Alfie must never fall back to paid API spend on its own.
    if not token:
        return "research: no Codex credential available; not dispatching."

    try:
        return asyncio.run(_ask_worker(question, depth, token))
    except Exception as exc:  # noqa: BLE001 — a tool must return, not raise
        logger.exception("research dispatch failed")
        return f"research failed to reach the worker: {type(exc).__name__}: {exc}"


def _available() -> bool:
    return all(os.path.exists(p) for p in (CLIENT_CERT, CLIENT_KEY, CA_CERT))


def tool_handler(args, **_):
    if not isinstance(args, dict) or set(args) - {'question', 'depth'}:
        return 'research: invalid arguments'
    return _research(**args)


def register(ctx) -> None:
    ctx.register_tool(
        name="research", toolset="websearch", handler=tool_handler,
        description=_SCHEMA["description"], schema=_SCHEMA,
        emoji="\U0001f50e", check_fn=_available,
    )
