# Artifact manifest

The authoritative artifact inventory is generated per run in
`runs/<name>/run_manifest.json`. This document describes artifact families; it
does not assert fixed row counts or endorse historical root outputs.

## Required run lifecycle

```bash
tasb run --config small --run-name smoke
tasb analyze --run runs/smoke
tasb plot --run runs/smoke
tasb report --run runs/smoke --html
tasb verify-run --strict runs/smoke
```

`run_manifest.json` records every file, schema family, and SHA-256 checksum.
`finalization.json` binds the manifest. Reports and plots capture the verified
source manifest before adding their own files, then the bundle is finalized
again.

## Scientific artifacts

- `results/metric_evidence.csv` and JSONL — metric-schema-v2 evidence;
- typed episode/step outcomes and versioned action records;
- `results/monitor_events.csv` — monitor-evaluation-v1 inputs;
- `results/clean_vs_shifted.csv` — clean/shift treatment comparison;
- scenario manifests, execution plan, identities, traces, status, and errors;
- statistical config, confidence intervals, paired effects, and power plans;
- monitor detector, gating, calibration, utility, and Pareto tables;
- verified report/plot source snapshots and report validation;
- plots and reports whose names match the rendered statistic.

Multi-seed parent bundles retain finalized child runs and a first-class stable
analysis identity. Confidence artifacts are absent when uncertainty was not
estimated; reports disclose that absence rather than implying zero width.

Historical checked-in `results/`, `figures/`, and generated reports are not
source inputs for v0.4.0 claims.
