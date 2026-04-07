#!/usr/bin/env bash

# Keep runtime auth limited to what is injected explicitly for this dev box.
unset GIT_ASKPASS
unset SSH_ASKPASS
unset SSH_AUTH_SOCK
unset SSH_AGENT_PID
unset GH_TOKEN
unset GITHUB_TOKEN
unset GITHUB_PAT
unset GIT_HTTPS_USERNAME
unset GIT_HTTPS_PASSWORD
unset GCM_INTERACTIVE

export GIT_TERMINAL_PROMPT=0
