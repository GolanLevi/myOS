#!/usr/bin/env python3
import json
import os
import time
from pathlib import Path

import jwt
import requests

app_id = os.environ.get("GITHUB_APP_ID")
installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID")
key_path = os.environ.get("GH_APP_PRIVATE_KEY_PATH", "/run/secrets/github_app_private_key.pem")
api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")

if not app_id or not installation_id:
    raise SystemExit("Missing GITHUB_APP_ID or GITHUB_APP_INSTALLATION_ID")

private_key = Path(key_path).read_text(encoding="utf-8")
now = int(time.time())
payload = {"iat": now - 60, "exp": now + 540, "iss": app_id}
encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")
headers = {
    "Authorization": f"Bearer {encoded_jwt}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
resp = requests.post(
    f"{api_url}/app/installations/{installation_id}/access_tokens",
    headers=headers,
    timeout=30,
)
resp.raise_for_status()
print(resp.json()["token"])
