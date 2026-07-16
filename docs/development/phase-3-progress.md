# Phase 3 progress

## Baseline

- Started from the clean Phase 2 result on `codex/phase-2-identity-config` and
  created `codex/phase-3-packaging-release`.
- Read repository instructions, major plans, Phase 1/2 plans and progress,
  Python metadata/dependencies, resources, CLI/audit/release scripts, workflow,
  citation/changelog/release notes, and archive-ignore rules.
- Baseline confirms a source-root import package, checkout-relative resources,
  a destructive reproduction script, mutable CI actions, uncontrolled `npx`,
  and metadata drift. No source or evidence artifacts have been regenerated.

## Current checkpoint

Checkpoint 10 — proper source layout — complete.

## Checkpoint evidence

Evidence and verification results will be appended before every checkpoint
commit. The final section will retain baseline failures and remaining risks.

### Checkpoint 10 — proper source layout

- Moved the real package to `src/tool_agent_shift_benchmark/` and changed all
  runtime and test imports, console metadata, module invocations, Make targets,
  scripts, and current documentation to the stable import name.
- Added `tool_agent_shift_benchmark.__main__`, so both `tasb` and
  `python -m tool_agent_shift_benchmark` expose the CLI.
- Removed pytest's `pythonpath = ["."]` masking and configured setuptools to
  discover only `tool_agent_shift_benchmark*` below `src/`.
- Intentionally did not retain a `src` compatibility shim. It is an overly
  generic import name that would conceal source-tree leakage; the v0.3.1
  documentation records the removal explicitly.
- Editable validation: `make setup PYTHON=.venv/bin/python`, `make test
  PYTHON=.venv/bin/python`, `tasb --help`, and `python -m
  tool_agent_shift_benchmark --help` passed (151 tests).
- Regular-install validation: a clean temporary source copy produced a wheel;
  a fresh virtual environment installed it with declared dependencies, then
  imported from `site-packages` and exercised both CLI forms from an empty
  working directory without `PYTHONPATH`.
- The first active-worktree wheel build contained a stale old `src` package
  from ignored `build/` state. The active checkout was not cleaned; subsequent
  builds used a clean temporary source copy. Checkpoint 13 will make that
  isolated build and archive inspection mandatory, preventing this class of
  developer-machine leakage.
- `ruff check`, `ruff format --check`, focused strict mypy, and `git diff
  --check` passed. A mechanical rename initially rewrote three local
  `src`-variable expressions in `run_artifacts`; the full test suite exposed
  the mistake and it was corrected before commit.
