# Tool-Agent Shift Benchmark v0.4.0 evidence release

## Highlights

- Every headline rate now has a versioned definition, numerator, denominator,
  inclusion rule, missing-data rule, and visible accounting for incomplete or
  failed episodes.
- Statistical inference uses unique scenario manifests as independent units,
  matched clean/shift effects where available, deterministic clustered
  bootstrap intervals, and explicit refusal when evidence is insufficient.
- Monitor detector labels come from counterfactual proposed-action risk.
  Realized interventions and executed outcomes are evaluated separately.
- Reports are generated only from complete verified bundles and bind claims to
  the source manifest, checksums, metric schema, sample counts, treatments,
  clean competence, and uncertainty method.
- Four packaged suite contracts provide smoke, standard regression, research,
  and held-out challenge plans. Challenge outcomes are sealed from development
  and tuning.

## Compatibility

Configuration schema v2 remains the supported input. The release deliberately
changes scientific artifact and metric semantics; consumers should follow
[`docs/migrations/v0.4.0.md`](docs/migrations/v0.4.0.md) rather than treating
legacy aggregate column names as equivalent. Python 3.10 through 3.14 remains
supported.

## Validation and scope

The retained local release rehearsals build from the sdist, install into clean
environments, execute and verify the smoke and standard suites twice, compare
canonical scientific outputs, inspect rendered reports and plots, and generate
checksums plus a CycloneDX SBOM. Exact logs and hashes are recorded in the
Phase 6 progress document after the rehearsals finish.

This release evaluates deterministic synthetic environments and transparent
reference agents. It does not establish production safety or frontier-model
capability, and it makes no claim about held-out challenge outcomes.
