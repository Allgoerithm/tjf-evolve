#!/usr/bin/env bash
# Build and start the leaderboard stack on the VM (run via provision.sh start).
# The site address is derived from the VM's external IP; secrets are read by
# the leaderboard process from Secret Manager, nothing secret is passed here.
set -euo pipefail
cd "$(dirname "$0")/../.."

command -v docker >/dev/null || { echo "Docker not installed yet; wait for the startup script"; exit 1; }
ip=$(curl -fs -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)
export SITE_ADDRESS="$ip.sslip.io"
sudo --preserve-env=SITE_ADDRESS docker compose -f deploy/gcp/docker-compose.yml up -d --build --wait
echo "Leaderboard: https://$SITE_ADDRESS/  (the certificate may take a minute on the first start)"
