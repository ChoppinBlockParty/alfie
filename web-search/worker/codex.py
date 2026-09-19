"""Minimal Codex client. ~30 lines of intent, not the 1,543-line agent transport.

The gateway stays the sole owner and sole refresher of auth.json; this module only
ever sees a access token, handed over per job in the WebSocket frame.
"""
from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from openai import OpenAI

# agent/codex_headers.py:16
OFFICIAL_BASE_URL = "https://chatgpt.com/backend-api/codex"
HERMES_VERSION = "0.1.0"


class RefusedBaseURL(RuntimeError):
    """The worker will talk to the official Codex endpoint and nothing else."""


def is_official_codex_base_url(base_url: str) -> bool:
    """Mirror of agent/codex_headers.py:19 — identify OpenAI's endpoint without
    matching a custom proxy that merely has 'codex' in its path."""
    try:
        parsed = urlparse(base_url)
        path = parsed.path.rstrip("/")
        return (parsed.scheme == "https" and parsed.hostname == "chatgpt.com"
                and parsed.port in (None, 443)
                and (path == "/backend-api/codex" or path.startswith("/backend-api/codex/")))
    except (TypeError, ValueError):
        return False


def _account_id(access_token: str) -> str:
    """ChatGPT-Account-ID from the token's own JWT claim (agent/codex_headers.py:46).
    A malformed token drops the header rather than raising, so it surfaces as a 401
    instead of a crash at client construction. Logs nothing."""
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return ""
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        acct = claims.get("https://api.openai.com/auth", {}).get("chatgpt_account_id")
        return acct if isinstance(acct, str) else ""
    except Exception:  # noqa: BLE001 — never raise on a token we must not log
        return ""


def make_client(access_token: str, base_url: str = OFFICIAL_BASE_URL) -> OpenAI:
    if not is_official_codex_base_url(base_url):
        raise RefusedBaseURL(f"refusing non-official codex base_url: {base_url!r}")
    headers = {"User-Agent": f"HermesAgent/{HERMES_VERSION}", "originator": "hermes-agent"}
    acct = _account_id(access_token)
    if acct:
        headers["ChatGPT-Account-ID"] = acct
    return OpenAI(api_key=access_token, base_url=base_url, default_headers=headers, max_retries=2)


def ask(client: OpenAI, model: str, instructions: str, user: str, timeout: float) -> Tuple[str, int]:
    """One tool-less Responses call. Returns (text, tokens_used).

    Streaming, and assembled from deltas here rather than with the SDK's high-level
    ``responses.stream()``: Codex returns ``response.completed.response.output`` as
    null, which crashes that path (agent/auxiliary_client.py:1452).

    The Codex endpoint rejects ``max_output_tokens`` and ``temperature`` with a 400
    (agent/auxiliary_client.py:1383), so neither is sent. The model gets **no tools**
    — that limits direct actions by the research model; a brief can still carry injection.
    """
    stream = client.responses.create(
        model=model, instructions=instructions,
        input=[{"role": "user", "content": user}],
        store=False, stream=True, timeout=timeout,
    )
    chunks: List[str] = []
    tokens = 0
    for event in stream:
        etype = getattr(event, "type", "")
        if etype == "response.output_text.delta":
            chunks.append(getattr(event, "delta", "") or "")
        elif etype in ("response.failed", "error"):
            raise RuntimeError(f"codex stream {etype}")
        elif etype == "response.completed":
            usage = getattr(getattr(event, "response", None), "usage", None)
            tokens = int(getattr(usage, "total_tokens", 0) or 0)
    return "".join(chunks), tokens


def ask_json(client: OpenAI, model: str, instructions: str, user: str,
             timeout: float) -> Tuple[Dict[str, Any], int]:
    """``ask`` plus tolerant JSON extraction. The model is asked for JSON; a model that
    wraps it in prose or a fence is a formatting slip, not a failure worth aborting a
    job for, so the first balanced object in the text is taken."""
    text, tokens = ask(client, model, instructions, user, timeout)
    try:
        return json.loads(text), tokens
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1]), tokens
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise ValueError("model did not return JSON")
