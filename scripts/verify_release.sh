#!/usr/bin/env bash
set -euo pipefail

# Release verification is intentionally diagnostic-only. It never cleans,
# regenerates, or overwrites benchmark evidence in the working tree.
PYTHON_BIN="${PYTHON:-python3}"
AUDIT_DIR="${TASB_RELEASE_AUDIT_DIR:-$(mktemp -d -t tasb-release-audit)}"
export PYTHONPYCACHEPREFIX="$AUDIT_DIR/pycache"
export COVERAGE_FILE="$AUDIT_DIR/.coverage"

"$PYTHON_BIN" -m compileall -q src tests
"$PYTHON_BIN" -m pytest -q -p no:cacheprovider
"$PYTHON_BIN" -m ruff check --no-cache src tests
"$PYTHON_BIN" -m ruff format --check --no-cache src tests
"$PYTHON_BIN" -m mypy --cache-dir "$AUDIT_DIR/mypy-cache"
"$PYTHON_BIN" -m coverage run -m pytest -q -p no:cacheprovider
"$PYTHON_BIN" -m coverage report
"$PYTHON_BIN" -m src.audit --strict --output-dir "$AUDIT_DIR" --python "$PYTHON_BIN"

echo "non-destructive release verification complete; audit report: $AUDIT_DIR/report.json"
