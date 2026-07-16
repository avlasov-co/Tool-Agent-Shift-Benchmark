# Repository instructions

## Structure and boundaries

- `src/tool_agent_shift_benchmark/` contains the package. `src/tool_agent_shift_benchmark/core/` owns contracts, deterministic
  planning, orchestration, serialization, run artifacts, and evaluator-side
  services; `src/tool_agent_shift_benchmark/agents/`, `src/tool_agent_shift_benchmark/environments/`, `src/tool_agent_shift_benchmark/faults/`, and
  `src/tool_agent_shift_benchmark/monitors/` provide benchmark components; `src/tool_agent_shift_benchmark/analysis/` and
  `src/tool_agent_shift_benchmark/reporting/` consume experiment outputs.
- `src/tool_agent_shift_benchmark/resources/` holds packaged validated YAML
  configurations, policy fixtures, and templates; `tests/` is the unit and
  regression suite; `scripts/` contains explicit operational scripts;
  `docs/` holds user and development documentation.
- Agents and monitors may receive only `ObservationContext` and policy-visible
  `ToolResponse`. Hidden evaluator state, ground truth, and shift provenance
  must not reach an agent, monitor, policy trace, plugin API, or planner output.
- Use `runs/<name>/` for run-scoped artifacts. Treat root `results/`,
  `figures/`, and generated reports as evidence outputs, not source inputs.

## Environment and stable commands

Use Python 3.10 or newer. Create an isolated environment and install development
dependencies before running checks:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
make setup
```

The supported repository commands are:

```bash
make lint
make format
make format-check
make typecheck
make test
make coverage
make audit
```

`make test` compiles the package and runs pytest. `make coverage` runs branch
coverage. `make audit` is diagnostic and non-destructive; it writes a JSON
report and per-check logs below `.audit/` by default. Use `python -m build` for
the package build and install the resulting wheel into a fresh temporary virtual
environment before exercising `tasb --help`, `tasb validate-config`, and
`tasb plan` as installed-package smoke tests.

To generate experiment evidence, use an explicit run name, for example
`tasb run --config small --run-name review-smoke`, then run
`tasb analyze --run runs/review-smoke`, `tasb plots --run runs/review-smoke`,
and `tasb report --run runs/review-smoke`. Never regenerate root benchmark
outputs merely to make tests pass.

## Determinism, artifacts, and plugins

- Keep run, episode, scenario, and seed identity derived from the resolved
  config and stable hashes. Do not use process ordering, wall-clock values, or
  random global state to define scientific identities.
- Use explicit data-model serializers for scientific records. Do not serialize
  scientific data via `json.dumps(..., default=str)`.
- Validate configuration before execution and fail clearly on malformed or
  unknown values; do not silently ignore malformed configuration.
- Keep generated files out of source commits unless an evidence release records
  the exact command, config, seed, runtime version, and provenance. Never
  commit `.venv`, caches, `__pycache__`, `.pyc`, `.DS_Store`, build directories,
  `*.egg-info`, local run bundles, coverage output, or IDE state.
- External plugins must have a declared compatible contract version and a
  validated descriptor. They must not bypass policy-visible boundaries, read
  evaluator-only state, mutate unrelated user files, or rely on unvalidated
  configuration. Treat plugin failures as orchestration errors, not benchmark
  safety outcomes.

## Release and definition of done

Release verification must be non-destructive: it may build and install isolated
artifacts but must never clean, delete, or rewrite user-owned results, figures,
or documents. Run the audit, validation commands, and installed-wheel smoke in
addition to checking release metadata consistency. Never make publication claims
that are unsupported by an executed, recorded experiment.

Before handing off a change: run the focused and full relevant tests, `git diff
--check`, lint, format-check, typing, branch coverage, compilation, package
build, installed-package smoke, and `make audit`; inspect staged files for
generated artifacts; document baseline failures and remaining risks. Do not use
broad exception swallowing, blanket lint/type-check suppression, or temporary
exclusions without a path, justification, and removal condition.
