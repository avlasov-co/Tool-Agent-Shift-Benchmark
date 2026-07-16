# Phase 5A progress

## Baseline

- Started from clean Phase 4B terminal commit `a59629f` on
  `codex/phase-4b-faults-oversight` and created
  `codex/phase-5a-plugin-security`.
- Read `AGENTS.md`, `PLANS.md`, every prior phase progress record, the Phase 4B
  plan/handoff and Phase 5A handoff, public contracts/base classes, plugin
  registration/discovery and CLI entry points, environment adapters, shift
  invocation/composition, artifact descriptors/manifests, boundary and threat
  documentation, and related contract/context/environment/agent/monitor tests.
- Baseline `make test PYTHON=.venv/bin/python` passed all 501 tests after byte
  compilation.
- The observed v1 gaps are eager entry-point import, partial one-method
  validation, descriptor override after weaker registration, environment-name
  dispatch in `ObservationContext`, full environment access from shifts,
  mutable nested policy records, and unbounded in-process external execution.

## Current checkpoint

Checkpoint 36 — plugin contract v2 — complete. Checkpoint 37 — generic
environment policy adapters — in progress.

## Checkpoint evidence

Evidence, contract/schema changes, compatibility effects, test results, and
commit identifiers will be recorded here before every checkpoint commit.

### Checkpoint 36 — plugin contract v2

- Added `plugin-descriptor-v2` and made public plugin contract version `2` the
  only accepted new-runtime contract. Descriptors bind plugin kind, name,
  implementation version, contract version, stable `module:qualname`
  implementation identifier, canonical configuration schema/hash, trust level,
  capabilities, isolation mode, and canonical metadata.
- Added `plugin-configuration-schema-v1` validation. Missing or extra schema
  fields, undeclared required properties, duplicate capabilities, mismatched
  hashes, malformed identifiers, unsupported contracts, and inconsistent
  trust/isolation declarations fail before registration.
- Inventoried and encoded every current runner-used method for environments,
  agents, shifts, monitors, evaluators, and reporters. Environment policy
  adapters have a separate public protocol ready for Checkpoint 37.
- Built-in, explicit programmatic, compatibility-registry, and currently eager
  entry-point paths call the same factory validator. Factories must match the
  descriptor name/implementation/schema/capabilities, implement every required
  method, and be concrete. Duplicate registration never overwrites the first
  plugin.
- Registered `HiddenStateEvaluator` as a first-class evaluator plugin. Planner
  validation and runtime construction now use the catalog instead of a
  hard-coded evaluator descriptor/class. Configured evaluator versions must
  match the selected v2 descriptor.
- Scientific identity advanced from schema 16 to 17. Component identities now
  bind implementation identifier, configuration hash, trust, capabilities, and
  isolation mode while identity-v2 through identity-v16 reads remain accepted.
  Run manifests default to contract `2` and full catalog serialization records
  every v2 descriptor field.
- Added `plugin-v1-to-v2-migration.md`. Contract v1 is not silently relabeled;
  historical records remain readable and plugin packages receive explicit
  descriptor/interface/entry-point/trust migration instructions.
- Contract-focused tests pass 75 cases. The full suite passes 508 tests after
  byte compilation. Branch coverage passes at 82.01% over 7,137 statements and
  2,172 branches. Ruff lint/format, strict mypy, and `git diff --check` pass.

## Terminal validation

Pending Checkpoints 36–41.

## Phase 5B handoff

Pending terminal validation and final security review.
