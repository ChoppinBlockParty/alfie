#!/bin/sh
# squid opens its log targets *after* dropping to cache_effective_user (proxy),
# and /dev/stdout is the container's stdout pipe, owned by root. Without this it
# dies at startup with "Cannot open '/dev/stdout' for writing", which reads like a
# config error and is really a privilege-drop ordering problem.
set -e
chown proxy:proxy /dev/stdout /dev/stderr 2>/dev/null || true
exec /usr/sbin/squid -N -d1 -f /etc/squid/squid.conf
