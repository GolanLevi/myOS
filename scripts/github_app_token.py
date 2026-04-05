#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

# Minimal helper that reads GitHub App data from runtime secret files and asks GitHub for an installation token.
# Requires: python3, requests, pyjwt, cryptography (install if you use this helper).
# This script is intentionally conservative: if dependencies are missing, it exits with a clear error.

try:
    import jwt  # PyJWT
    import requests
except Exception as e:
    print(f"Missing python dependency: {e}", file=sys.stderr)
    sys.exit(2)

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import time

root = Path("/run/myos-secrets")
app_id = (root / "github_app_id").read_text().strip()
installation_id = (root / "github_app_installation_id").read_text().strip()
pem = (root / "github_app_private_key.pem").read_text()

private_key = serialization.load_pem_private_key(pem.encode(), password=None, backend=default_backend())
now = int(time.time())
payload = {"iat": now - 60, "exp": now + 540, "iss": app_id}
token = jwt.encode(payload, private_key, algorithm="RS256")

resp = requests.post(
    f"https://api.github.com/app/installations/{installation_id}/access_tokens",
    headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    },
    timeout=30
)
resp.raise_for_status()
print(resp.json()["token"])
