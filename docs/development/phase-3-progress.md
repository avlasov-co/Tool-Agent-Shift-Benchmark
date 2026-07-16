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

Checkpoint 16 — CI and supply-chain hardening — complete.

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

### Checkpoint 13 — isolated distribution testing

- Added `scripts/distribution_smoke.py` and `make distribution-smoke`. The
  driver copies source to a sanitized temporary directory before asking the
  standard PEP 517 backend to produce one sdist and one wheel, so builds never
  mutate or clean the active checkout.
- Archive inspection rejects VCS metadata, virtual environments, caches,
  bytecode, macOS metadata, local results/figures/runs, `node_modules`, stale
  egg-info, undeclared Python package roots, and missing packaged config,
  policy, or HTML-template resources.
- Each artifact is independently installed into a fresh virtual environment
  from an empty working directory with `PYTHONPATH` removed. The driver first
  installs the reviewed development lock, then installs the artifact with
  `--no-deps`; it verifies import location and resource access, both CLI entry
  points, config listing/validation, planning, a minimal run, analysis, HTML
  reporting, and `pip check`.
- Added focused archive-inspection tests. The full `make distribution-smoke
  PYTHON=.venv/bin/python` command built and independently exercised both
  `tool_agent_shift_benchmark-0.3.0.tar.gz` and its wheel. A first Make-target
  run exposed a virtualenv-symlink bug in the driver; preserving the selected
  venv executable path fixed it before this checkpoint's successful run.
- `ruff check`, formatting, focused strict mypy, 156 tests, `pip check`, and
  `git diff --check` passed. CI integration follows in Checkpoint 15.

### Checkpoint 14 — non-destructive release verification

- Replaced the old shell sequence with the packaged Python driver
  `tool_agent_shift_benchmark.release_verification`; `make verify-release`,
  `tasb verify-release`, and the compatibility shell wrapper all invoke it.
  The driver first copies source to a retained temporary workspace and never
  invokes cleanup, builds, tests, or benchmark generation in the active
  checkout.
- Every phase records a command or check description, status, duration,
  timeout, and dedicated log. The driver prints a readable phase table and
  writes `release-verification.json`; both the workspace and logs remain on
  success or failure for review.
- The isolated workflow creates a fresh venv from the development lock, then
  verifies compilation, lint/format/type checks, tests, branch coverage,
  config validation, deterministic planning, two fixed-seed small runs,
  analysis, plotting, HTML reports, locked Node tooling, architecture rendering,
  and the independent sdist/wheel smoke driver.
- The deterministic check compares canonical JSON/JSONL and byte content from
  each run's `results/`, `figures/`, and `docs/` bundles. It explicitly omits
  only `run_manifest.json`, whose timestamps and run-specific path are
  documented volatile fields. The completed verifier compared 31 files exactly.
- Browser acquisition is version-pinned to the Mermaid CLI's declared
  `chrome-headless-shell@131.0.6778.204`. A guarded ZIP extraction repair
  rejects traversal and links, preserves modes, and supplies the verified
  executable explicitly; this handles a partial macOS extraction from the Node
  browser installer without accepting archive-path injection.
- Full release verification passed in
  `/tmp/tasb-release-verification-zci_1e68`, including architecture rendering
  and distribution smoke (the final phase took 39.262 seconds). Focused
  verifier/archive tests, lint, formatting, and `git diff --check` passed.

### Checkpoint 15 — CI

- Replaced the single mutable-action workflow with focused, timeout-bounded
  jobs for quality, tests across Python 3.10--3.14, branch coverage,
  configuration validation, package builds, isolated installation, one
  designated deterministic release verification, documentation checks, and a
  macOS distribution smoke on Python 3.12.
- All CI jobs use the two hash-checked lockfiles through `make setup` and
  setup-python's lock-aware pip cache. The expensive reproducibility and
  architecture workflow runs only once on Linux; the macOS lane independently
  verifies both distribution formats without relying on a checkout import.
- Added concurrency cancellation, a read-only default token, explicit shell
  strict mode, immutable action references with human-readable version
  comments, and failure-only upload of retained release/distribution logs.
- Added `scripts/check_docs.py`, which validates local Markdown links without
  mechanically rewriting historical documents. The two intentionally generated
  architecture-render references are allowed only because strict architecture
  rendering is separately enforced by the release-verification job.
- Local validation parsed the workflow YAML, checked all 35 Markdown files,
  and passed `git diff --check`. Security workflow and dependency automation
  are added next in Checkpoint 16.

### Checkpoint 16 — CI and supply-chain hardening

- Kept workflow default permissions at `contents: read`, while giving CodeQL
  only its required `security-events: write`. Workflows do not use
  `pull_request_target`, publishing, deployment credentials, or privileged
  release paths, so untrusted fork pull requests cannot receive secrets.
- Pinned every workflow action to a reviewed immutable SHA with its readable
  release version beside it. Added Dependabot updates for pip, npm, and Actions;
  a pull-request dependency-review workflow; and scheduled/push/PR Python
  CodeQL analysis.
- Added a locked `pip-audit` job and reproducible CycloneDX SBOM generation
  beside the standard sdist/wheel build artifacts. A local audit of
  `requirements/development.txt` with `pip-audit 2.10.1` reported no known
  vulnerabilities at the time of validation.
- Expanded `SECURITY.md` with lockfile, immutable-action, fork-PR, SBOM, secret
  scanning, and push-protection expectations. The safe browser ZIP repair is
  covered by traversal and executable-mode regression tests; shell commands in
  repository scripts were also reviewed for quoted interpolation and do not
  execute untrusted archive members.
- Workflow YAML parses cleanly. The action-pinning/security tests, verifier
  tests, docs checks, lint, formatting, and `git diff --check` passed.
