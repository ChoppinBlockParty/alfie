# Alfie egress proxy — the sandbox's and the web-search worker's only route off
# the host. Upstream's own design: docs/security/network-egress-isolation.md.
#
# Self-built from debian:13; spec forbids unofficial Docker Hub images.
FROM debian:13

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        squid ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY squid.conf /etc/squid/squid.conf
COPY entrypoint.sh /usr/local/sbin/entrypoint.sh
RUN chmod 755 /usr/local/sbin/entrypoint.sh

# -N foreground, -d1 log to stderr so `docker logs` sees denials.
ENTRYPOINT ["/usr/local/sbin/entrypoint.sh"]
