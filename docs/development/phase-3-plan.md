# Phase 3 packaging and release-foundation plan

## Problem statement

The Phase 2 implementation is scientifically deterministic, but it is not a
properly isolated Python distribution: its import package is named `src`, its
CLI and tests rely on checkout-relative paths, configs and fixture policies live
outside the wheel, its dependency declarations drift, and its release/CI
controls are insufficiently isolated or pinned. Phase 3 will make the v0.3.1
stabilization candidate installable and verifiable outside its checkout without
rewriting benchmark evidence.

## Observed behavior

- The clean Phase 2 baseline is `codex/phase-2-identity-config`; Phase 3 starts
  on `codex/phase-3-packaging-release`.
- `pyproject.toml` exposes `tool_agent_shift_benchmark.cli:main`, discovers `src*`, sets pytest
  `pythonpath = ["."]`, and has no package-data declaration.
- Built-in configs are checkout-root `configs/*.yaml`; the fixture agent reads
  `fixtures/offline_llm_policy/policy_cases.json` relative to the process CWD.
- Runtime imports, Make targets, audit checks, docs, workflows, and scripts use
  `tool_agent_shift_benchmark.*` or checkout-relative locations. The existing release shell verifier
  invokes source-tree commands; the reproduction script invokes destructive
  cleanup.
- CI installs a short requirements file, uses mutable action tags and
  `npx --yes`; `CITATION.cff` and project metadata still describe v0.1.0 or an
  example repository while the package says v0.3.0.

## Invariants

- Agents and monitors retain the policy-visible-only context boundary, and
  Phase 2 identity/config/serialization versions remain explicit.
- Scientific identity remains deterministic and independent of CWD, process
  order, wall-clock values, or developer checkout files.
- Installed-distribution tests run from an empty external working directory;
  they may not set `PYTHONPATH` or import the source checkout.
- All verification remains non-destructive to the active checkout and its
  user-owned evidence. No verifier invokes the cleanup/reproduction scripts in
  the active tree.
- External tooling is pinned or locked; untrusted PRs never receive secrets or
  privileged release permissions.

## Affected modules

- The real Python package moves from `src/tool_agent_shift_benchmark/` to
  `src/tool_agent_shift_benchmark/tool_agent_shift_benchmark/`; every runtime/test/script/doc import and
  module invocation must follow it.
- Package resources will hold built-in YAML configs and fixture policies.
- `pyproject.toml`, constraints, Makefile, audit/distribution/release scripts,
  CI workflows, Dependabot and security configuration define installation and
  release behavior.
- Citation, changelog, release notes, docs, tests, and archive validation
  define the v0.3.1 release record.

## Migration strategy

1. Create the nested package and update imports, entry points, module execution
   and project test configuration. Do not retain the misleading `src` import
   shim: it would reserve a common generic package name and hide leaks.
2. Move all shipped configs, policies, and templates into package data; provide
   importlib-resources APIs for named configs and explicit external paths.
3. Declare runtime, analysis, docs, development, and release extras solely in
   `pyproject.toml`, backed by generated/reviewed constraints.
4. Build and inspect sdist/wheel, then use a reusable script that installs each
   archive in fresh environments outside the repository and exercises the full
   installed CLI/resource flow.
5. Replace the shell verifier with a Python driver that works in a temporary
   extracted distribution, records every phase and compares deterministic
   canonical artifacts.
6. Add least-privilege, SHA-pinned CI with lock-aware caches, dependency and
   static-analysis checks, SBOM generation, and release artifact validation.
7. Reconcile metadata under one runtime version source and produce v0.3.1
   release notes/checksums only from final wheel/sdist artifacts.

## Compatibility

- `tasb` remains the stable command and `python -m tool_agent_shift_benchmark`
  becomes the module interface. The former `python -m tool_agent_shift_benchmark.*` interface is a
  source-layout implementation detail and is intentionally removed in v0.3.1;
  it is documented as such rather than preserved with a generic package shim.
- External configuration paths remain valid. Named packaged configurations add
  a supported installed-package alternative.
- Existing schema-v1 config migration and v2 identity/artifact compatibility
  remain unchanged. Policy records gain an explicit policy version/hash.

## Tests

- Add focused package-layout, resource, fixture-policy, optional-extra, archive
  inspection, isolated-install, verifier, metadata, and CI-config tests.
- Each checkpoint runs its focused suite and `git diff --check`; the final gate
  runs lint, format check, typing, full branch coverage, compilation, audit,
  build, sdist/wheel smoke, release verification, workflow checks, and commands
  from an empty directory.

## Rollout

- Commit separately after Checkpoints 10, 11, 12, 13, 14, 15/16, and 17. Each
  commit updates `phase-3-progress.md` with commands, outcomes, compatibility
  effects, and risks.
- CI performs lightweight checks per supported Python, with reproducibility and
  documentation rendering once on a designated interpreter; release-only
  artifact assembly stays non-publishing.

## Rollback

- Each checkpoint is a coherent revert boundary. Reverts never delete runs,
  results, figures, reports, or workspace files; temporary verification and
  archive paths are owned by their drivers.
- The branch retains Phase 2 commits unmodified, so rollback can return to the
  prior source package before any v0.3.1 release is published.

## Unresolved risks

- The dependency set must remain compatible with the actual supported Python
  range; CI matrix claims will be limited by resolver evidence.
- Mermaid/Chromium tooling needs a reviewed lock and must not be downloaded via
  an uncontrolled `npx` invocation during CI.
- Existing root evidence remains intentionally absent from version control; no
  release or audit change will manufacture it merely to satisfy a check.
