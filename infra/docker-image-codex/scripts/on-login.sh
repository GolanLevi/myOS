# shellcheck shell=bash
# Auto-attach / create tmux session for interactive SSH logins.
if [[ -n "${SSH_CONNECTION:-}" && -z "${TMUX:-}" ]]; then
  if [[ "${AUTO_ATTACH_TMUX:-true}" == "true" ]]; then
    SESSION="${TMUX_SESSION_NAME:-codex}"
    WORKDIR="${WORKSPACE_DIR:-/workspace}"
    if [[ "${CODEX_AUTO_START:-true}" == "true" ]]; then
      exec tmux new-session -A -s "$SESSION" "cd '$WORKDIR' && codex"
    else
      exec tmux new-session -A -s "$SESSION"
    fi
  fi
fi
