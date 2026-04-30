#!/usr/bin/env bash
set -euo pipefail
rm -f results/*.csv results/*.json figures/*.png docs/experimental_report.md
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
find . -name "*.pyc" -delete
