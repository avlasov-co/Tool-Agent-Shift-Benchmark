#!/usr/bin/env bash
set -euo pipefail
rm -rf results/*.csv results/*.json results/*.jsonl results/analysis docs/experimental_report.md docs/analysis_report.md docs/analysis_report.html figures/*.png .pytest_cache
find . -type d -name __pycache__ -prune -exec rm -rf {} +
mkdir -p results figures
: > results/.gitkeep
: > figures/.gitkeep
