#!/usr/bin/env bash
# Existing-image security cutover: no builds, no new services, no Google writes.
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/local-env.sh"
python3 "$DIR/../google-workspace/render_approval_policy.py" --check
python3 "$DIR/render.py" "$DIR/firewall.sh" >/dev/null
python3 "$DIR/render.py" "$DIR/verify.py" >/dev/null
scp -q "$DIR/prepare.py" "$DIR/apply.py" "$DIR/sandbox_mounts.py" "$ALFIE_VPS_HOST:/opt/alfie/deployment/"
ssh "$ALFIE_VPS_HOST" 'python3 /opt/alfie/deployment/prepare.py'
# Stop before replacing any bind-mounted sources. Failure leaves the gateway stopped;
# inspect/repair or restore the private backup rather than restarting a mixed release.
ssh "$ALFIE_VPS_HOST" 'docker stop alfie >/dev/null'
bash "$DIR/../google-workspace/deploy.sh"
bash "$DIR/../email-watch/stage.sh"
for template in firewall.sh verify.py; do
    python3 "$DIR/render.py" "$DIR/$template" | ssh "$ALFIE_VPS_HOST" "python3 -c 'import pathlib,sys; p=pathlib.Path(\"/opt/alfie/deployment/$template\"); p.write_bytes(sys.stdin.buffer.read()); p.chmod(0o700)'"
done
ssh "$ALFIE_VPS_HOST" 'python3 /opt/alfie/deployment/apply.py && docker compose -f /opt/alfie/docker-compose.alfie.yml.next config --quiet && bash /opt/alfie/deployment/firewall.sh'
ssh "$ALFIE_VPS_HOST" 'install -m 755 /opt/alfie/deployment/firewall.sh /usr/local/sbin/alfie-docker-firewall.sh && mv /opt/alfie/docker-compose.alfie.yml.next /opt/alfie/docker-compose.alfie.yml && mv /opt/alfie/data/config.yaml.next /opt/alfie/data/config.yaml && docker compose -f /opt/alfie/docker-compose.alfie.yml up -d --no-build --force-recreate sandbox && /usr/local/sbin/alfie-docker-firewall.sh && docker compose -f /opt/alfie/docker-compose.alfie.yml up -d --no-build gateway'
printf '%s\n' 'Security code activated using existing images. Run verification before recording acceptance.'
