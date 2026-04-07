# shellcheck shell=bash
. /opt/bootstrap/sanitize-env.sh

# Auto-attach / create tmux session for interactive SSH logins.
if [[ -n "${SSH_CONNECTION:-}" && -z "${TMUX:-}" ]]; then
  if [[ "${AUTO_ATTACH_TMUX:-true}" == "true" ]]; then
    SESSION="${TMUX_SESSION_NAME:-codex}"
    if [[ "${CODEX_AUTO_START:-true}" == "true" ]]; then
      exec tmux new-session -A -s "$SESSION" "/opt/bootstrap/start_codex.sh"
    else
      exec tmux new-session -A -s "$SESSION"
    fi
  fi
fi
