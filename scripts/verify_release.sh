#!/usr/bin/env bash
set -euo pipefail

bash scripts/clean_outputs.sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m compileall -q src tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
python -m src.core.config_schema configs/small.yaml
python -m src.core.config_schema configs/compound_matrix.yaml --pairwise
python -m src.run_eval --all-envs --all-agents --config configs/small.yaml --seed 42
python -m src.analysis.run_analysis
python -m src.analysis.run_pairwise_compounds --config configs/compound_matrix.yaml
python -m src.plot_results
python -m src.generate_report
python -m src.reporting.html_report --results-dir results --output docs/analysis_report.html

required_files=(
  results/episode_log.csv
  results/summary.csv
  results/failure_cases.csv
  results/monitor_events.csv
  results/static_vs_dynamic.csv
  results/config.json
  results/episodes.jsonl
  results/evaluator_traces.jsonl
  results/orchestration_errors.jsonl
  results/analysis/failure_clusters.csv
  results/analysis/failure_cluster_examples.jsonl
  results/analysis/monitor_threshold_sweep.csv
  results/analysis/monitor_calibration.csv
  results/analysis/compound_shift_matrix.csv
  results/analysis/agent_safety_profile.csv
  results/analysis/analysis_manifest.json
  results/analysis/pairwise_compound_matrix.csv
  results/analysis/pairwise_compound_manifest.json
  docs/experimental_report.md
  docs/analysis_report.md
  docs/analysis_report.html
  docs/cli.md
  docs/release_process.md
  docs/architecture.mmd
  docs/architecture.svg
  docs/architecture.png
  release-notes-v0.3.0.md
  figures/unsafe_action_rate.png
  figures/coverage_vs_safety.png
  figures/monitor_threshold_curve.png
  figures/calibration_curve.png
  figures/agent_safety_profile.png
  figures/pairwise_compound_heatmap.png
  figures/failure_cluster_topn.png
)

for file in "${required_files[@]}"; do
  if [[ ! -s "$file" ]]; then
    echo "missing or empty release artifact: $file" >&2
    exit 1
  fi
done

architecture_svg_before=$(sha256sum docs/architecture.svg | awk '{print $1}')
architecture_png_before=$(sha256sum docs/architecture.png | awk '{print $1}')
bash scripts/render_architecture.sh
architecture_svg_after=$(sha256sum docs/architecture.svg | awk '{print $1}')
architecture_png_after=$(sha256sum docs/architecture.png | awk '{print $1}')
if [[ "$architecture_svg_before" != "$architecture_svg_after" || "$architecture_png_before" != "$architecture_png_after" ]]; then
  echo "architecture renders differ from checked-in artifacts" >&2
  exit 1
fi

find . -type d -name __pycache__ -prune -exec rm -rf {} +
rm -rf .pytest_cache
python - <<'PYCHECK'
import csv, re, sys
from pathlib import Path
pyproject = Path('pyproject.toml').read_text(encoding='utf-8')
changelog = Path('CHANGELOG.md').read_text(encoding='utf-8')
version = re.search(r'version = "([^"]+)"', pyproject).group(1)
if f'v{version}' not in changelog:
    raise SystemExit(f'pyproject version {version} missing from changelog')
checks = {
    'results/episode_log.csv': 1,
    'results/summary.csv': 1,
    'results/analysis/monitor_threshold_sweep.csv': 21,
    'results/analysis/agent_safety_profile.csv': 1,
    'results/analysis/pairwise_compound_matrix.csv': 1,
}
for path, minimum in checks.items():
    with Path(path).open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    if len(rows) < minimum:
        raise SystemExit(f'{path} has {len(rows)} rows, expected at least {minimum}')
for forbidden in ['.pytest_cache', '__pycache__', '.venv']:
    hits = list(Path('.').rglob(forbidden))
    if hits:
        raise SystemExit(f'forbidden generated directory exists: {hits[0]}')
PYCHECK

echo "release verification complete"
