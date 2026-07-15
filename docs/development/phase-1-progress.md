# Phase 1 progress

## Observed repository state

Discovery began from `main` at `c1572db` (`v0.3.0`) with significant unreleased
platform-evolution source work, matching tests and documentation, regenerated
results and figures, an untracked smoke bundle, architecture render outputs, and
generated egg-info. A recovery branch, `backup/phase-1-pre-preservation`, points
at stash commit `1d0c7485a35d9e5a3f6951490031c919ca79a3c5`; the working tree was
then restored from that stash without loss.
Generated evidence was then split into `backup/phase-1-generated-evidence`
(also retained as the newest named stash), leaving source, test, configuration,
CI/release, and source-documentation work for the Checkpoint 1 commit.

## Current checkpoint

Checkpoint 1 -- auditing and splitting unreleased work.

## Decisions

- Preserve the source/platform implementation and its tests as source work.
- Preserve generated results, figures, architecture render outputs, and smoke
  bundles separately; do not include them in source commits without an explicit
  provenance release decision.
- Treat `.venv`, caches, `.DS_Store`, and `*.egg-info` as local/generated junk.
- Record the missing local test toolchain as a baseline environment failure and
  provision an isolated tool environment for validation rather than modifying
  project artifacts.

## Commands executed

- `git status --short --branch`, branch/tag/history/ignored-file inspection, and
  repository file discovery.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m compileall -q src tests && ... pytest -q`
  (failed: `python` command missing).
- Equivalent `python3` command (failed: Python 3.14.6 has no `pytest`).
- `git stash push --include-untracked`, creation of
  `backup/phase-1-pre-preservation`, and `git stash apply` to verify recovery.
- `git stash push --include-untracked -- figures results ...` and creation of
  `backup/phase-1-generated-evidence` to isolate generated evidence.
- Isolated-environment compilation and pytest: **54 passed**; focused platform
  tests: **7 passed**; `git diff --check`: passed.

## Test results

No tests ran at baseline because the documented interpreter command is missing
and the available interpreter has no pytest installation. The preserved source
work passes 54 tests in the isolated environment; platform-focused tests pass 7.

## Failures and resolutions

- Baseline command portability is incomplete. Phase 4 will standardize commands
  on `python3` while retaining an overridable interpreter variable.
- Test dependencies will be installed in an isolated temporary environment for
  validation; the repository's existing `.venv` is left untouched.

## Remaining risks

- Python 3.14 may surface dependency or typing-tool compatibility issues.
- Python 3.10--3.13 remain to be covered by CI after the quality toolchain work.

## Exact handoff required for Phase 2

Phase 2 should start from the final Phase 1 commit with a clean source tree,
review `docs/development/phase-1-progress.md`, retain the named backup refs for
unreleased generated evidence, run `make audit`, and decide whether any preserved
benchmark output is reproducible enough for an evidence-only release commit.
