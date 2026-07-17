# Analysis layer

The analysis command operates on one explicit complete-valid run bundle:

```bash
tasb analyze --run runs/<name>
```

It captures the verified pre-analysis manifest before writing bundle-local
artifacts. Loose root outputs may be used only by unit-test diagnostic helpers
and are labeled unverified.

## Inputs

- `results/episodes.jsonl`, `results/metric_evidence.csv`, and typed outcomes;
- `results/failure_cases.csv` and action records;
- `results/monitor_events.csv` with proposed-action counterfactual truth;
- `results/summary.csv`, `results/clean_vs_shifted.csv`, and scenario pairs.

## Outputs

- `analysis/failure_clusters.csv` with content-hash IDs;
- `analysis/monitor_threshold_sweep.csv` for detector quality;
- `analysis/monitor_gating_outcomes.csv` for executed oversight;
- `analysis/monitor_calibration.csv` and calibration eligibility/summary;
- `analysis/monitor_utility_frontier.csv` plus exact utility config;
- `analysis/agent_safety_profile.csv` containing raw components, not a ranking;
- `analysis/compound_shift_matrix.csv` and `analysis/analysis_manifest.json`;
- `reports/analysis_report.md` and its verified source snapshot.

Threshold sweeps are not described as executed gating treatments. Calibration
is emitted only for `probability-score-v1`. Failure clustering, metric tables,
and reports do not call external models.

Pairwise compound experiments remain available through `tasb pairwise`; their
bar plots are called compound-effect plots, not heatmaps.
