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

Checkpoint 43 — ArtifactStore-only isolated bundle writing — complete;
Checkpoint 44 is next.

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

### Checkpoint 43 — ArtifactStore-only run bundles

- Replaced copy-after-write `snapshot_outputs` behavior with an explicit
  `artifact-store-v2`. New bundles have a unique root and the store validates
  every run-relative path; it has no global-results copy or restore API.
- Runtime records now write through the store under one bundle: normalized
  configuration, identity, plugin descriptors, scenario manifests, episode
  data, failures, statuses, policy/evaluator traces, analysis, plots, reports,
  and the final manifest/checksum inventory. The normal run command creates the
  bundle before execution, so no result first exists outside it.
- Updated ordinary, seed-sweep, all-environment/agent sweep, pairwise, replay,
  analysis, report, plot, and standalone entry points to use explicit bundles.
  Global workspace cleanup/restore is retired rather than deleting or mutating
  historical evidence. Historical `snapshot_outputs` is now only a name-stable
  finalizer for files already in a bundle.
- Added stale-global isolation coverage: stale `results/`, `figures/`, and
  `docs/` files are neither copied into nor deleted by a run; analysis, report,
  and plot smoke files remain self-contained below the bundle.
- Full pytest passes after migrating legacy-path tests to explicit stores.
  A command smoke exercised `tasb run`, `analyze`, `report --html`, `plot`, and
  `pairwise` against a bundle with deliberately stale global files.
