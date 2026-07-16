# Tool-Agent Shift Benchmark v0.3.1 stabilization

## Highlights

- Ships a correctly named `tool_agent_shift_benchmark` package with the `tasb`
  console command and module entry point.
- Packages built-in configuration, policy, and report-template resources, and
  verifies both sdist and wheel installations outside the source checkout.
- Adds hash-checked Python locks, locked Node tooling, non-destructive release
  verification, deterministic output comparison, and release artifact checks.
- Establishes Python 3.10--3.14 CI coverage, macOS distribution smoke testing,
  immutable GitHub Action pins, dependency automation/review, CodeQL,
  dependency auditing, and a reproducible SBOM.

## Validation

Run the retained, non-destructive verifier after `make setup`:

```bash
make verify-release
```

Build final artifacts only into a new or empty output directory:

```bash
make release-artifacts RELEASE_OUTPUT=release-artifacts
(cd release-artifacts && sha256sum -c SHA256SUMS)
```

The release process validates package metadata, resource inclusion, installed
distribution behavior, deterministic output content, and final checksums. It
does not publish packages or make new benchmark-performance claims.

The v0.3.1 stabilization validation collected 166 tests before the final
release-artifact and release-verifier checks.

## Safety boundary

This stabilization release remains synthetic and non-operational. It adds no
real API calls, credentials, user data, exploit code, bypass guidance, or
production safety claims.
