#!/usr/bin/env bash
# Provision and operate the leaderboard VM on Google Cloud. Run from the repo
# root, one step at a time:
#
#   export GCP_PROJECT=my-project            # required
#   export GCP_ZONE=europe-west3-a           # optional (default: Frankfurt)
#   deploy/gcp/provision.sh apis             # enable Compute Engine + Secret Manager
#   deploy/gcp/provision.sh secrets          # store gateway key + workshop token (typed in, never on disk)
#   deploy/gcp/provision.sh iam              # service account that may read exactly these two secrets
#   deploy/gcp/provision.sh network          # static IP + firewall rule for ports 80/443
#   deploy/gcp/provision.sh vm               # create the VM (Debian 12, Docker via startup script)
#   deploy/gcp/provision.sh upload           # copy the committed repo state (incl. heldout/) to the VM
#   deploy/gcp/provision.sh start            # build and start the stack on the VM
#   deploy/gcp/provision.sh status           # containers + URL
#   deploy/gcp/provision.sh logs             # follow the leaderboard log
#   deploy/gcp/provision.sh stop | resume    # stop / start the VM (no compute cost while stopped)
#   deploy/gcp/provision.sh teardown         # delete VM, IP, firewall rule, service account, secrets
#
# Billable: the VM (e2-medium, ~1 USD/day while running), its disk and the
# static IP (also while the VM is stopped), Secret Manager (cents).
set -euo pipefail

PROJECT="${GCP_PROJECT:?export GCP_PROJECT=<project id>}"
ZONE="${GCP_ZONE:-europe-west3-a}"
REGION="${ZONE%-*}"
VM="${VM_NAME:-tjf-leaderboard}"
MACHINE="${VM_MACHINE:-e2-medium}"
SA_NAME="tjf-leaderboard"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
SECRETS=(tjf-btelligent-api-key tjf-leaderboard-token)
TAG="tjf-leaderboard"
REMOTE_DIR="tjf-evolve"
G=(gcloud --project "$PROJECT" --quiet)

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

put_secret() {   # name, prompt: value is read silently and piped to gcloud via stdin
    local name="$1" value
    read -rs -p "$2: " value; echo
    [ -n "$value" ] || { echo "empty, skipped $name"; return; }
    if ! "${G[@]}" secrets describe "$name" >/dev/null 2>&1; then
        "${G[@]}" secrets create "$name" --replication-policy=automatic
    fi
    printf '%s' "$value" | "${G[@]}" secrets versions add "$name" --data-file=-
    unset value
}

ip() { "${G[@]}" compute addresses describe "$VM-ip" --region "$REGION" --format='value(address)'; }

case "${1:-}" in
apis)
    "${G[@]}" services enable compute.googleapis.com secretmanager.googleapis.com ;;
secrets)
    put_secret tjf-btelligent-api-key "Gateway API key for the server (BTELLIGENT_API_KEY)"
    put_secret tjf-leaderboard-token "Workshop token handed out to participants" ;;
iam)
    "${G[@]}" iam service-accounts describe "$SA" >/dev/null 2>&1 \
        || "${G[@]}" iam service-accounts create "$SA_NAME" --display-name "tjf leaderboard VM"
    for s in "${SECRETS[@]}"; do
        "${G[@]}" secrets add-iam-policy-binding "$s" --member "serviceAccount:$SA" \
            --role roles/secretmanager.secretAccessor >/dev/null
    done
    echo "service account $SA may read: ${SECRETS[*]}" ;;
network)
    "${G[@]}" compute addresses describe "$VM-ip" --region "$REGION" >/dev/null 2>&1 \
        || "${G[@]}" compute addresses create "$VM-ip" --region "$REGION"
    "${G[@]}" compute firewall-rules describe "$TAG-web" >/dev/null 2>&1 \
        || "${G[@]}" compute firewall-rules create "$TAG-web" --allow tcp:80,tcp:443 \
               --target-tags "$TAG" --source-ranges 0.0.0.0/0 --description "tjf leaderboard HTTPS (Caddy)"
    echo "static IP: $(ip)  ->  https://$(ip).sslip.io/" ;;
vm)
    "${G[@]}" compute instances create "$VM" --zone "$ZONE" --machine-type "$MACHINE" \
        --image-family debian-12 --image-project debian-cloud --boot-disk-size 30GB \
        --address "$(ip)" --tags "$TAG" \
        --service-account "$SA" --scopes cloud-platform \
        --metadata-from-file startup-script="$here/vm-startup.sh"
    echo "The startup script installs Docker (1-2 minutes); check with: $0 status" ;;
upload)
    [ -z "$(git status --porcelain)" ] || echo "warning: uncommitted changes are NOT uploaded (git archive HEAD)"
    git archive --format=tar HEAD | "${G[@]}" compute ssh "$VM" --zone "$ZONE" \
        --command "rm -rf $REMOTE_DIR.new && mkdir $REMOTE_DIR.new && tar -x -C $REMOTE_DIR.new \
                   && rm -rf $REMOTE_DIR && mv $REMOTE_DIR.new $REMOTE_DIR && echo uploaded $(git rev-parse --short HEAD)" ;;
start)
    "${G[@]}" compute ssh "$VM" --zone "$ZONE" --command "bash $REMOTE_DIR/deploy/gcp/start.sh" ;;
status)
    "${G[@]}" compute ssh "$VM" --zone "$ZONE" --command \
        "sudo docker ps --format '{{.Names}}  {{.Status}}' 2>/dev/null || echo 'Docker not ready yet'"
    echo "URL: https://$(ip).sslip.io/" ;;
logs)
    "${G[@]}" compute ssh "$VM" --zone "$ZONE" --command "sudo docker logs -f --tail 50 tjf-leaderboard-1" ;;
stop)
    "${G[@]}" compute instances stop "$VM" --zone "$ZONE" ;;
resume)
    "${G[@]}" compute instances start "$VM" --zone "$ZONE"
    echo "containers restart automatically; check with: $0 status" ;;
teardown)
    read -r -p "Delete VM $VM (incl. all submissions), IP, firewall rule, service account and secrets? [yes/N] " ok
    [ "$ok" = yes ] || exit 1
    "${G[@]}" compute instances delete "$VM" --zone "$ZONE" || true
    "${G[@]}" compute addresses delete "$VM-ip" --region "$REGION" || true
    "${G[@]}" compute firewall-rules delete "$TAG-web" || true
    "${G[@]}" iam service-accounts delete "$SA" || true
    for s in "${SECRETS[@]}"; do "${G[@]}" secrets delete "$s" || true; done ;;
*)
    sed -n '2,24p' "$0"; exit 1 ;;
esac
