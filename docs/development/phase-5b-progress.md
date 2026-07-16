# Phase 5B progress

## Baseline

- Started from clean Phase 5A terminal commit `da5bd70` and created
  `codex/phase-5b-artifacts-resume`.
- Read repository instructions, major-plan requirements, Phase 1–5A progress
  and handoff records, command entry points, planner/runner, artifact facade,
  checkpoint path, manifests, analysis/reporting paths, and relevant tests.
- Baseline gaps are duplicate entry-point dispatch, root-output copying into run
  directories, a non-owning `ArtifactStore`, non-atomic artifact paths, and
  checkpoint compatibility limited primarily to a run ID.

## Current checkpoint

Checkpoint 42 — unify experiment runners — complete; Checkpoint 43 is next.

## Checkpoint evidence

Evidence, contracts, compatibility notes, validation, and commit IDs will be
added before each numbered checkpoint commit.

### Checkpoint 42 — unified execution request, plan, and runner

- Added `execution-request-v1`, `execution-plan-v1`, and
  `execution-result-v1`. Every public execution request is normalized before
  planner construction, then executes through the existing canonical
  `ExperimentPlanner` and `RunCoordinator` path.
- Ordinary run, all-environment/agent sweep, seed wrapper, severity and monitor
  matrices expressed in configuration, replay, and resume now use the common
  request/result API. Pairwise compatibility helpers no longer build identities
  or invoke `EpisodeRunner` directly: they project their treatment from a
  normalized ordinary plan and execute it through the coordinator.
- `tasb plan` uses the same request normalizer as API execution and emits the
  versioned resolved execution plan, including every matrix dimension. Worker
  count remains operational: it does not change semantic run or episode IDs.
- Added CLI/API parity, worker-count, and pairwise-projection tests. Focused
  execution, identity, pairwise, reproducibility, and schema suites pass (62
  tests); Ruff lint, format-check, strict mypy, and `git diff --check` pass.
