# CLI Guide

The `tasb` command wraps the benchmark workflow into reviewer-friendly commands.

## Install

```bash
python -m pip install -e .
```

## Common workflow

```bash
tasb validate-config configs/small.yaml
tasb run --config configs/small.yaml --all-envs --all-agents --seed 42 --run-name smoke --overwrite
tasb analyze --run runs/smoke
tasb pairwise --config configs/compound_matrix.yaml --run runs/smoke
tasb plot --run runs/smoke
tasb report --run runs/smoke --html
tasb replay CASE_ID --run runs/smoke --format markdown
tasb verify-release
```

## Commands

- `tasb run`: run benchmark evaluation and optionally snapshot outputs into `runs/<name>/`.
- `tasb analyze`: generate post-hoc analysis artifacts.
- `tasb pairwise`: run pairwise compound-fault analysis.
- `tasb plot`: generate PNG plots.
- `tasb report`: generate Markdown and optionally HTML reports.
- `tasb replay`: replay a recorded failure case as JSON, Markdown, or text.
- `tasb validate-config`: validate benchmark or pairwise configs.
- `tasb verify-release`: run the full release verifier.
- `tasb clean`: remove generated outputs.

Legacy `python -m src...` commands remain supported.
