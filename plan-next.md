# Alfie — four-container execution plan

Date: 2026-09-19. Status: deployed; acceptance passed. Authorization: owner requested preparation and deployment.
Use cases: UC1/UC2 public shopping preparation; UC3 interactive public-web research; UC5 Google operations.
History belongs in git. This file records the executable build and its verification status.

## Accepted design

Keep gateway, command sandbox, research/browser worker, and egress proxy. No Docker socket
inside any container. Google operations move to a gateway plugin. Interactive browsing is
its own source subsystem (`web-browser/`) but shares `alfie-websearch` at runtime. Public browsing
has no login, payment, mailbox, persistent profile or personal-record mounts. The browser and
research worker share a compromise boundary, including the worker's service TLS key and any
in-flight model access token. OpenAI refresh credentials stay in the gateway.

Enforced RAM ceilings: gateway 1024 MiB, sandbox 512 MiB, research/browser 1280 MiB, egress 128 MiB.
These are enforced budgets, not reservations or measured peaks. One research job OR one browser
session at a time. Browser starts on demand, has idle and absolute expiry, and closes on error.

## 1. Inventory and preparation

- [x] Read subsystem sources and existing local changes; preserve email-watch edits.
- [x] Connect to VPS without disclosing credentials; confirm four containers and 3814 MiB RAM.
- [x] Inspect mounts, resource limits, credential-sync source and firewall.
- [x] Back up operational config and plugin/skill files on VPS in a root-only directory.
- [x] Capture rollback image IDs; do not prune rollback images or personal data.

## 2. Google boundary (`google-workspace/`)

- [x] Implement a gateway plugin with fixed Google operations and typed argument validation.
      No arbitrary command, URL, local file upload/download or credential-return operation.
      Preserve Gmail search/get/send/reply/labels/modify, calendar list/create/delete and
      supported Drive/Contacts/Docs/Sheets operations that do not touch arbitrary files.
- [x] Keep existing MIME parsing and email-watch behavior; deploy no unrelated email-watch changes.
- [x] Replace skill instructions and remove credential-sync declarations.
- [x] Add Google credential filenames to upstream read/sync protection using a reproducible patch.
- [x] Remove sandbox Google mounts and configured credential forwarding; recreate the sandbox.
- [x] Verify through Hermes's actual execution environment that credentials cannot be read or synced.
- [x] Test a read-only Google operation without printing email content; report re-auth if necessary.

## 3. Browser subsystem (`web-browser/`)

- [x] Build pinned Playwright plus Chromium into the shared worker image; no extra container.
- [x] Implement open/snapshot/click/fill/select/scroll/back/close over existing mutual TLS.
      Bounded text and element inventory, opaque session ID, one page, no arbitrary JavaScript,
      cookies export, file upload/download, credential injection or persistent profile API.
- [x] Block non-HTTP(S) navigation and private/reserved IP targets; enforce independently in proxy
      and host firewall. Disable service workers, popups and WebSockets for this first build.
- [x] Block password/payment input types and document that UI heuristics are not a security boundary.
- [x] Keep Chromium's own sandbox enabled; verify it works on this host. Do not silently disable it.
- [x] Serialize browser and research work; expire idle sessions and cap lifetime/actions.
- [x] Register gateway tool and skill; disable native gateway browser/web tools that bypass this path.

## 4. Network and deployment (`deployment/`, `egress/`)

- [x] Sandbox retains restricted egress. Worker gets public HTTP(S), with private/reserved destinations
      denied before allow rules. Deny cross-container initiation except required proxy traffic;
      gateway may initiate SSH and worker TLS. Block access to host services, including public host IP.
- [x] Persist firewall rules, br_netfilter and bridge filtering. Test direct and proxied bypasses.
- [x] Apply resource caps and no-swap worker policy; keep rootfs read-only and bounded tmpfs.
- [x] Stage all images/plugins before cutover; validate configuration without printing secrets.
- [x] Restart only required services. Keep gateway service and Telegram identity unchanged.

## 5. Acceptance and documentation

- [x] Unit tests: browser URL/action policy, session ownership/lifecycle, Google argument handling.
- [x] Integration: controlled public page with navigation, click and fill; normal public site;
      private IP, localhost, metadata, redirected private target and direct network attempts denied.
- [x] Integration: research still works, simultaneous work rejected, browser closes and memory drops.
- [x] Negative boundary tests: credential registration refused, sandbox clean, worker cannot reach
      gateway/sandbox/host, unauthenticated TLS caller rejected, no Docker socket.
- [x] Gateway discovers plugins; Google read-only check; existing cron remains configured.
- [x] Record measured RAM and limitations; rewrite main-spec to current state, remove stale decisions
      and old build narratives; update affected subsystem READMEs.

## Rollback

Staging changes bind-mounted plugin files; treat deployment as a maintenance window even before
cutover. After cutover restore matching saved Compose, config, skills/plugins and image tags,
then recreate affected services and reconcile the firewall with the restored network layout.
A rollback that restores Google sandbox access is a security regression: prefer keeping the
new Google boundary while disabling the browser if browser-only checks fail. Never use
`terminal.backend: local` as a security rollback. No automated external messages or purchases
are part of acceptance tests.

## Evidence and deferred work

See [acceptance](deployment/acceptance.md) for live results and memory samples, and
[deployment instructions](deployment/README.md) for repeat deployment and rollback.

- LLM commands in the SSH sandbox still need explicit model access-token provisioning.
- Firewall persistence is configured and enabled; a host reboot was not part of acceptance.
- Browser compatibility and peak memory on large sites are not guaranteed by these smoke tests.
- Maintain Chromium updates and rotate worker PKI deliberately. Existing CA metadata requires
  explicit CA/hostname verification without Python's additional strict X.509 verification flag.
