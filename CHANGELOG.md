# Changelog

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
