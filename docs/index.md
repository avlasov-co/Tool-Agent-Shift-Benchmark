# Reviewer Guide

## Platform architecture

See the [architecture diagram](architecture.svg) and [Mermaid source](architecture.mmd) for the separation between policy-visible observations, shift provenance, hidden ground truth, orchestration, and generated artifacts.

Start here if you are evaluating the repository.

## Read first

1. [`README.md`](../README.md) — short overview, quick start, headline results, safety boundary, and repository map.
2. [`docs/paper.md`](paper.md) — mini-paper with experimental matrix, results summary, ablations, static-vs-dynamic gap, and failure analysis.
3. [`docs/agent_monitor_boundaries.md`](agent_monitor_boundaries.md) — visible-only agent/monitor context and evaluator-state separation.
4. [`docs/eval_card.md`](eval_card.md) — what the benchmark measures, what it does not measure, intended use, and limitations.
5. [`docs/experimental_report.md`](experimental_report.md) — generated report from the included run.
6. [`docs/cli.md`](cli.md) — command-line workflow.
7. [`docs/release_process.md`](release_process.md) — release validation and archive checklist.
8. [`docs/analysis_layer.md`](analysis_layer.md) — post-hoc analysis, pairwise compound analysis, and release verification.
9. [`docs/development/phase-4b-handoff.md`](development/phase-4b-handoff.md) — Phase 4A contract, migration, evidence, limitations, and Phase 4B continuation map.

## Run first

```bash
bash scripts/run_repro.sh
```

## Inspect a failure

Find a `case_id` in `results/failure_cases.csv`, then run:

```bash
python -m tool_agent_shift_benchmark.reporting.failure_cases --case-id CASE_ID
```

The replay shows the environment, fault, agent decision, monitor decision, action taken, hidden ground-truth check, and unsafe reason codes.

## Key artifacts

- `results/summary.csv`
- `results/failure_cases.csv`
- `results/static_vs_dynamic.csv`
- `results/confidence_intervals.csv`
- `results/analysis/agent_safety_profile.csv`
- `results/analysis/failure_clusters.csv`
- `results/analysis/monitor_threshold_sweep.csv`
- `results/analysis/pairwise_compound_matrix.csv`
- `figures/coverage_vs_safety.png`
- `figures/unsafe_action_rate.png`
- `figures/confidence_intervals.png`
- `figures/static_vs_dynamic_gap.png`

## What to look for

- Whether unsafe action rates increase under shift.
- Whether monitor-gated and validation-heavy agents reduce unsafe behavior.
- Whether safety gains come with coverage or abstention costs.
- Whether compound faults expose failures that single faults do not.
- Whether failure cases are inspectable and reproducible.

## Safety boundary reminder

The benchmark is fully synthetic. It does not call real APIs, modify real files, access real calendars, use real market data, handle credentials, or execute operational abuse workflows.


## v0.3.0 workflow

Use the CLI for reviewer-friendly runs:

```bash
tasb validate-config small
tasb run --config small --all-envs --all-agents --seed 42 --run-name smoke --overwrite
tasb analyze --run runs/smoke
tasb pairwise --run runs/smoke
tasb plot --run runs/smoke
tasb report --run runs/smoke --html
```
