# Changelog

## v0.2.0 — 2026-05-24

- Added post-hoc analysis runner: `python -m src.analysis.run_analysis`.
- Added failure clustering artifacts for unsafe cases.
- Added monitor threshold sweeps and calibration tables based on recorded risk scores.
- Added agent safety profiles combining safety, coverage, recovery, latency, and static-vs-dynamic gap signals.
- Added fixed compound-shift comparison against clean and worst single-fault rows.
- Added analysis manifest generation and `docs/analysis_report.md` output.
- Added tests for deterministic clustering, monitor confusion counts, agent profiles, and analysis artifact generation.

## Unreleased

- Added visible-only `ObservationContext` for agents and monitors.
- Prevented the retry baseline from bypassing shifted observations by calling a clean tool response after a fault.
- Added evaluator-boundary regression tests and documentation.
- Regenerated small benchmark outputs and plots after the boundary change.

## v0.1.0 — 2026-04-29

Initial release.

- Core dataclass model and stable episode IDs.
- Synthetic FileOps, CalendarOps, and RiskOps environments.
- Deterministic fault injectors.
- Five agent policies.
- Six monitors.
- Metrics, plots, reporting, and failure replay.
- Tests, CI, Makefile, documentation, and release packaging.
