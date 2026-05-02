#!/usr/bin/env bash
set -euo pipefail
rm -f results/*.csv results/*.json results/*.jsonl figures/*.png docs/experimental_report.md
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
find . -name "*.pyc" -delete
find . -name ".pytest_cache" -type d -prune -exec rm -rf {} +
find . -name ".mypy_cache" -type d -prune -exec rm -rf {} +
find . -name ".ruff_cache" -type d -prune -exec rm -rf {} +
