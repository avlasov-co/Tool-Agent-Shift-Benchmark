# Phase 1 execution plan

## Problem statement

The repository contains an unreleased platform-evolution implementation together
with regenerated benchmark artifacts and local development by-products.  Phase 1
must make that work recoverable, document the repository contract, add a
non-destructive audit entry point, and establish a repeatable quality toolchain
without changing experimental evidence merely to obtain passing checks.

## Observed behavior and baseline

- `main` is at `v0.3.0` (`c1572db`); the worktree contains modified source,
  documentation, release, configuration, and generated benchmark files, plus
  untracked platform modules, architecture renders, a smoke run bundle, and
  generated package metadata.
- Existing documented commands use `python`.  In this environment `python` is
  absent.  `python3` is Python 3.14.6 but does not yet have `pytest` installed,
  so the baseline compile/test command cannot start (`No module named pytest`).
- A recoverable backup branch, `backup/phase-1-pre-preservation`, points to a
  stash commit containing the pre-preservation tracked and untracked work.

## Invariants

- Policy-visible contexts and monitor inputs never receive evaluator-only state.
- Run and episode identities remain deterministic for the same resolved config.
- Audit and release verification do not delete, rewrite, or regenerate user
  files; generated outputs are evidence, not a way to mask test failures.
- Malformed configuration fails explicitly; scientific values are serialized by
  declared serializers rather than `default=str`.
- Source changes, generated experiment outputs, and local junk stay isolated.

## Affected modules

- Core platform contracts, catalog, evaluator, orchestration, episode, artifact,
  config, CLI, and evaluation modules under `src/`.
- Tests under `tests/`, build metadata in `pyproject.toml`, CI/Make targets, and
  release/repository documentation.
- New development documentation, `AGENTS.md`, `PLANS.md`, and audit tooling.

## Migration strategy

1. Audit and commit legitimate source, tests, configuration, release scripts,
   and documentation while preserving generated evidence in a named local ref.
2. Add focused repository and planning instructions.
3. Implement an isolated audit runner that records each check and never invokes
   cleanup or generation commands.
4. Add Ruff, mypy, branch coverage, pre-commit, and stable Make targets; fix
   real violations and document any narrowly scoped transition exceptions.

## Compatibility

The package continues to support Python 3.10+. Existing `python -m src.*` and
`tasb` entry points remain supported. New audit reports are written below an
explicit, ignored output directory unless the caller supplies another location.

## Tests and validation

Each checkpoint runs focused tests, the full suite, `git diff --check`, and an
inspection for generated artifacts. Final validation adds lint, formatting,
typing, branch coverage, compilation, package build, installed-wheel smoke, and
`make audit`. Baseline environment failures are recorded rather than hidden.

## Rollout and rollback

Each checkpoint is a separate local commit. The pre-preservation backup branch
and stash make the original work recoverable. A change can be reverted by commit
without deleting local evidence; generated evidence remains available through a
separate named preservation ref.

## Unresolved risks

- The local Python 3.14 environment lacks the test toolchain and may expose
  compatibility issues not present on the supported 3.10--3.13 range.
- Existing committed result and figure snapshots are generated evidence; their
  modified replacements need provenance rather than automatic inclusion.
- The current release script is destructive and must not be used by the audit.
