# Release Process

Use this checklist before publishing an archive or GitHub release.

## Required command

```bash
bash scripts/verify_release.sh
```

The verifier runs compile checks, tests, config validation, a smoke benchmark, analysis, pairwise compounds, plots, Markdown report generation, HTML report generation, artifact checks, and version metadata checks.

## Metadata checks

- `pyproject.toml` version must match the latest changelog version.
- `release-notes-vX.Y.Z.md` should exist for the intended release.
- Generated CSV artifacts must have headers and expected rows.
- Generated plots must be non-empty.
- The archive must not include `.pytest_cache`, `__pycache__`, `.venv`, or local junk.

## Archive command

```bash
tar --exclude='.git' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.venv' -czf tool-agent-shift-benchmark-vX.Y.Z.tar.gz Tool-Agent-Shift-Benchmark-main
```
