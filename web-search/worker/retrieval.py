"""Tavily search and Firecrawl extract, called directly.

The worker has no Hermes, so it cannot use the bundled plugins. These are the same
endpoints and the same keyless handshakes those plugins use, read off the source on
the box rather than copied from documentation:

  Tavily    plugins/web/tavily/provider.py:28-36,44  — POST {base}/search, and
            keyless is the header X-Tavily-Access-Mode: keyless with NO Authorization
  Firecrawl plugins/web/firecrawl/provider.py:24,103-118 — POST {base}/v2/scrape,
            keyless is simply the absence of an Authorization header

Neither vendor is given a key here. When TAVILY_API_KEY / FIRECRAWL_API_KEY appear,
they are picked up from the environment and the keyless handshake is dropped — the
same switch the gateway's ``provider_tier: auto`` makes.

Research retrieval uses server-side fetching. Interactive browsing in browser.py
fetches public pages directly through Squid; the shared worker has public HTTP(S) egress.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

# httpx is imported inside the call sites, not here, so this module — and the loop
# that imports it — stays importable for unit tests without the worker's venv.

TAVILY_BASE_URL = os.environ.get("TAVILY_BASE_URL", "https://api.tavily.com")
FIRECRAWL_BASE_URL = os.environ.get("FIRECRAWL_API_URL", "https://api.firecrawl.dev")
CLIENT_NAME = "hermes-agent"
HTTP_TIMEOUT = 60.0


class VendorFailed(RuntimeError):
    """Search or extract failed in a way the round cannot continue past."""


def _tavily_headers() -> Dict[str, str]:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    headers = {"X-Client-Name": CLIENT_NAME}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    else:
        headers["X-Tavily-Access-Mode"] = "keyless"
    return headers


def search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """[{title, url, snippet, position}] — never raises for an empty result set, only
    for a transport or status failure, so a thin round is a gap and not an abort."""
    import httpx

    payload = {"query": query, "max_results": limit,
               "include_raw_content": False, "include_images": False}
    try:
        response = httpx.post(f"{TAVILY_BASE_URL}/search", json=payload,
                              headers=_tavily_headers(), timeout=HTTP_TIMEOUT)
    except httpx.HTTPError as exc:
        raise VendorFailed(f"tavily transport: {type(exc).__name__}") from None
    if response.status_code >= 400:
        raise VendorFailed(f"tavily http {response.status_code}")
    results = response.json().get("results") or []
    return [{"title": r.get("title", "") or "", "url": r.get("url", "") or "",
             "snippet": r.get("content", "") or "", "position": i + 1}
            for i, r in enumerate(results) if r.get("url")]


def _firecrawl_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def extract(url: str, page_chars: int) -> Dict[str, Any]:
    """{url, title, text, error} — a per-page failure is an entry, not an exception,
    because one dead link must not lose the other three pages of the round."""
    import httpx

    try:
        response = httpx.post(f"{FIRECRAWL_BASE_URL}/v2/scrape",
                              json={"url": url, "formats": ["markdown"]},
                              headers=_firecrawl_headers(), timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        data = response.json().get("data") or {}
    except Exception as exc:  # noqa: BLE001 — per-page error entry is the contract
        return {"url": url, "title": "", "text": "", "error": type(exc).__name__}
    text = data.get("markdown") or data.get("content") or ""
    meta = data.get("metadata") or {}
    return {"url": url, "title": meta.get("title", "") or "",
            "text": text[:page_chars], "error": ""}
