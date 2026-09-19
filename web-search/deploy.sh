#!/usr/bin/env bash
# Deploy the web-search worker and its gateway plugin. Idempotent; safe to re-run.
#
# Does NOT restart the gateway: installing the plugin needs one, but that is a
# deliberate act and belongs to the operator, not to a deploy script.
set -euo pipefail

DIR=$(cd "$(dirname "$0")" && pwd)
source "$DIR/../deployment/local-env.sh"
DEST=/opt/alfie/websearch
PKI=$DEST/pki
DATA=/opt/alfie/data

ssh "$HOST" "mkdir -p $DEST/worker"
scp -q "$DIR/worker/Dockerfile" "$DIR/worker/codex.py" "$DIR/worker/retrieval.py" \
       "$DIR/worker/research.py" "$DIR/worker/server.py" "$DIR/../web-browser/worker/browser.py" "$HOST:$DEST/worker/"

# --- PKI ------------------------------------------------------------------
# Generated on the box, never in $HERMES_HOME: that tree is the sandbox's sync
# source and the backup target, and these keys belong to neither. Generated once;
# re-running never rotates silently, because a silent rotation would break the
# running gateway's client certificate.
ssh "$HOST" "set -euo pipefail
  mkdir -p $PKI && chmod 700 $PKI
  cd $PKI
  if [ ! -f ca.crt ]; then
    echo 'minting CA'
    openssl req -x509 -newkey rsa:3072 -sha256 -days 3650 -nodes \
      -keyout ca.key -out ca.crt -subj '/CN=alfie-websearch-ca'
    chmod 600 ca.key
  fi
  if [ ! -f server.crt ]; then
    echo 'minting server cert'
    openssl req -newkey rsa:3072 -nodes -keyout server.key -out server.csr \
      -subj '/CN=websearch'
    printf 'subjectAltName=DNS:websearch,DNS:alfie-websearch,IP:172.31.240.4\nextendedKeyUsage=serverAuth\n' > server.ext
    openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
      -out server.crt -days 3650 -sha256 -extfile server.ext
    chmod 600 server.key; rm -f server.csr server.ext
  fi
  if [ ! -f client.crt ]; then
    echo 'minting client cert'
    openssl req -newkey rsa:3072 -nodes -keyout client.key -out client.csr \
      -subj '/CN=alfie-gateway'
    printf 'extendedKeyUsage=clientAuth\n' > client.ext
    openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
      -out client.crt -days 3650 -sha256 -extfile client.ext
    chmod 600 client.key; rm -f client.csr client.ext
  fi
  # Both the gateway and the worker run as uid 10000 and must read their own half.
  # The CA key stays root-only: nothing at runtime needs it, only a future rotation.
  chown 10000:10000 client.crt client.key ca.crt server.crt server.key
  chmod 640 client.key server.key
  chmod 600 ca.key
  openssl x509 -in server.crt -noout -enddate | sed 's/^/server cert /'
  openssl x509 -in client.crt -noout -enddate | sed 's/^/client cert /'"

# --- worker image ---------------------------------------------------------
ssh "$HOST" "docker build -t alfie-websearch:latest $DEST/worker"

# --- gateway plugin -------------------------------------------------------
ssh "$HOST" "mkdir -p $DATA/plugins/websearch $DEST/gateway-plugin"
scp -q "$DIR/gateway-plugin/__init__.py" "$DIR/gateway-plugin/plugin.yaml" \
       "$HOST:$DATA/plugins/websearch/"
scp -q "$DIR/gateway-plugin/__init__.py" "$DIR/gateway-plugin/plugin.yaml" "$HOST:$DEST/gateway-plugin/"
ssh "$HOST" "chown -R 10000:10000 $DATA/plugins/websearch && chmod 644 $DATA/plugins/websearch/* $DEST/gateway-plugin/*"

echo
echo "Deployed. The plugin is loaded at gateway start:"
echo "  docker compose -f /opt/alfie/docker-compose.alfie.yml up -d"
