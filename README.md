# Tool-Agent Shift Benchmark

[![CI](https://github.com/avlasov-co/tool-agent-shift-benchmark/actions/workflows/ci.yml/badge.svg)](https://github.com/avlasov-co/tool-agent-shift-benchmark/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A deterministic synthetic benchmark for tool-using agent behavior under schema
drift, stale observations, conflicting outputs, memory faults, latency, and
constraint shift.

The benchmark separates visible policy context from evaluator-only state. It
records proposed actions, monitor decisions, interventions, executed actions,
counterfactual proposed-action risk, and realized outcomes without exposing
hidden labels to agents or monitors.

## Evidence status

This branch prepares v0.4.0 evidence contracts. Checked-in root `results/`,
`figures/`, and generated reports are historical examples, not current headline
evidence. Current claims must come from a named `runs/<name>/` bundle whose
`tasb verify-run --strict` status is `complete_valid`.

The versioned [golden suites](docs/golden-suites.md), [benchmark
card](docs/benchmark-card.md), and [v0.4.0 migration
guide](docs/migrations/v0.4.0.md) define the release matrix, evidence scope,
and compatibility boundary.

The project does not claim production safety, frontier-model capability, or
real-world effectiveness. Synthetic reference-policy results support only the
declared suite and metric definitions.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
make setup

tasb validate-config small
tasb run --config small --seed 42 --run-name smoke
tasb analyze --run runs/smoke
tasb plot --run runs/smoke
tasb report --run runs/smoke --html
tasb verify-run --strict runs/smoke
```

`tasb analyze`, `tasb plot`, and `tasb report` consume an explicit run bundle.
Evidence-bearing plots and reports embed a snapshot of the complete-valid source
manifest. Existing run names are never overwritten.

## Metrics and uncertainty

Normative definitions are in
[`docs/metrics/metric-data-dictionary.md`](docs/metrics/metric-data-dictionary.md).
Every v2 rate record includes its numerator, denominator, unit, formula,
inclusion rule, and missing-data rule.

Key distinctions include:

- safe success versus safe non-success;
- unsafe proposed action versus unsafe executed action;
- constraint violation versus generic unsafe outcome;
- agent abstention versus oversight intervention;
- temporal recovery versus schema recovery;
- monitor detector quality versus realized gating safety.

Statistical intervals use unique scenario manifests as independent clusters.
Clean/shift effects are matched within scenarios before deterministic bootstrap
resampling. Insufficient cells have no numeric interval. Built-in monitor scores
are ordinal and do not produce reliability diagrams; calibration requires the
explicit `probability-score-v1` contract.

## Run-bundle outputs

Important bundle-local artifacts include:

- `results/metric_evidence.csv` — long-form metric-schema-v2 evidence;
- `results/episode_outcomes.csv` and `results/step_outcomes.csv` — typed outcomes;
- `results/action_records.jsonl` — lossless proposal-through-execution records;
- `results/monitor_events.csv` — counterfactual monitor evaluation inputs;
- `results/clean_vs_shifted.csv` — correctly named treatment comparison;
- `analysis/monitor_threshold_sweep.csv` — detector confusion/interval rows;
- `analysis/monitor_gating_outcomes.csv` — actual intervention/execution rows;
- `analysis/monitor_calibration_summary.csv` — calibration eligibility, Brier, and ECE;
- `results/confidence_intervals.csv` and `results/paired_effect_intervals.csv` — scenario-clustered inference;
- `reports/source_evidence_snapshot.json` and `reports/report_provenance.json` — report evidence links;
- `run_manifest.json` and `finalization.json` — schema inventory and checksums.

## Failure inspection

```bash
tasb replay CASE_ID --run runs/smoke --format markdown
```

Failure replay shows the visible observation, proposed action, monitor decision,
intervention, executed action, evaluator-only check, and reason codes.

## Architecture and boundaries

The maintained architecture is in
[`docs/architecture.mmd`](docs/architecture.mmd), with checked-in
[`SVG`](docs/architecture.svg) and [`PNG`](docs/architecture.png) renders.
Agents and monitors receive only `ObservationContext` and policy-visible tool
responses. They cannot access hidden ground truth, clean unfaulted responses,
post-hoc metrics, or shift provenance.

The benchmark is non-operational: it uses no real filesystem, calendar, market,
or user data and requires no network credentials.

## Development checks

```bash
make lint
make format-check
make typecheck
make test
make coverage
make audit
```

See [`docs/index.md`](docs/index.md), [`docs/paper.md`](docs/paper.md),
[`docs/eval_card.md`](docs/eval_card.md), and
[`docs/development/phase-6-progress.md`](docs/development/phase-6-progress.md).

## License

MIT. See [`LICENSE`](LICENSE).
