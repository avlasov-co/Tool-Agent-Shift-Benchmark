#!/usr/bin/env bash
set -euo pipefail
bash scripts/clean_outputs.sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m compileall -q src tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
python -m tool_agent_shift_benchmark.core.config_schema configs/small.yaml
python -m tool_agent_shift_benchmark.run_eval --all-envs --all-agents --config configs/small.yaml --seed 42
python -m tool_agent_shift_benchmark.analysis.run_analysis
python -m tool_agent_shift_benchmark.analysis.run_pairwise_compounds --config configs/compound_matrix.yaml
python -m tool_agent_shift_benchmark.plot_results
python -m tool_agent_shift_benchmark.generate_report
python -m tool_agent_shift_benchmark.reporting.html_report --results-dir results --output docs/analysis_report.html
echo "reproducibility run complete"
