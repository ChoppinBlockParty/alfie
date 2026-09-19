#!/bin/sh
# Dedicated chains: preserve unrelated Docker/user rules. Host + bridge enforcement.
set -eu
# A source template must never flush working rules before it has been rendered.
case '@@ALFIE_PUBLIC_IPV4@@' in *'@@'*) echo 'Render firewall.sh through deployment/deploy.sh first' >&2; exit 1;; esac
modprobe br_netfilter
sysctl -q -w net.bridge.bridge-nf-call-iptables=1
printf 'br_netfilter\n' > /etc/modules-load.d/alfie-bridge.conf
printf 'net.bridge.bridge-nf-call-iptables=1\n' > /etc/sysctl.d/90-alfie-bridge.conf
# Docker networks in this deployment have IPv6 disabled; Squid has no IPv6 route.
iptables -N ALFIE-FORWARD 2>/dev/null || true
iptables -F ALFIE-FORWARD
iptables -C DOCKER-USER -j ALFIE-FORWARD 2>/dev/null || iptables -I DOCKER-USER 1 -j ALFIE-FORWARD
iptables -A ALFIE-FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
iptables -A ALFIE-FORWARD -i eth0 -j DROP
# Workers may initiate only to proxy on the internal bridge.
for src in 172.31.240.3 172.31.240.4; do
    iptables -A ALFIE-FORWARD -s "$src" -d 172.31.240.5 -p tcp --dport 3128 -j RETURN
    iptables -A ALFIE-FORWARD -s "$src" -j DROP
done
# Egress must not initiate to other containers, the host or non-public destinations.
# Its internet-facing address is fixed by deployment/apply.py.
for src in 172.31.240.5 172.31.241.2; do
    for dst in 0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.168.0.0/16 192.0.0.0/24 192.0.2.0/24 198.18.0.0/15 198.51.100.0/24 203.0.113.0/24 224.0.0.0/3 @@ALFIE_PUBLIC_IPV4@@/32; do
        iptables -A ALFIE-FORWARD -s "$src" -d "$dst" -j DROP
    done
    iptables -A ALFIE-FORWARD -s "$src" -p tcp -m multiport --dports 80,443 -j RETURN
    # Docker's embedded resolver forwards DNS for Squid; no arbitrary UDP egress.
    iptables -A ALFIE-FORWARD -s "$src" -j DROP
done
iptables -A ALFIE-FORWARD -j RETURN
# INPUT, unlike DOCKER-USER, covers services on the host itself.
iptables -N ALFIE-HOST 2>/dev/null || true
iptables -F ALFIE-HOST
iptables -C INPUT -j ALFIE-HOST 2>/dev/null || iptables -I INPUT 1 -j ALFIE-HOST
iptables -A ALFIE-HOST -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
for src in 172.31.240.3 172.31.240.4 172.31.240.5 172.31.241.2; do
    iptables -A ALFIE-HOST -s "$src" -j DROP
done
iptables -A ALFIE-HOST -j RETURN
