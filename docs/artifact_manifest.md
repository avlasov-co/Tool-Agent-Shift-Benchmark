# Artifact Manifest

This file records the expected artifact contract for the smoke reproducibility path. It is intentionally boring. Boring reproducibility beats decorative research cosplay.

## Smoke command

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m compileall -q src tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
python -m tool_agent_shift_benchmark.run_eval --all-envs --all-agents --config configs/small.yaml --seed 42
python -m tool_agent_shift_benchmark.plot_results
python -m tool_agent_shift_benchmark.generate_report
python -m tool_agent_shift_benchmark.analysis.run_analysis
```

CI runs this same smoke contract via `scripts/run_repro.sh`.

## Expected smoke outputs

For `configs/small.yaml` with `--all-envs --all-agents`:

- environments: 3
- agents: 6
- fault groups: `normal` at severity `1.0`, plus 3 shifted faults at severities `0.5` and `1.0`
- groups: `3 * 6 * 7 = 126`
- episodes per group: 2
- expected episodes: 252

Expected files after the smoke run:

- `results/episode_log.csv`: 252 data rows
- `results/summary.csv`: 126 data rows
- `results/failure_cases.csv`: zero or more unsafe-case rows
- `results/monitor_events.csv`: one or more monitor rows per episode
- `results/static_vs_dynamic.csv`: one row per evaluated agent
- `results/config.json`: includes both raw config and effective env/agent/fault selections
- `results/multistep_traces.jsonl`: one line per episode
- `figures/unsafe_action_rate.png`
- `figures/coverage_vs_safety.png`
- `figures/monitor_recall_precision.png`
- `figures/recovery_rate.png`
- `figures/failure_breakdown.png`
- `figures/unsafe_step_rate.png`
- `figures/static_vs_dynamic_gap.png`
- `docs/experimental_report.md`

`results/seed_summary.csv`, `results/confidence_intervals.csv`, and `figures/confidence_intervals.png` are generated only by the multi-seed path. They should not silently survive as stale artifacts after a single-seed run.

## Multi-seed command

```bash
python -m tool_agent_shift_benchmark.run_seeds --config configs/seeds.yaml --all-envs --all-agents
python -m tool_agent_shift_benchmark.plot_results
python -m tool_agent_shift_benchmark.generate_report
python -m tool_agent_shift_benchmark.analysis.run_analysis
```

The multi-seed output is the only valid source for confidence intervals.

## Included artifact state after final validation

The checked-in generated artifacts are from the extended multi-seed validation path:

```bash
python -m tool_agent_shift_benchmark.run_seeds --config configs/seeds.yaml --all-envs --all-agents
python -m tool_agent_shift_benchmark.plot_results
python -m tool_agent_shift_benchmark.generate_report
python -m tool_agent_shift_benchmark.analysis.run_analysis
```

Expected current generated outputs for that path:

- `results/episode_log.csv`: 324 data rows from the latest seed run
- `results/summary.csv`: 162 data rows from the latest seed run
- `results/failure_cases.csv`: zero or more unsafe-case rows from the latest seed run
- `results/monitor_events.csv`: one or more monitor rows per episode from the latest seed run
- `results/static_vs_dynamic.csv`: 6 data rows, one per evaluated agent
- `results/multistep_traces.jsonl`: 324 lines from the latest seed run
- `results/seed_summary.csv`: 486 data rows across 3 seeds
- `results/confidence_intervals.csv`: 270 data rows
- `figures/confidence_intervals.png`: present only because the multi-seed path was run

The smoke command remains the fastest reviewer path. The multi-seed artifacts are checked in as example evidence, not as production-safety proof.


## Pairwise compound matrix

Run explicit fault-pair analysis with:

```bash
python -m tool_agent_shift_benchmark.analysis.run_pairwise_compounds --config configs/compound_matrix.yaml
```

Expected outputs:

- `results/analysis/pairwise_compound_matrix.csv`
- `results/analysis/pairwise_compound_manifest.json`

## Release verification

Before packaging a release archive, run:

```bash
bash scripts/verify_release.sh
```

This checks compile, tests, smoke benchmark outputs, generated reports, post-hoc analysis outputs, and pairwise compound outputs.


## v0.3.0 expected additional artifacts

- `docs/analysis_report.html`
- `figures/monitor_threshold_curve.png`
- `figures/calibration_curve.png`
- `figures/agent_safety_profile.png`
- `figures/pairwise_compound_heatmap.png`
- `figures/failure_cluster_topn.png`
- optional `runs/<run-name>/run_manifest.json` when using the CLI run directory workflow.
# Run bundle format

Completed runs are self-contained under `runs/<name>/`: `run_manifest.json`, a copied `config.json`, legacy CSV exports, structured `results/episodes.jsonl`, policy/evaluator traces, figures, reports, and replay data. The manifest records schema and contract versions, config digest, plugin catalog, episode count, checkpoint information, and SHA-256 checksums for every generated file.
