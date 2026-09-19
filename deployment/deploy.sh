#!/usr/bin/env bash
# Build/stage, validate Chromium offline, then perform coordinated four-container cutover.
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
python3 "$DIR/render.py" "$DIR/firewall.sh" >/dev/null
python3 "$DIR/render.py" "$DIR/../egress/squid.conf" >/dev/null
ssh "$ALFIE_VPS_HOST" 'mkdir -p /opt/alfie/deployment'
scp -q "$DIR/prepare.py" "$DIR/apply.py" "$DIR/sandbox_mounts.py" "$DIR/activate.sh" "$DIR/measure.py" "$ALFIE_VPS_HOST:/opt/alfie/deployment/"
for template in firewall.sh verify.py; do
    python3 "$DIR/render.py" "$DIR/$template" | ssh "$ALFIE_VPS_HOST" "umask 077; cat > /opt/alfie/deployment/$template"
done
ssh "$ALFIE_VPS_HOST" 'python3 /opt/alfie/deployment/prepare.py'
"$DIR/../google-workspace/deploy.sh"
bash "$DIR/../email-watch/stage.sh"
"$DIR/../sandbox/deploy.sh"
"$DIR/../egress/deploy.sh"
"$DIR/../web-browser/deploy.sh"
scp -q "$DIR/../web-browser/seccomp_profile.json" "$DIR/../web-browser/smoke_chromium.py" "$ALFIE_VPS_HOST:/opt/alfie/web-browser/"
ssh "$ALFIE_VPS_HOST" 'docker run --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=384m,mode=1777 --memory 1280m --memory-swap 1280m --pids-limit 256 --cap-drop ALL --security-opt no-new-privileges:true --security-opt seccomp=/opt/alfie/web-browser/seccomp_profile.json -v /opt/alfie/web-browser/smoke_chromium.py:/test.py:ro --entrypoint /opt/venv/bin/python3 alfie-websearch:latest /test.py'
ssh "$ALFIE_VPS_HOST" 'bash /opt/alfie/deployment/activate.sh'
ssh "$ALFIE_VPS_HOST" 'python3 /opt/alfie/deployment/verify.py --research'
