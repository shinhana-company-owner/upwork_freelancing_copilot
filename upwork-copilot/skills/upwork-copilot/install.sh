#!/usr/bin/env bash
# One-time setup for the Upwork Copilot skill.
#
# Creates a self-contained virtualenv INSIDE this skill folder and installs the
# bundled data CLI (only the `mcp` client — no LLM libraries). After this, the
# skill runs entirely from `.venv/bin/python` with no dependency on the parent
# repo. Safe to re-run.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"

# Prefer `uv` if present (fast); fall back to stdlib venv + pip.
if command -v uv >/dev/null 2>&1; then
  echo "Installing with uv…"
  uv venv "$VENV"
  uv pip install --python "$VENV/bin/python" -e "$DIR"
else
  PY="${PYTHON:-python3}"
  echo "Installing with $PY venv + pip…"
  "$PY" -m venv "$VENV"
  "$VENV/bin/python" -m pip install --upgrade pip >/dev/null
  "$VENV/bin/python" -m pip install -e "$DIR"
fi

echo
echo "✓ Installed. Next, log in to your Upwork account (opens a browser):"
echo "    \"$VENV/bin/python\" -m upwork_agent.skill_cli login"
echo
echo "Then this skill's commands are ready. Point the skill at this folder with:"
echo "    export SKILL_DIR=\"$DIR\""
