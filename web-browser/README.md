# Interactive public-web browsing

The native assistant may use `browse` directly. Its fixed interface and isolated public worker,
not a conversational permission classifier, define the boundary.

Source subsystem for UC1/UC2 shopping preparation and UC3 interactive research. Runtime is
**inside alfie-websearch**; there is no fifth container. Deployment status and measurements
are recorded in [deployment acceptance](../deployment/acceptance.md).

## Interface and data flow

Hermes `browse` gateway plugin → mutual-TLS WebSocket on worker port 8770 → Playwright Chromium
→ Squid at 172.31.240.5:3128 → public HTTP(S). The worker returns bounded page text and element
references, not model-generated summaries. This path needs no model credential. `research`
continues to use a model access token and the same worker, exclusively with browser sessions.

`browse(action, session_id?, url?, ref?, value?, direction?)`:
- `open`: validate URL, launch Chromium, create a disposable context and one page, navigate.
- `snapshot`: return URL/title, at most 10,000 text characters and 80 visible controls.
- `click`, `fill`, `select`: act on an opaque reference from the latest snapshot. References are
  renewed after every action and refer to actual observed nodes, not model-provided JavaScript.
- `scroll`: up/down by 650 pixels. `back`: previous page. `close`: destroy browser and profile.

Every subsequent call supplies the returned session_id. Idle timeout 120 seconds, lifetime
600 seconds, maximum 60 actions. Reaper runs every 5 seconds. Each action has a 40-second
server deadline; gateway waits 50 seconds. Navigation waits up to 25 seconds, element operations
10 seconds. Timeout/operation failure closes the owning session. A foreign session cannot
close an active session. Research returns busy while a browser session exists.

## Boundaries

- Non-root uid 10000, all capabilities dropped, no-new-privileges, read-only rootfs, bounded
  tmpfs, no swap, core dumps disabled. Chromium sandbox remains **enabled**.
- Playwright 1.63.0 plus its matching Chromium are pinned in `../web-search/worker/Dockerfile`.
  `seccomp_profile.json` starts from Moby's official default profile and additionally permits
  `clone`, `unshare`, `setns`, and `chroot`, which Chromium needs for its user-namespace sandbox.
  The offline launch test must pass with `chromium_sandbox=True`. No SYS_ADMIN, added capability,
  privileged mode, or `--no-sandbox` is permitted.
- Public URLs on ports 80/443 only. URL checks block obvious local/IP targets, while Squid's
  resolved-address deny rules and host packet filtering enforce the network boundary. Redirects
  and subresources use the same proxy. No route to gateway, command sandbox or host services.
- Service workers, WebSockets, extra pages, media/fonts and downloads are disabled. No arbitrary
  evaluate, upload, cookie export, credential injection, screenshot or browser-debugging endpoint.
- Browser environment receives PATH/HOME/TMPDIR/LANG only; no model token. Research/browser
  still share a container: a full worker compromise can read its server TLS key and residual
  model token memory. This is the accepted consolidation tradeoff.
- No Google/Telegram/refresh tokens, personal records or HERMES_HOME mounts. Anonymous cookies
  exist in disposable session storage. No authentication or persistent profile.
- Password/file/email/tel inputs and recognized personal/payment fields are refused. This is
  a usability guard, **not** a guarantee against disguised fields or arbitrary website effects.
  Never send personal data, email, credentials or payment details to this tool.
- Raw webpage output can contain prompt injection. The gateway must treat it as untrusted;
  this subsystem does not make Google/Telegram actions immune to malicious page instructions.

## Shopping

Search public catalogues, inspect options/prices and prepare product/cart links. Do not submit
orders, log in, solve CAPTCHAs or automate payment. Owner completes checkout. Cart cookies usually
stay in this session; report product/variant/quantity when a cart cannot be transferred.

## Build and verify

`./deploy.sh` stages plugin/skill and calls `../web-search/deploy.sh` to rebuild the shared image.
`../deployment/deploy.sh` owns the coordinated cutover and network changes. The worker image
must be built with browser.py even when only research changes.

Local: `python3 -m unittest discover -s web-browser -p 'test_*.py'` from repository root.
VPS: offline `smoke_chromium.py`, then `deployment/verify.py` through gateway tools. Never use
`--no-sandbox` to bypass a launch failure. No purchases or messages in smoke tests.

Upstream references: https://playwright.dev/python/docs/api/class-browsertype and
https://github.com/moby/profiles/blob/main/seccomp/default.json.
