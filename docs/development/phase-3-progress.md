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

Checkpoint 12 — reproducible dependencies — complete.

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

### Checkpoint 11 — package resources

- Moved every shipped YAML config into
  `tool_agent_shift_benchmark/resources/configs/`, the offline policy into
  `resources/policies/`, and added the HTML report template to
  `resources/templates/`. `pyproject.toml` now declares all three data groups.
- Added importlib-resources access with named built-ins (`small`, `full`,
  `seeds`, `ablations`, `default`, `compound_matrix`), `tasb config list`, and
  continued support for explicit external YAML paths. The historical
  `configs/small.yaml` spelling resolves to its packaged counterpart where
  practical.
- The offline fixture policy now has strict schema/version validation. Its
  visible-signal rules, actions, confidences, and reasons drive decisions; the
  policy path, version, SHA-256, and observed visible signals are recorded in
  every fixture decision. Built-in configurations record that same policy hash
  in the scientific identity resource map.
- Tests prove named-resource loading, external-path loading, clear missing or
  malformed policy errors, and that a changed external policy changes the
  resulting action. The suite has 154 passing tests.
- A clean temporary source copy built a regular wheel containing config,
  policy, and template resources. A fresh installed wheel, run from an empty
  directory, listed/validated/planned `small` and loaded the fixture policy
  without checkout access or `PYTHONPATH`.
- `ruff check`, `ruff format --check`, focused strict mypy, and `git diff
  --check` passed.

### Checkpoint 12 — reproducible dependencies

- Made `PyYAML` the sole runtime dependency. Plotting is an explicit
  `analysis` extra and imports its plotting stack only when plots are
  requested, with an actionable install message if it is absent. Development,
  documentation, and release tooling live in bounded extras.
- Replaced the floating `requirements.txt` file with two generated,
  hash-checked lockfiles: `requirements/runtime.txt` for the installed runtime
  graph and `requirements/development.txt` for every declared extra. The
  accompanying README records the exact `pip-tools==7.5.3` regeneration
  commands. `make setup` first installs the development lock with
  `--require-hashes`, then installs the checkout with `--no-deps`.
- Added a committed `package-lock.json` for exact Mermaid/browser tooling and
  changed architecture rendering to use its locked local executable. The
  script no longer triggers an uncontrolled `npx` download; unavailable
  tooling retains the existing checked-in render unless strict mode is set.
- Fresh temporary environments proved the intended split: runtime lock plus a
  wheel installed `--no-deps` passed CLI, module-entry, built-in config, and
  planning checks outside the checkout, while plotting failed with the
  documented optional-dependency message. The full development lock plus
  extras passed imports and `pip check`.
- `npm ci --ignore-scripts` installed the committed Node graph and confirmed
  Mermaid CLI `11.12.0` and Puppeteer browsers `2.7.1`. `make setup`, lint,
  formatting, focused strict mypy, tests, `pip check`, and `git diff --check`
  passed.
