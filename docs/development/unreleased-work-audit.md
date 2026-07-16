# Unreleased work audit

## Current state

Baseline is `main` at `c1572db` (`v0.3.0`). Before any preservation work, all
tracked modifications and untracked non-ignored files were captured in stash
commit `1d0c7485a35d9e5a3f6951490031c919ca79a3c5`, retained both as
`stash@{0}` and local branch `backup/phase-1-pre-preservation`. The stash was
applied back cleanly for inspection.

The baseline test command could not run through the documented interpreter:
`python` is absent and system `python3` lacked pytest. In an isolated temporary
Python 3.14 environment, compile plus pytest passed: **54 passed**.

## Path-by-path classification

| Category | Paths | Assessment |
|---|---|---|
| Source code | `src/tool_agent_shift_benchmark/analysis/run_analysis.py`, `src/tool_agent_shift_benchmark/cli.py`, `src/tool_agent_shift_benchmark/run_eval.py`, `src/tool_agent_shift_benchmark/orchestration.py`, `src/tool_agent_shift_benchmark/core/__init__.py`, `src/tool_agent_shift_benchmark/core/artifacts.py`, `src/tool_agent_shift_benchmark/core/catalog.py`, `src/tool_agent_shift_benchmark/core/config_schema.py`, `src/tool_agent_shift_benchmark/core/contracts.py`, `src/tool_agent_shift_benchmark/core/episode.py`, `src/tool_agent_shift_benchmark/core/evaluator.py`, `src/tool_agent_shift_benchmark/core/orchestration.py`, `src/tool_agent_shift_benchmark/core/plugin_catalog.py`, `src/tool_agent_shift_benchmark/core/run_artifacts.py`, `src/tool_agent_shift_benchmark/reporting/plots.py`, `src/tool_agent_shift_benchmark/reporting/report.py` | Intentional platform evolution: contracts, catalog, visible/evaluator boundary, deterministic planning, scheduling, structured artifacts, CLI, analysis, and reporting. Preserve as source. |
| Tests | `tests/test_platform_evolution.py` | Intentional regression coverage for the platform evolution. Preserve with source. |
| Orchestration and contracts | `src/tool_agent_shift_benchmark/core/contracts.py`, `src/tool_agent_shift_benchmark/core/catalog.py`, `src/tool_agent_shift_benchmark/core/evaluator.py`, `src/tool_agent_shift_benchmark/core/orchestration.py`, `src/tool_agent_shift_benchmark/orchestration.py`, `src/tool_agent_shift_benchmark/run_eval.py`, `src/tool_agent_shift_benchmark/cli.py`, `src/tool_agent_shift_benchmark/core/config_schema.py` | Intentional; depends on the core source and test changes above. Preserve together. |
| CLI and configuration | `src/tool_agent_shift_benchmark/cli.py`, `src/tool_agent_shift_benchmark/run_eval.py`, `src/tool_agent_shift_benchmark/core/config_schema.py`, `pyproject.toml`, `Makefile` | Intentional support for planning, plugins, resumable runs, architecture rendering, and runtime dependency metadata. Preserve, then extend in Checkpoints 3--4. |
| Artifact handling | `src/tool_agent_shift_benchmark/core/artifacts.py`, `src/tool_agent_shift_benchmark/core/run_artifacts.py`, `src/tool_agent_shift_benchmark/core/episode.py`, `results/episodes.jsonl`, `results/evaluator_traces.jsonl`, `results/orchestration_errors.jsonl`, `runs/` | The modules are source and belong with the platform work. The JSONL files and `runs/smoke/` are generated evidence and must be preserved separately. |
| Analysis and reporting | `src/tool_agent_shift_benchmark/analysis/run_analysis.py`, `src/tool_agent_shift_benchmark/reporting/plots.py`, `src/tool_agent_shift_benchmark/reporting/report.py`, `docs/experimental_report.md`, `figures/agent_safety_profile.png`, `figures/calibration_curve.png`, `figures/coverage_vs_safety.png`, `figures/failure_breakdown.png`, `figures/failure_cluster_topn.png`, `figures/monitor_recall_precision.png`, `figures/monitor_threshold_curve.png`, `figures/pairwise_compound_heatmap.png`, `figures/recovery_rate.png`, `figures/static_vs_dynamic_gap.png`, `figures/unsafe_action_rate.png`, `figures/unsafe_step_rate.png` | Code is intentional and preserved. The report and PNG replacements are generated evidence and stay outside source commits. |
| Documentation | `PROJECT_SPEC.md`, `README.md`, `docs/agent_monitor_boundaries.md`, `docs/artifact_manifest.md`, `docs/cli.md`, `docs/index.md`, `docs/release_process.md`, `docs/architecture.mmd`, `scripts/render_architecture.sh` | Intentional repository/source documentation and render recipe. Preserve. |
| Generated benchmark outputs | `results/config.json`, `results/episode_log.csv`, `results/failure_cases.csv`, `results/monitor_events.csv`, `results/multistep_traces.jsonl`, `results/static_vs_dynamic.csv`, `results/summary.csv`, plus the three JSONL files above, all `figures/*.png` replacements, `docs/experimental_report.md`, `docs/architecture.svg`, `docs/architecture.png`, and `runs/smoke/` | Generated from a local experiment or renderer. Preserve in a named local ref, never add to the source commits solely to satisfy checks. |
| Build metadata | `pyproject.toml` | Intentional project metadata update (`matplotlib`). Preserve as source. |
| Local junk | `tool_agent_shift_benchmark.egg-info/`, `.venv/`, `.pytest_cache/`, all `__pycache__/`, `.DS_Store` including under `runs/` | Generated/local only. Do not commit. `runs/` and `*.egg-info/` are now ignored. |
| CI and release | `.github/workflows/ci.yml`, `scripts/verify_release.sh` | Intentional release/render integration. Preserve, but the existing verifier is destructive and must never be called by the audit. |

## Dependencies between changes

The catalog, contracts, evaluator, and orchestration modules underpin updated
config validation, `run_eval`, CLI commands, structured episode persistence,
run manifests, and the platform-evolution tests. Analysis and reporting code
consume structured episodes with a CSV compatibility fallback. Architecture
documentation and the renderer explain this same boundary. Generated files are
outputs of that source and are not a source dependency.

## Preservation strategy

1. Keep the named stash and backup branch unchanged throughout Phase 1.
2. Commit only legitimate source, tests, configuration, CI/release scripts, and
   source documentation in the Checkpoint 1 commit.
3. Before that commit, save generated benchmark evidence in an additional named
   local stash/reference, then restore a clean source-only worktree.
4. Leave `.venv`, caches, OS files, egg-info, and run bundles uncommitted and
   ignored. Do not run cleanup against user-owned output.

## Proposed commit structure

1. **Checkpoint 1:** preserve and split the platform source work; add audit,
   plan, progress records, and generated/local-file isolation.
2. **Checkpoint 2:** repository instructions (`AGENTS.md`, `PLANS.md`).
3. **Checkpoint 3:** non-destructive audit command, tests, and documentation.
4. **Checkpoint 4:** Ruff, mypy, coverage, pre-commit, stable commands, and
   CI/toolchain tests.

## Risks

- The current release script begins by deleting generated output and therefore
  cannot be used as an audit primitive.
- Existing generated replacements may be valuable experimental evidence but do
  not yet have a recorded reproduction command/version manifest suitable for a
  release evidence commit.
- Python 3.14 validates the current source but supported 3.10--3.13 still need
  CI coverage.
