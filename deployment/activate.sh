#!/usr/bin/env bash
# Run on VPS after all images and immutable files are staged and smoke checks pass.
set -euo pipefail
ROOT=/opt/alfie
python3 "$ROOT/deployment/apply.py"
docker compose -f "$ROOT/docker-compose.alfie.yml.next" config --quiet
# Fail before cutover if the new proxy policy cannot parse.
docker run --rm --network none --entrypoint /usr/sbin/squid alfie-egress:latest -k parse >/dev/null 2>&1
# Apply traffic restrictions before public browsing is made available.
install -m 755 "$ROOT/deployment/firewall.sh" /usr/local/sbin/alfie-docker-firewall.sh
/usr/local/sbin/alfie-docker-firewall.sh
mv "$ROOT/docker-compose.alfie.yml.next" "$ROOT/docker-compose.alfie.yml"
mv "$ROOT/data/config.yaml.next" "$ROOT/data/config.yaml"
# Stop scheduling/model activity during the credential cutover.
docker compose -f "$ROOT/docker-compose.alfie.yml" stop gateway
docker compose -f "$ROOT/docker-compose.alfie.yml" up -d --force-recreate sandbox egress websearch
/usr/local/sbin/alfie-docker-firewall.sh
docker compose -f "$ROOT/docker-compose.alfie.yml" up -d gateway
# DOCKER-USER bridge rules must survive daemon and host restarts.
systemctl enable alfie-docker-firewall.service >/dev/null
printf '%s\n' 'Activated. Run deployment/verify.py before recording acceptance.'
