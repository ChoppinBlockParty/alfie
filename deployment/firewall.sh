#!/bin/sh
# One filter-table transaction: existing restrictions remain live until COMMIT.
set -eu
case '@@ALFIE_PUBLIC_IPV4@@' in *'@@'*) echo 'Render firewall.sh through deployment/deploy.sh first' >&2; exit 1;; esac
mode=${1:-apply}
case "$mode" in apply|--print) ;; *) echo 'Usage: firewall.sh [--print]' >&2; exit 2;; esac
add_forward=1
add_host=1
rules() {
    printf '%s\n' '*filter' ':ALFIE-FORWARD - [0:0]' ':ALFIE-HOST - [0:0]' '-F ALFIE-FORWARD' '-F ALFIE-HOST'
    [ "$add_forward" = 0 ] || printf '%s\n' '-I DOCKER-USER 1 -j ALFIE-FORWARD'
    [ "$add_host" = 0 ] || printf '%s\n' '-I INPUT 1 -j ALFIE-HOST'
    # Restrict worker sources before accepting established connections. This also
    # closes connections made under an older, more permissive policy.
    for pair in 172.31.240.3:2222 172.31.240.4:8770; do
        src=${pair%:*}
        port=${pair#*:}
        printf '%s\n' "-A ALFIE-FORWARD -s $src -d 172.31.240.5 -p tcp --dport 3128 -j RETURN"
        printf '%s\n' "-A ALFIE-FORWARD -s $src -d 172.31.240.2 -p tcp --sport $port -m conntrack --ctstate ESTABLISHED --ctdir REPLY -j RETURN"
        printf '%s\n' "-A ALFIE-FORWARD -s $src -j DROP"
    done
    for src in 172.31.240.5 172.31.241.2; do
        for dst in 172.31.240.3 172.31.240.4; do
            printf '%s\n' "-A ALFIE-FORWARD -s $src -d $dst -p tcp --sport 3128 -m conntrack --ctstate ESTABLISHED --ctdir REPLY -j RETURN"
        done
        for dst in 0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.168.0.0/16 192.0.0.0/24 192.0.2.0/24 198.18.0.0/15 198.51.100.0/24 203.0.113.0/24 224.0.0.0/3 @@ALFIE_PUBLIC_IPV4@@/32; do
            printf '%s\n' "-A ALFIE-FORWARD -s $src -d $dst -j DROP"
        done
        printf '%s\n' "-A ALFIE-FORWARD -s $src -p tcp -m multiport --dports 80,443 -j RETURN"
        printf '%s\n' "-A ALFIE-FORWARD -s $src -j DROP"
    done
    printf '%s\n' '-A ALFIE-FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN'
    printf '%s\n' '-A ALFIE-FORWARD -i eth0 -j DROP' '-A ALFIE-FORWARD -j RETURN'
    # Host access stays denied even for an old established worker connection.
    for src in 172.31.240.3 172.31.240.4 172.31.240.5 172.31.241.2; do
        printf '%s\n' "-A ALFIE-HOST -s $src -j DROP"
    done
    printf '%s\n' '-A ALFIE-HOST -j RETURN' 'COMMIT'
}
if [ "$mode" = --print ]; then
    rules
    exit 0
fi
# Serialize this updater; iptables-restore additionally acquires the xtables lock.
exec 9>/run/lock/alfie-firewall.lock
flock -x 9
modprobe br_netfilter
sysctl -q -w net.bridge.bridge-nf-call-iptables=1
printf 'br_netfilter\n' > /etc/modules-load.d/alfie-bridge.conf
printf 'net.bridge.bridge-nf-call-iptables=1\n' > /etc/sysctl.d/90-alfie-bridge.conf
# Docker networks must retain IPv6 disabled; IPv6 requires a separate policy.
iptables -w 10 -C DOCKER-USER -j ALFIE-FORWARD 2>/dev/null && add_forward=0
iptables -w 10 -C INPUT -j ALFIE-HOST 2>/dev/null && add_host=0
policy_file=$(mktemp /run/alfie-firewall.XXXXXX)
trap 'rm -f "$policy_file"' EXIT HUP INT TERM
rules > "$policy_file"
iptables-restore --wait 10 --noflush --test < "$policy_file"
iptables-restore --wait 10 --noflush < "$policy_file"
