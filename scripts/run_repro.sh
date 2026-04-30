#!/usr/bin/env bash
set -euo pipefail
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m compileall -q src tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
python -m src.run_eval --all-envs --all-agents --config configs/small.yaml --seed 42
python -m src.plot_results
python -m src.generate_report
echo "reproducibility run complete"
