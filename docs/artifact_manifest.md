# Artifact Manifest

This file records the expected artifact contract for the smoke reproducibility path. It is intentionally boring. Boring reproducibility beats decorative research cosplay.

## Smoke command

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m compileall -q src tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
python -m src.run_eval --all-envs --all-agents --config configs/small.yaml --seed 42
python -m src.plot_results
python -m src.generate_report
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
python -m src.run_seeds --config configs/seeds.yaml --all-envs --all-agents
python -m src.plot_results
python -m src.generate_report
```

The multi-seed output is the only valid source for confidence intervals.

## Included artifact state after final validation

The checked-in generated artifacts are from the extended multi-seed validation path:

```bash
python -m src.run_seeds --config configs/seeds.yaml --all-envs --all-agents
python -m src.plot_results
python -m src.generate_report
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
