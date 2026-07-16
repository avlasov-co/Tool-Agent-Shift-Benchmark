#!/usr/bin/env bash
set -euo pipefail

# The Python driver copies the checkout before it builds, tests, or generates
# evidence. It never runs a cleanup command against this working tree.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" && -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
fi
PYTHON_BIN="${PYTHON_BIN:-python3}"
exec "$PYTHON_BIN" -m tool_agent_shift_benchmark.release_verification --source-root "$ROOT" "$@"
