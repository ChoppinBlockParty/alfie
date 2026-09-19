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
import ipaddress
import json
import time
from functools import lru_cache
from urllib.parse import urlsplit
from typing import Any, Dict, List

# httpx is imported inside the call sites, not here, so this module — and the loop
# that imports it — stays importable for unit tests without the worker's venv.

TAVILY_BASE_URL = os.environ.get("TAVILY_BASE_URL", "https://api.tavily.com")
FIRECRAWL_BASE_URL = os.environ.get("FIRECRAWL_API_URL", "https://api.firecrawl.dev")
CLIENT_NAME = "hermes-agent"
HTTP_TIMEOUT = 60.0
MAX_RESPONSE = 2 * 1024 * 1024


@lru_cache(maxsize=128)
def public_addresses(host):
    """Public worker has no direct DNS. Resolve through fixed HTTPS over existing egress.

    This cache lives only in the disposable research child (maximum 300 seconds).
    """
    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        addresses = []
        for kind in ('A', 'AAAA'):
            data = request_json('GET', 'https://cloudflare-dns.com/dns-query',
                {'name': host, 'type': kind}, {'Accept': 'application/dns-json'}, timeout=10, limit=64 * 1024)
            if type(data.get('Status')) is not int or data['Status'] != 0 or data.get('TC', False) is not False \
                    or not isinstance(data.get('Answer', []), list):
                raise ValueError('Public DNS lookup failed')
            for answer in data.get('Answer', []):
                if not isinstance(answer, dict):
                    raise ValueError('Invalid DNS answer')
                if answer.get('type') in (1, 28):
                    addresses.append(str(ipaddress.ip_address(answer.get('data', ''))))
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError('Non-public destination address')
    return tuple(addresses)


def public_url(url):
    """Preflight only: the remote scraper controls its own DNS and redirects."""
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        raise ValueError('Invalid public URL')
    parsed = urlsplit(url)
    host = parsed.hostname
    if parsed.scheme not in ('http', 'https') or not host or parsed.username is not None \
            or parsed.password is not None or parsed.port not in (None, 80, 443) \
            or '\\' in url or '%' in host:
        raise ValueError('Invalid public URL destination')
    host = host.rstrip('.').encode('idna').decode('ascii').lower()
    if '.' not in host and ':' not in host or host.endswith(('.localhost', '.local', '.internal', '.test')):
        raise ValueError('Non-public hostname')
    public_addresses(host)
    return url


def request_json(method, url, payload, headers, *, timeout=HTTP_TIMEOUT, limit=MAX_RESPONSE):
    """Bound raw bytes before JSON parsing; reject compression and redirects."""
    import httpx
    deadline = time.monotonic() + timeout
    try:
        with httpx.stream(method, url, **({'json': payload} if method == 'POST' else {'params': payload}),
                          headers={**headers, 'Accept-Encoding': 'identity'},
                          timeout=timeout, follow_redirects=False) as response:
            if not 200 <= response.status_code < 300:
                raise VendorFailed('Retrieval provider rejected request')
            if response.headers.get('content-encoding', 'identity').lower() not in ('', 'identity'):
                raise VendorFailed('Compressed provider response refused')
            length = response.headers.get('content-length')
            if length is not None and (not length.isdigit() or int(length) > limit):
                raise VendorFailed('Provider response too large')
            content = bytearray()
            for chunk in response.iter_raw(chunk_size=16384):
                if time.monotonic() >= deadline or len(content) + len(chunk) > limit:
                    raise VendorFailed('Provider response budget exhausted')
                content.extend(chunk)
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError('Expected object')
        return result
    except (httpx.HTTPError, ValueError, RecursionError):
        raise VendorFailed('Retrieval transport or response invalid') from None


def post_json(url, payload, headers):
    return request_json('POST', url, payload, headers)


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
    if not isinstance(query, str) or not 1 <= len(query) <= 2000 or type(limit) is not int or not 1 <= limit <= 10:
        raise VendorFailed('Invalid search request')
    payload = {"query": query, "max_results": limit,
               "include_raw_content": False, "include_images": False}
    results = post_json(f"{TAVILY_BASE_URL}/search", payload, _tavily_headers()).get('results', [])
    if not isinstance(results, list) or len(results) > 100:
        raise VendorFailed('Invalid search response')
    output = []
    for row in results[:limit]:
        if not isinstance(row, dict) or any(not isinstance(row.get(k, ''), str) for k in ('title', 'url', 'content')):
            raise VendorFailed('Invalid search result')
        try:
            url = public_url(row.get('url', ''))
        except (ValueError, OSError, VendorFailed):
            continue
        output.append({'title': row.get('title', '')[:500], 'url': url,
                       'snippet': row.get('content', '')[:4000], 'position': len(output) + 1})
    return output


def _firecrawl_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def extract(url: str, page_chars: int) -> Dict[str, Any]:
    """{url, title, text, error} — a per-page failure is an entry, not an exception,
    because one dead link must not lose the other three pages of the round."""
    try:
        public_url(url)
        if type(page_chars) is not int or not 1 <= page_chars <= 12000:
            raise ValueError('Invalid page budget')
        data = post_json(f"{FIRECRAWL_BASE_URL}/v2/scrape",
                         {'url': url, 'formats': ['markdown']}, _firecrawl_headers()).get('data') or {}
        if not isinstance(data, dict):
            raise ValueError('Invalid page response')
        text = data.get('markdown') or data.get('content') or ''
        meta = data.get('metadata') or {}
        if not isinstance(text, str) or not isinstance(meta, dict) or not isinstance(meta.get('title', ''), str):
            raise ValueError('Invalid page fields')
        return {'url': url, 'title': meta.get('title', '')[:500], 'text': text[:page_chars], 'error': ''}
    except Exception as exc:  # noqa: BLE001 — per-page error entry is the contract
        return {"url": url, "title": "", "text": "", "error": type(exc).__name__}
