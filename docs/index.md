# Reviewer Guide

Start here if you are evaluating the repository.

## Read first

1. [`README.md`](../README.md) — short overview, quick start, headline results, safety boundary, and repository map.
2. [`docs/paper.md`](paper.md) — mini-paper with experimental matrix, results summary, ablations, static-vs-dynamic gap, and failure analysis.
3. [`docs/agent_monitor_boundaries.md`](agent_monitor_boundaries.md) — visible-only agent/monitor context and evaluator-state separation.
4. [`docs/eval_card.md`](eval_card.md) — what the benchmark measures, what it does not measure, intended use, and limitations.
5. [`docs/experimental_report.md`](experimental_report.md) — generated report from the included run.

## Run first

```bash
bash scripts/run_repro.sh
```

## Inspect a failure

Find a `case_id` in `results/failure_cases.csv`, then run:

```bash
python -m src.reporting.failure_cases --case-id CASE_ID
```

The replay shows the environment, fault, agent decision, monitor decision, action taken, hidden ground-truth check, and unsafe reason codes.

## Key artifacts

- `results/summary.csv`
- `results/failure_cases.csv`
- `results/static_vs_dynamic.csv`
- `results/confidence_intervals.csv`
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
