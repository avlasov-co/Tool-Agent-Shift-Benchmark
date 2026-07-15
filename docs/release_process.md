# Release Process

Use this checklist before publishing an archive or GitHub release.

## Required command

```bash
bash scripts/verify_release.sh
```

The verifier runs compilation, tests, linting, formatting, typed core-contract
checks, branch coverage, package build, installed-wheel CLI smoke, configuration
validation, deterministic planning, artifact consistency, and release-metadata
checks. It writes all temporary files to an isolated audit directory.

It never cleans, regenerates, or overwrites root `results/`, `figures/`, or
reports. If checked-in experiment evidence is missing or inconsistent, the audit
fails honestly; reproduce and review the experiment separately rather than
regenerating output merely to turn a check green.

CI may render architecture assets in an isolated verification context; review
any resulting evidence change as a deliberate generated-artifact update.

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
