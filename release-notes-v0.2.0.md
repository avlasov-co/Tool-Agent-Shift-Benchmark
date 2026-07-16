# Tool-Agent Shift Benchmark v0.2.0

Release date: 2026-05-24

## Summary

This release upgrades the benchmark from basic result generation to a release-grade analysis workflow. It adds post-hoc failure clustering, monitor calibration, agent safety profiles, explicit pairwise compound-fault analysis, and a release verification script.

## New commands

```bash
python -m tool_agent_shift_benchmark.analysis.run_analysis
python -m tool_agent_shift_benchmark.analysis.run_pairwise_compounds --config configs/compound_matrix.yaml
bash scripts/verify_release.sh
```

## New generated artifacts

- `results/analysis/failure_clusters.csv`
- `results/analysis/failure_cluster_examples.jsonl`
- `results/analysis/monitor_threshold_sweep.csv`
- `results/analysis/monitor_calibration.csv`
- `results/analysis/compound_shift_matrix.csv`
- `results/analysis/agent_safety_profile.csv`
- `results/analysis/analysis_manifest.json`
- `results/analysis/pairwise_compound_matrix.csv`
- `results/analysis/pairwise_compound_manifest.json`
- `docs/analysis_report.md`

## Validation run

The release verifier completed successfully:

```bash
bash scripts/verify_release.sh
```

Observed validation output:

- test suite: 42 passed
- smoke benchmark episodes: 252
- summary rows: 126
- failure clusters: 43
- monitor threshold sweep rows: 1533
- agent safety profile rows: 6
- pairwise compound matrix rows: 216

## Safety boundary

All new analysis remains synthetic and post-hoc. It does not call external APIs, use credentials, modify real files, access real calendars, use market data, expose hidden ground truth to agents or monitors, or change evaluator scoring.
