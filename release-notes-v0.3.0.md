# Tool-Agent Shift Benchmark v0.3.0

## Highlights

- Added the `tasb` CLI for benchmark runs, analysis, pairwise compounds, plots, reports, replay, config validation, release verification, and cleanup.
- Added named run directory snapshots under `runs/`.
- Added config validation for benchmark and pairwise compound configs.
- Added HTML analysis report generation.
- Enhanced failure replay with JSON, Markdown, and text output plus failure-cluster lookup.
- Added analysis plots for monitor thresholds, calibration, agent safety profiles, pairwise compound effects, and top failure clusters.
- Strengthened release verification and aligned package metadata with the changelog.

## Validation

Release verification command:

```bash
bash scripts/verify_release.sh
```

Expected result:

```text
47 passed
release verification complete
```

## Safety boundary

This release remains synthetic and non-operational. It does not add real API calls, real filesystem actions outside local benchmark artifacts, real calendars, real market data, credentials, exploit code, bypass guidance, or production safety claims.
