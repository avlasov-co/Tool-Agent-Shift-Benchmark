#!/usr/bin/env bash
set -euo pipefail
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m compileall -q src tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
python -m tool_agent_shift_benchmark.core.config_schema small
run_name="${1:-repro-$(date -u +%Y%m%d-%H%M%S)}"
python -m tool_agent_shift_benchmark run --all-envs --all-agents --config small --seed 42 --run-name "$run_name"
run_dir="runs/$run_name"
python -m tool_agent_shift_benchmark analyze --run "$run_dir"
python -m tool_agent_shift_benchmark pairwise --config compound_matrix --run "$run_dir"
python -m tool_agent_shift_benchmark plot --run "$run_dir"
python -m tool_agent_shift_benchmark report --run "$run_dir" --html
echo "reproducibility run complete"
