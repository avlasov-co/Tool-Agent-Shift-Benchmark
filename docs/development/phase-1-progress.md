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

Phase 1 complete -- final validation and handoff recorded.

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
- Audit runner tests: **5 passed**. A non-strict audit records all required
  checks and writes its JSON/log output under its caller-selected directory.
  It correctly reports the dirty in-progress tree and missing checked-in
  `results/episodes.jsonl` evidence; build, wheel inspection, isolated install,
  CLI smoke, configuration, deterministic planning, unit tests, and coverage
  passed in the temporary audit run.
- Quality-toolchain validation: Ruff lint and format check pass across `src/`
  and `tests/`; strict mypy passes for core contracts and orchestration; 59
  tests pass; final branch coverage is 73.68% against a 73% floor. `make audit`
  passes Git cleanliness, junk detection, compilation, tests, coverage,
  configuration, deterministic planning, package build, wheel inspection,
  isolated installation, CLI smoke, and metadata checks. It reports only the
  absent checked-in `results/episodes.jsonl` evidence.

## Test results

No tests ran at baseline because the documented interpreter command is missing
and the available interpreter has no pytest installation. The preserved source
work passes 54 tests in the isolated environment; platform-focused tests pass 7.

## Failures and resolutions

- Stable Make commands now use an overridable `PYTHON` variable, defaulting to
  `python3`; use the isolated environment interpreter in this workspace.
- Test dependencies will be installed in an isolated temporary environment for
  validation; the repository's existing `.venv` is left untouched.

## Remaining risks

- Python 3.14 may surface dependency or typing-tool compatibility issues.
- Python 3.10--3.13 remain to be covered by CI after the quality toolchain work.

## Completed checkpoints

- Checkpoint 1 committed as `421eb8a` (`Preserve and separate unreleased
  platform work`). It preserves source work, tests, repository documentation,
  and the audit trail while generated evidence remains in a named backup ref.
- Checkpoint 2 committed as `1eddee2` (`Add repository execution
  instructions`). `AGENTS.md` and `PLANS.md` now encode the verified repository
  boundaries, commands, generated-file policy, and planning structure.
- Checkpoint 3 committed as `6180301` (`Add non-destructive repository audit`).
  The audit aggregates checked results, logs, strict/non-strict exit behavior,
  timeouts, subprocess failures, skipped checks, JSON reports, package checks,
  isolated installation, and CLI smoke without invoking cleanup or generation.
- Checkpoint 4 configures Ruff, formatting, focused strict mypy, branch
  coverage, pre-commit, stable Make commands, explicit scientific JSON
  serialization, and non-destructive release verification. The final checkpoint
  commit is the current `HEAD`.

## Exact handoff required for Phase 2

Phase 2 should start from the final Phase 1 commit with a clean source tree,
review `docs/development/phase-1-progress.md`, retain the named backup refs for
unreleased generated evidence, run `make audit`, and decide whether any preserved
benchmark output is reproducible enough for an evidence-only release commit.
Before treating the current source as releasable, reproduce the structured-output
run in a named run bundle and make an explicit provenance decision for
`results/episodes.jsonl` and any associated figures/reports; do not copy them
from the backup merely to satisfy the audit.
