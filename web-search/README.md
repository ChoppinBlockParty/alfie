# Web research and shared public-web worker

UC3. `research(question, depth)` runs plan → search → select → read → analyse → repeat →
synthesise in alfie-websearch and returns a bounded brief. `web-browser/` supplies interactive
Chromium browsing inside the same container. Subsystem source ownership remains separate;
`worker/Dockerfile` and `worker/server.py` own the shared runtime.

## Research behavior

`retrieval.py` uses Tavily `/search` and Firecrawl `/v2/scrape`. They fetch pages server-side.
Current deployment uses keyless access and mounts no provider credentials. Optional provider-key
support exists in source but enabling it would change the worker credential boundary.

`research.py` uses gpt-5.5 with no tools. quick = 1 round / 4 pages; deep = 3 rounds / 12 pages.
Each page is capped at 12,000 characters. Wall-clock budget 300 seconds, token ceiling 120,000.
The result is rebuilt from structured fields: conclusion ≤1200 characters, ≤8 findings of
≤200 characters, ≤12 sources. Model-emitted links are stripped; source URLs come from retrieval.
Injection markers are reported, not treated as a guarantee that content is safe. A malicious
page can still influence the brief or the gateway that reads it.

Historical sizing samples (September 13): quick 12,384 tokens / 36.9 s / 1,781 output characters;
deep 45,584 tokens / 263 s / 6,446 characters. These are examples, not current latency guarantees.

## Shared runtime and protocol

Worker listens on 8770 using mutual TLS. Gateway uses its client certificate; worker uses its
own server key. No published ports. Source firewall rejects command-sandbox connections.
Messages:
- `ask`: id, question, depth, access_token, expires_at; returns progress then result/error.
- `browser`: id plus action/session_id/url/ref/value/direction; returns browser result/error.
- Browser and research are mutually exclusive. Research refuses while a browser session exists.
- A 5-second reaper closes idle/expired browser sessions. See `../web-browser/README.md`.

The gateway plugin resolves OpenAI authentication before dispatch with refresh skew 420 seconds
(300-second task plus 120-second margin). Refresh token and auth.json stay in gateway. Access
tokens are not inherently short-lived: previously measured lifetime was 10 days. No paid API
fallback. Worker constructs the client per research job and closes it afterward. Python strings
cannot be reliably erased, so zeroization is best effort, not a promise of no remaining copies.

The worker has a read-only rootfs, bounded tmpfs, 1280 MiB memory ceiling/no swap, 256 PID cap,
1.5 CPU ceiling, no capabilities and no-new-privileges. Core dumps are disabled. The worker holds
its TLS server key and temporarily a model access token; it mounts no Google/Telegram credentials,
mailbox, records or gateway home. Browser and research share this compromise boundary.

Public browsing requires public HTTP(S) egress rather than the old three-provider allowlist.
The proxy and host firewall reject private/reserved destinations and lateral/host access.
Do not send confidential material to the public worker: its public egress can disclose it.

## Deployment

`./deploy.sh` stages server/research/browser code, builds alfie-websearch:latest, stages the
research plugin and creates missing PKI only. Existing certificates are never silently rotated.
`../web-browser/deploy.sh` also stages browser plugin/skill. `../deployment/deploy.sh` owns the
coordinated configuration and restart. Plugins must be enabled in gateway config.

PKI lives at `/opt/alfie/websearch/pki`, outside HERMES_HOME and sandbox sync. CA private key is
root-only; gateway mounts client key/cert/CA, worker mounts server key/cert/CA. Certificate
expiry is tracked in private operator records. Rotate both ends deliberately.

Tests: `python3 -m unittest discover -s web-search -p 'test_*.py'`.
Live acceptance: `../deployment/verify.py`, plus a real research call without printing private
content or tokens. Do not mistake summaries for a complete prompt-injection boundary.
