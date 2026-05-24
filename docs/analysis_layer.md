# Analysis Layer

The analysis layer is a post-hoc research artifact generator. It reads benchmark outputs that already exist under `results/` and writes deeper analysis artifacts under `results/analysis/` plus `docs/analysis_report.md`.

It does not modify agent inputs, monitor inputs, hidden ground truth, evaluator scoring, fault injection, or environment execution. This keeps the evaluator boundary intact while making the generated benchmark evidence easier to inspect.

## Command

```bash
python -m src.analysis.run_analysis
```

Optional paths:

```bash
python -m src.analysis.run_analysis --results-dir results --analysis-dir results/analysis
```

## Inputs

The command consumes whichever of these files are present:

- `results/episode_log.csv`
- `results/failure_cases.csv`
- `results/monitor_events.csv`
- `results/summary.csv`
- `results/static_vs_dynamic.csv`

Missing optional files produce empty or partial analysis outputs instead of crashing.

## Outputs

- `results/analysis/failure_clusters.csv`
- `results/analysis/failure_cluster_examples.jsonl`
- `results/analysis/monitor_threshold_sweep.csv`
- `results/analysis/monitor_calibration.csv`
- `results/analysis/compound_shift_matrix.csv`
- `results/analysis/agent_safety_profile.csv`
- `results/analysis/analysis_manifest.json`
- `docs/analysis_report.md`

## Failure clustering

Unsafe cases are grouped by environment, fault, severity bucket, agent, action type, unsafe reason family, monitor blocking state, failure step, and stop reason.

Each cluster includes deterministic IDs, representative case IDs, representative episode IDs, and a template-based interpretation. No LLM calls are used.

## Monitor threshold sweep

Monitor events are joined with episode outcomes by `episode_id`. The analysis sweeps risk thresholds from `0.00` to `1.00` in `0.05` steps and reports true-positive blocks, false-positive blocks, false-negative allows, true-negative allows, precision, recall, false-positive rate, false-negative rate, coverage after gate, and unsafe rate after gate.

## Monitor calibration

Risk scores are bucketed into deciles. Each bucket reports mean risk score, empirical unsafe rate, and absolute calibration error.

## Agent safety profile

The agent profile aggregates episode-level behavior into a compact table with unsafe rate, coverage, abstention, success, safe-useful action rate, recovery, monitor blocked rate, mean latency, static-vs-dynamic gap, and a conservative safety/coverage score.

The score is only a sorting helper. The component metrics remain the evidence.

## Compound-shift comparison

The compound-shift matrix compares the existing fixed `compound_shift` fault against clean and worst single-fault rows when those rows are available in `results/summary.csv`.

This is post-hoc comparison, not a new pairwise fault injector. Pairwise compound-fault generation remains future work.
