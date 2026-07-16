# Phase 2 progress

## Baseline

- Started from clean Phase 1 commit `fb3bd01` on branch
  `codex/phase-2-identity-config`.
- Retained `backup/phase-1-pre-preservation` and
  `backup/phase-1-generated-evidence` plus their named stashes.
- Provisioned the ignored `.venv` from declared development dependencies.
- Baseline `make audit PYTHON=.venv/bin/python` passed cleanliness, junk
  detection, compilation, tests, branch coverage, config validation,
  deterministic planning, build/wheel/install/CLI smoke, and metadata checks.
  It reported only the documented missing checked-in
  `results/episodes.jsonl` evidence.

## Current checkpoint

Checkpoint 5 complete and pending commit: selector-safe canonical episode
planning.

## Checkpoint evidence

### Checkpoint 5 — episode filtering

- Reproduced the defect: selecting copied episode
  `ep_de1f4d89465060fb` changed run `run_dfb379c348b1cb76` to
  `run_38027f281c612505` and returned zero episodes.
- Reproduced scenario selector leakage: scenario index 1 changed the run to
  `run_e332b26e1a7c93a8` and changed the episode ID.
- Canonical construction now completes before episode-ID, scenario-index,
  pagination, worker-partition, resume, or replay selection.
- Complete-plan compatibility is preserved: the reproduced run and episode IDs
  remain `run_dfb379c348b1cb76` and `ep_de1f4d89465060fb`; selecting that ID now
  returns exactly the canonical episode.
- Unknown episode and resume IDs raise `UnknownEpisodeSelectionError`; a valid
  combination may intentionally produce an empty selection without changing
  run identity.
- CLI and Python planning share the same selectors and return identical
  matrices. Partition union/disjointness and canonical ordering are covered.

## Compatibility decisions

- Preserve historical IDs from complete unfiltered plans at Checkpoint 5.
- Treat IDs emitted by the broken filtered implementation as non-canonical;
  document and retain them as legacy provenance rather than silently mapping
  them to a potentially different semantic episode.

## Validation log

- Baseline audit: all checks passed except the expected generated-artifact
  consistency finding for absent `results/episodes.jsonl`.
- Checkpoint 5 focused identity/platform/CLI/reproducibility suite: 26 passed.
- Checkpoint 5 full suite and branch coverage: 72 passed; 74.46% branch
  coverage against the 73% floor.
- Ruff lint and format check, strict mypy, compilation, and `git diff --check`:
  passed.
- Pre-commit diagnostic audit passed junk detection, compilation, tests,
  coverage, config validation, deterministic planning, package build, wheel
  inspection/install, CLI smoke, and release metadata. It reported the
  expected in-progress dirty worktree and the baseline absent structured
  evidence; both are recorded rather than hidden.

## Remaining work

- Complete and commit Checkpoints 5, 6, 7, 8, and 9 sequentially.
- Run the final installed-wheel, audit, deterministic identity, compatibility,
  and focused leakage review gates.
