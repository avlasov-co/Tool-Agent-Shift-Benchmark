# Release Process

Use this checklist before publishing an archive or GitHub release.

## Required command

```bash
make verify-release
```

The Python verifier copies the checkout into a temporary workspace and runs
compilation, tests, linting, formatting, typed core-contract checks, branch
coverage, config validation, deterministic planning, two fixed-seed small
benchmark runs, analysis, plotting, reports, locked architecture rendering,
package build, and independent sdist/wheel installation smoke tests. Every
phase has a timeout, dedicated log, status, and duration; the final JSON report
and its temporary workspace are retained for review.

It never cleans, regenerates, or overwrites root `results/`, `figures/`, or
reports. The deterministic comparison covers the canonical contents of each
run's `results/`, `figures/`, and `docs/` directories. It excludes only the
run manifest, whose timestamps and run-specific path are explicitly volatile.
If checked-in experiment evidence is missing or inconsistent, investigate it
separately rather than regenerating output merely to turn a check green.

CI may render architecture assets in an isolated verification context; review
any resulting evidence change as a deliberate generated-artifact update.

## Metadata checks

- `pyproject.toml` version must match the latest changelog version.
- `release-notes-vX.Y.Z.md` should exist for the intended release.
- Generated CSV artifacts must have headers and expected rows.
- Generated plots must be non-empty.
- The archive must not include `.pytest_cache`, `__pycache__`, `.venv`, or local junk.

## Archive artifacts

Release archives are the standard sdist and wheel built and inspected by the
verifier. Do not create a release archive by tarring a developer checkout.

To produce the final, non-published release bundle, choose an output directory
that is new or empty (the command refuses to overwrite an existing bundle):

```bash
make release-artifacts RELEASE_OUTPUT=release-artifacts
(cd release-artifacts && sha256sum -c SHA256SUMS)
```

The builder uses a temporary source copy, validates both archives, checks
metadata, creates a reproducible CycloneDX SBOM, then writes checksums only
after those final files exist.
