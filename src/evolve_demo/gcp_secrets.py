"""Load secrets from Google Secret Manager into this process's environment.

Used by the leaderboard on the Google Cloud VM, so the gateway key and the
workshop token never appear in files or in Docker's container configuration:
they are fetched at every start with the VM's service account and live only
in the process memory.

  SECRETS_FROM_GCP="BTELLIGENT_API_KEY=tjf-btelligent-api-key,LEADERBOARD_TOKEN=tjf-leaderboard-token"

Each VAR=SECRET pair sets os.environ[VAR] to the latest version of SECRET in
the VM's project (or GCP_PROJECT, if set). Only works on Google Cloud: the
access token and project come from the metadata server.
"""
import base64
import os

import requests

METADATA = os.environ.get("GCE_METADATA_URL", "http://metadata.google.internal/computeMetadata/v1")
SECRET_MANAGER = os.environ.get("SECRET_MANAGER_URL", "https://secretmanager.googleapis.com/v1")


class SecretError(Exception):
    pass


def _metadata(path):
    r = requests.get(f"{METADATA}/{path}", headers={"Metadata-Flavor": "Google"}, timeout=5)
    r.raise_for_status()
    return r


def parse_mapping(spec):
    pairs = {}
    for item in filter(None, (p.strip() for p in spec.split(","))):
        var, sep, secret = item.partition("=")
        if not sep or not var.strip() or not secret.strip():
            raise SecretError(f"bad SECRETS_FROM_GCP entry '{item}' (expected VAR=SECRET)")
        pairs[var.strip()] = secret.strip()
    return pairs


def load(spec=None):
    """Fetch the secrets named in spec (default: $SECRETS_FROM_GCP) into os.environ.
    Returns the names of the variables set (never their values)."""
    spec = os.environ.get("SECRETS_FROM_GCP", "") if spec is None else spec
    pairs = parse_mapping(spec)
    if not pairs:
        return []
    try:
        project = os.environ.get("GCP_PROJECT") or _metadata("project/project-id").text
        token = _metadata("instance/service-accounts/default/token").json()["access_token"]
    except (requests.RequestException, ValueError, KeyError) as e:
        raise SecretError(f"Google Cloud metadata server not reachable ({type(e).__name__}); not on a GCP VM?")
    for var, secret in pairs.items():
        url = f"{SECRET_MANAGER}/projects/{project}/secrets/{secret}/versions/latest:access"
        try:
            r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        except requests.RequestException as e:
            raise SecretError(f"Secret Manager not reachable: {type(e).__name__}")
        if r.status_code != 200:
            raise SecretError(f"cannot read secret '{secret}' (HTTP {r.status_code}); "
                              "does it exist and may the VM's service account access it?")
        os.environ[var] = base64.b64decode(r.json()["payload"]["data"]).decode("utf-8").strip()
    return list(pairs)
