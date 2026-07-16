# Analysis Layer

The analysis layer is a post-hoc research artifact generator. It reads benchmark outputs that already exist under `results/` and writes deeper analysis artifacts under `results/analysis/` plus `docs/analysis_report.md`.

It does not modify agent inputs, monitor inputs, hidden ground truth, evaluator scoring, fault injection, or environment execution. This keeps the evaluator boundary intact while making the generated benchmark evidence easier to inspect.

## Command

```bash
python -m tool_agent_shift_benchmark.analysis.run_analysis
```

Optional paths:

```bash
python -m tool_agent_shift_benchmark.analysis.run_analysis --results-dir results --analysis-dir results/analysis
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

The legacy compound-shift matrix can compare historical fixed `compound_shift`
rows against clean and worst single-fault rows when those rows are available in
`results/summary.csv`. New experiments represent compounds as explicit ordered
`shift_chains` and record their full composition histories.

This is post-hoc comparison, not a new pairwise fault injector. For explicit pairwise fault generation, use the pairwise compound experiment below.


## Pairwise compound experiment

The analysis runner above accepts legacy fixed `compound_shift` rows when they
are already present in `results/summary.csv`. For an explicit pairwise ordered-chain experiment, run:

```bash
python -m tool_agent_shift_benchmark.analysis.run_pairwise_compounds --config compound_matrix
```

This command generates clean, single-fault, and paired-fault episodes under the same visible-only policy boundary used by the main benchmark. It reports pair-vs-clean and pair-vs-worst-single deltas for unsafe rate, coverage, safe-useful action rate, recovery, monitor recall, and monitor false-positive rate.

The default config covers six fault pairs across FileOps, CalendarOps, and RiskOps. It remains synthetic and does not call external APIs.

Outputs:

- `results/analysis/pairwise_compound_matrix.csv`
- `results/analysis/pairwise_compound_manifest.json`

## Release verification

Use the release verifier before packaging:

```bash
bash scripts/verify_release.sh
```

It runs compile checks, the full test suite, a smoke benchmark, plots, reports, post-hoc analysis, pairwise compound analysis, and artifact existence checks. This is stricter than the fast repro script because releases should not be held together by optimism and string.


## v0.3.0 additions

The analysis layer now integrates with the `tasb` CLI, named run directories, HTML reports, enhanced failure replay, config validation, and additional analysis plots.
