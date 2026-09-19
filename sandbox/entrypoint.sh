#!/bin/sh
# Host key lives in /etc/ssh/keys, which compose backs with a named volume. Without
# that, every `docker compose up -d --force-recreate sandbox` mints a new host key
# and the gateway's known_hosts entry stops matching — which, under
# StrictHostKeyChecking=accept-new, fails the backend at the worst possible moment.
set -e

mkdir -p /etc/ssh/keys
if [ ! -f /etc/ssh/keys/ssh_host_ed25519_key ]; then
    echo "entrypoint: minting host key" >&2
    ssh-keygen -q -t ed25519 -N '' -f /etc/ssh/keys/ssh_host_ed25519_key
fi
chmod 600 /etc/ssh/keys/ssh_host_ed25519_key
chmod 644 /etc/ssh/keys/ssh_host_ed25519_key.pub

# sshd starts every session with a sanitized environment: the container's own env
# does NOT reach it, and with `UsePAM no` /etc/environment is not read either. So
# the proxy variables have to be handed to sshd explicitly, or the sandbox — which
# sits on an internal network with no route of its own — fails every outbound call
# with a timeout that looks like a network fault rather than a missing variable.
#
# Generated here from the container env so compose stays the single source of truth.
# One SetEnv line, not several: sshd applies only the first instance of the keyword.
ENVCONF=/etc/ssh/sshd_config.d/20-env.conf
pairs=""
for v in HTTP_PROXY HTTPS_PROXY http_proxy https_proxy NO_PROXY no_proxy; do
    eval "val=\${$v:-}"
    [ -n "$val" ] && pairs="$pairs $v=$val"
done
if [ -n "$pairs" ]; then
    echo "SetEnv$pairs" > "$ENVCONF"
else
    rm -f "$ENVCONF"
fi
chmod 644 "$ENVCONF" 2>/dev/null || true

# sshd's privilege-separation directory. Must exist and be root-owned and 0755.
mkdir -p /run/sshd
chmod 755 /run/sshd

exec /usr/sbin/sshd -D -e
