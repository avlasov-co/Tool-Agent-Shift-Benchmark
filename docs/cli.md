# CLI Guide

The `tasb` command wraps the benchmark workflow into reviewer-friendly commands.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Common workflow

```bash
tasb validate-config small
tasb run --config small --all-envs --all-agents --seed 42 --run-name smoke --overwrite
tasb analyze --run runs/smoke
tasb pairwise --config compound_matrix --run runs/smoke
tasb plot --run runs/smoke
tasb report --run runs/smoke --html
tasb replay CASE_ID --run runs/smoke --format markdown
tasb verify-release
```

`small`, `full`, `seeds`, `ablations`, `default`, and `compound_matrix` are
packaged configuration names. Discover them with `tasb config list`. Supplying
an explicit YAML file path remains supported for user-authored configurations.

## Commands

- `tasb run`: run benchmark evaluation and optionally snapshot outputs into `runs/<name>/`.
- `tasb analyze`: generate post-hoc analysis artifacts.
- `tasb pairwise`: run pairwise compound-fault analysis.
- `tasb plot`: generate PNG plots.
- `tasb report`: generate Markdown and optionally HTML reports.
- `tasb replay`: replay a recorded failure case as JSON, Markdown, or text.
- `tasb validate-config`: validate benchmark or pairwise configs.
- `tasb config list`: list packaged built-in configs; `tasb config validate`
  and `tasb config migrate` retain the versioned configuration workflow.
- `tasb verify-release`: run the full release verifier.
- `tasb clean`: remove generated outputs.
- `tasb plugins list|validate`: inspect and validate built-in and external plugins.
- `tasb plan`: print the resolved experiment matrix and deterministic seed policy.
- `tasb inspect-run`: inspect a self-contained run manifest.
- `tasb render-architecture`: regenerate the Mermaid architecture renders.

`python -m tool_agent_shift_benchmark` is equivalent to `tasb`; individual
submodules remain useful for development but are not the primary user surface.
# Platform commands

`tasb plugins list` lists built-in and statically discovered entry-point
metadata, including scoped discovery errors; `tasb plugins validate` checks
catalog metadata without importing unselected implementations. `tasb plan
--config <config>` resolves the Cartesian matrix and stable seed policy,
loading only explicitly selected plugins without executing episodes. `tasb run
--config <config> --workers N` executes serially by default or with
deterministic parallel scheduling. `tasb inspect-run <run>` prints the
self-describing manifest, and `tasb render-architecture` regenerates the
Mermaid renders.
