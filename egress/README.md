# Egress proxy

Squid in `alfie-egress` is the only external route for the command sandbox and web worker.
No LLM, model client or external-account token runs here. HTTPS CONNECT is tunnelled without
TLS interception; ordinary HTTP is unencrypted and readable by the proxy.

## Policy

`squid.conf` is authoritative.
The public-host address markers are rendered from ignored `.env.local` by `deploy.sh`;
do not copy the source template directly into a running proxy.

Rules execute in this order:
1. Permit HTTP ports 80/443 and CONNECT only to 443.
2. Deny private, loopback, link-local, metadata, reserved and host public IP destinations using
   resolved destination addresses, regardless of the hostname's spelling.
3. For sandbox 172.31.240.3, permit only chatgpt.com. No Google access is needed after migration.
4. For web worker 172.31.240.4, permit public HTTP(S), including arbitrary webshop destinations.
5. Deny all other clients/requests. Caching is off; logs omit URLs/query strings.

The Docker internal bridge prevents direct internet routing. Host firewall additionally blocks
worker lateral/host access and proxy requests to non-public addresses; see `../deployment/`.
This independent packet filter matters for proxy compromise and DNS rebinding. Proxy's outward
address is fixed at 172.31.241.2 on a separate bridge. Neither worker can modify proxy config.

Public browsing removes the worker's former three-provider destination restriction. Egress
therefore **cannot prevent exfiltration of anything given to the public worker**. Keep mail,
personal records, Google/Telegram credentials and refresh tokens out of it. Sandbox policy
remains narrower; approved model traffic can still transmit any data present in the sandbox.

## Runtime

Squid listens on 3128, with a 128 MiB ceiling. Entry point adjusts stdout/stderr ownership before
Squid drops privileges to proxy; this is why CAP_CHOWN remains. Initial root startup and Squid's
proxy uid are not uid 10000. No ports are published.

`./deploy.sh` stages and builds; Compose owns restart. Validate `squid -k parse`, then run
public/private/direct/lateral probes. A configuration listing alone is not acceptance.
