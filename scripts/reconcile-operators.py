#!/usr/bin/env python3
import json
import os
import pwd
import grp
import subprocess
from pathlib import Path

CONFIG = Path("/srv/myos-config/operators.json")
DESIRED = []
NEVER_TOUCH = {"root", "ubuntu", "myos-runtime"}

def run(cmd):
    subprocess.run(cmd, check=True)

def user_exists(name):
    try:
        pwd.getpwnam(name)
        return True
    except KeyError:
        return False

def ensure_group(group):
    try:
        grp.getgrnam(group)
    except KeyError:
        run(["groupadd", group])

def ensure_user(user):
    username = user["username"]
    if username in NEVER_TOUCH:
        return
    if not user_exists(username):
        run(["useradd", "-m", "-s", "/bin/bash", username])
    home = Path("/home") / username
    ssh_dir = home / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    auth = ssh_dir / "authorized_keys"
    auth.write_text("\n".join(user.get("ssh_public_keys", [])) + "\n")
    uid = pwd.getpwnam(username).pw_uid
    gid = pwd.getpwnam(username).pw_gid
    os.chown(ssh_dir, uid, gid)
    os.chown(auth, uid, gid)
    ssh_dir.chmod(0o700)
    auth.chmod(0o600)
    for group in user.get("groups", []):
        ensure_group(group)
        run(["usermod", "-aG", group, username])
    run(["usermod", "-aG", "myos-operators", username])

def disable_user(username):
    if username in NEVER_TOUCH or not user_exists(username):
        return
    run(["usermod", "--lock", username])
    # keep home directory and data; just disable login

if CONFIG.exists():
    data = json.loads(CONFIG.read_text())
    desired = {u["username"]: u for u in data.get("operators", [])}
    existing = [u.pw_name for u in pwd.getpwall() if u.pw_uid >= 1000]
    for username, user in desired.items():
        if user.get("state", "present") == "present":
            ensure_user(user)
        else:
            disable_user(username)
    for username in existing:
        if username in NEVER_TOUCH:
            continue
        if username.startswith("systemd-"):
            continue
        if username not in desired:
            disable_user(username)
print("operator reconcile complete")
