# Leaderboard on a Google Cloud VM

Decided 2026-10-28: the leaderboard runs on a small Google Cloud VM instead of
the instructor laptop, so the workshop does not depend on the local network.
Participants use `LEADERBOARD_URL=https://<static-ip>.sslip.io`.

```
participants ──HTTPS──► Caddy (Let's Encrypt, <ip>.sslip.io) ──► leaderboard ──► OpenSearch
                                                                     │
                                         Secret Manager ◄────────────┘ key + token, read at every start
```

Files (instructor only, not shipped):
- `provision.sh` – one subcommand per step, run from the repo root on the
  instructor machine (needs the gcloud CLI).
- `vm-startup.sh` – VM startup script: Docker Engine + Compose plugin,
  `vm.max_map_count` for OpenSearch.
- `start.sh` – on the VM: build and start the stack for `<external-ip>.sslip.io`.
- `docker-compose.yml` – OpenSearch, indexer, leaderboard (no public port),
  Caddy (ports 80/443).
- `../leaderboard.Dockerfile` – the same image as on the laptop.

## Setup

Requirements: gcloud CLI logged in (`gcloud auth login`), a project with
billing, and permissions for Compute Engine, Secret Manager, service accounts
and IAM bindings (e.g. project Owner).

```bash
export GCP_PROJECT=<project id>
export GCP_ZONE=europe-west3-a        # optional, default Frankfurt
deploy/gcp/provision.sh apis          # enable Compute Engine and Secret Manager
deploy/gcp/provision.sh secrets       # type in the server's gateway key and the workshop token
deploy/gcp/provision.sh iam           # service account tjf-leaderboard, may read exactly these 2 secrets
deploy/gcp/provision.sh network       # static IP + firewall rule tcp:80,443; prints the URL
deploy/gcp/provision.sh vm            # e2-medium, Debian 12, 30 GB; Docker installed at boot
deploy/gcp/provision.sh status        # wait until Docker is ready (1-2 min)
deploy/gcp/provision.sh upload        # git archive HEAD (incl. heldout/) -> ~/tjf-evolve on the VM
deploy/gcp/provision.sh start         # build image, start stack (first start: ~5 min incl. pulls)
```

Then open `https://<ip>.sslip.io/`: the baseline appears and is scored within
about a minute. Test a submission from a participant machine with
`LEADERBOARD_URL=https://<ip>.sslip.io` and `evolve-eval submit … --wait`.

## Secrets

- `tjf-btelligent-api-key` – the server's own gateway key (scoring costs
  about 60 LLM calls per submission).
- `tjf-leaderboard-token` – the shared workshop token.

`provision.sh secrets` reads both silently and pipes them to Secret Manager;
they are never written to a file. On the VM, the leaderboard process fetches
them at every start through the metadata server with the VM's service account
(`SECRETS_FROM_GCP`, `src/evolve_demo/gcp_secrets.py`). They are not in the
compose file, not in Docker's container configuration and not on the VM disk.
To change the token: run `provision.sh secrets` again (empty input keeps a
value), then restart the leaderboard (`provision.sh start`).

## Operation

| Task | Command |
|---|---|
| Deploy a new commit | `provision.sh upload && provision.sh start` (submissions are kept) |
| Follow the log | `provision.sh logs` |
| Containers and URL | `provision.sh status` |
| Pause between workshops | `provision.sh stop` (no compute cost; disk and static IP still billed), later `resume` |
| Back up submissions | `gcloud compute ssh tjf-leaderboard --zone $GCP_ZONE --command "sudo docker cp tjf-leaderboard-1:/data/leaderboard.sqlite3 -" > leaderboard-backup.sqlite3` |
| Remove everything | `provision.sh teardown` (asks first; deletes all submissions) |

`upload` deploys the committed state only (`git archive HEAD`) and warns about
uncommitted changes.

## Costs (approximate)

e2-medium in Frankfurt about 1 USD per day while running, 30 GB disk and the
static IP a few USD per month, Secret Manager cents. Stop the VM between
workshops, tear it down when no longer needed.

## Security notes

- HTTPS with a Let's Encrypt certificate for `<ip>.sslip.io` (sslip.io only
  maps the name to the IP; traffic does not pass through it).
- Only ports 80 (redirect to HTTPS, certificate challenge) and 443 are open;
  SSH via `gcloud compute ssh`. OpenSearch is bound to localhost on the VM.
- Shared token, no individual accounts: anyone with the token can submit
  under any name.
- The VM holds the instructor repo including `heldout/`; the API returns
  scores only.

## Status

Written and syntax-checked; the secret loader is unit-tested against a fake
metadata server and Secret Manager. **Not run against Google Cloud yet.**
