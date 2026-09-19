# Deployment acceptance — 2026-09-19

Status: deployed and verified on the privately configured deployment target. Four running containers: alfie, alfie-sandbox,
alfie-websearch and alfie-egress. Browser code is part of the shared worker image; no fifth container.
Images were built locally; subsystem Dockerfiles use official Debian 13. Hermes source remains
revision `77915e344cb0cd8e20661d4a7b393f987a2eef32`.

## Verified

- 36 local tests passed: browser 9, Google argument validation 3, research 24. `git diff --check` passed.
- Chromium launched in an offline container with its own sandbox enabled, deployed seccomp,
  all capabilities dropped, no-new-privileges, read-only rootfs and bounded memory/tmpfs.
- Gateway discovers browse, research and google_workspace. Native gateway browser/web toolsets
  are disabled. The real Hermes code execution environment is SSH, and credential files are absent
  there. Read guards reject .env/auth.json/Google credential filenames; credential registration and
  all credential forwarding are refused. No container has Docker socket access or privileged mode.
- Google labels read succeeds. Existing email-watch remains configured as `no_agent`. Its unrelated
  local code edits were preserved and not deployed. These checks do not claim a complete cron run.
- Public browser open/snapshot/click/back/fill/close succeeded using example.com, Books to Scrape
  and the httpbin demonstration form. The form was not submitted. A foreign session cannot close
  the owner's browser; research returns busy during that session.
- Metadata URL and public-to-metadata redirect refused. Proxy rejects loopback, metadata, gateway,
  VPS public IP and a hostname resolving to loopback. Direct worker traffic to gateway, sandbox,
  host and internet is denied; the gateway test used a live temporary listener on port 18888.
- Sandbox proxy rejects general web, Google and metadata requests, while CONNECT to chatgpt.com:443
  succeeds without a token. Direct sandbox traffic to worker, host and public internet is denied.
- Worker refuses a caller without a mutual-TLS certificate, with explicit server CA verification.
  Gateway browser and research calls authenticate successfully with their client certificate.
- End-to-end research succeeded after the redirect fix; returned 1369 characters for the public
  example.com/IANA question. No private content or credential values were printed.
- Browser close terminates Chromium; only the Python worker remained. Resource limits and
  read-only worker rootfs are active. Firewall service is enabled and bridge filtering is 1.

## Resource samples

Host: 2 vCPU, 3814 MiB RAM, 2047 MiB swap. After verification: 2621 MiB available RAM,
110 MiB swap used, 12 GiB free on the 38 GiB root filesystem.

`measure.py`, same public example.com session, Docker memory usage:

| Container | Browser open | Browser closed | RAM ceiling |
|---|---:|---:|---:|
| Gateway | 570.4 MiB | 552.5 MiB | 1024 MiB |
| Sandbox | 16.84 MiB | 16.84 MiB | 512 MiB |
| Research/browser | 288.9 MiB | 136.4 MiB | 1280 MiB |
| Squid | 11.99 MiB | 11.99 MiB | 128 MiB |

These are point samples, not peaks or worst-case sizing. Worker memory fell by 152.5 MiB after
close. Sandbox and worker cannot use swap. One research job or one browser session is allowed.

## Limits and deferred verification

No host reboot or disaster-recovery restore was performed. Persistence configuration and enabled
firewall service were checked. Idle/lifetime/action expiry has unit coverage; long-duration browser
soak and large-site peak-memory tests were not performed. Public fixtures do not guarantee every
webshop works. Authentication, CAPTCHA, popup-only flows, payment and completed purchases remain
outside scope. No email, Telegram message, calendar write or purchase was sent during acceptance.

Browser and research share a compromise boundary: a compromised worker could access its TLS key
and any in-flight model access token. Public egress can disclose any input sent there. No Google,
Telegram, refresh token or personal-record mount is supplied to the worker. Page text and research
summaries remain untrusted. Input-field heuristics do not guarantee prevention of disguised
payment/login actions. The command sandbox still reads shared personal records and approved
model traffic can transmit them; this build provisions no model token to shell commands.

Rollback images/configuration were retained. Unused build cache was pruned during deployment;
current/tagged images, volumes and personal data were preserved. See [operations](README.md).
