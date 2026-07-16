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

Checkpoints 36–39 are complete. Checkpoint 40 — lazy plugin discovery — is
next.

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

### Checkpoint 37 — generic environment policy adapters

- Added `environment-policy-adapter-v1` with exactly five declared safe
  capability groups: action schema, visible candidate extraction, visible
  observation/action validation, safe abstention, and recommendation helpers.
  Adapter snapshots contain only environment name, required visible fields,
  visible constraints, public task metadata, action schema, and capabilities;
  validation rejects environment/evaluator/execution handles.
- Moved every file/calendar/risk recommendation and visible-validation branch
  out of `ObservationContext` into first-party environment-provided adapters.
  The context now delegates generically and the episode runner constructs it
  from an adapter rather than passing or introspecting an environment object.
  Agents and monitors required no environment-specific changes.
- Added explicit first-party action schemas and visible-candidate extractors.
  Policy traces record the safe adapter contract/schema used for each decision.
- Added a `synthetic_inventory` test plugin environment. It plans, generates a
  scenario, produces an adapter with a custom schema marker, runs the ordinary
  naive agent, and records the adapter without adding its name anywhere in
  central context, agent, or runner dispatch.
- First-party environment descriptors advance to version `2.0.0` and declare
  the adapter capability. Scientific identity advances from schema 17 to 18
  and binds `environment-policy-adapter-v1`; identity-v2 through identity-v17
  reads remain accepted.
- Adapter/context/environment focused tests pass 29 cases. The full suite
  passes 511 tests after compilation. Branch coverage passes at 81.91% over
  7,296 statements and 2,200 branches. Ruff lint/format, strict mypy, and
  `git diff --check` pass.

### Checkpoint 38 — sanitized shift context

- Replaced the historical `ShiftPlugin.apply(response, environment, rng)`
  surface with `apply(response, context)`. The new immutable
  `shift-context-v1` contains only the step/attempt, public scenario metadata,
  visible schema, declared timing, a component-local deterministic RNG seed,
  fault-schedule data, and explicitly allowed channel metadata.
- The runner constructs the context from public scenario data and the visible
  response. Shift implementations no longer receive environment, evaluator,
  execution, filesystem, network, credential, protected-ground-truth, or
  authoritative scenario/split handles. Fault composition derives a fresh
  immutable context for each component seed.
- Updated every first-party fault to the context interface. Fault descriptors
  advance to version `4.0.0` (deprecated compound alias `5.0.0`) and declare
  `shift-context-v1` as a capability. Direct fault tests use the same safe
  context shape as orchestration.
- Scientific identity advances from schema 18 to 19 and binds
  `shift-context-v1` in step semantics; identity-v2 through identity-v18 reads
  remain accepted. Schedule provenance also records the context schema on
  every attempted application.
- Added a malicious runner-integrated shift that probes all historically
  exposed authority, verifies absent hidden/environment/file/network handles,
  and fails to mutate the context. Additional tests prove nested context data
  is immutable, RNG creation is deterministic and local, canonical
  serialization is stable, and the serialized schema contains only its nine
  documented fields.
- Context/shift-focused tests pass 270 cases. The full suite passes 515 tests
  after compilation. Branch coverage passes at 81.96% over 7,352 statements
  and 2,218 branches. Ruff lint/format, strict mypy, and `git diff --check`
  pass.

### Checkpoint 39 — deep immutability

- Added `policy-data-immutability-v1` and a single canonical defensive-freeze
  utility. It first canonicalizes into an alias-free copy, then recursively
  exposes mappings as read-only mapping proxies and sequences as tuples.
  Canonical serialization returns fresh ordinary dictionaries and lists.
- Observation data/constraints/metadata, response metadata/errors, action
  parameters, agent and monitor reasons/metadata, execution records, policy
  memory values, adapter schemas/constraints/task metadata/candidates, policy
  traces, tool-attempt provenance, action records, shift contexts, and plugin
  descriptor schema/metadata now freeze in their constructors. Frozen
  dataclasses no longer retain mutable nested aliases.
- Updated agents and monitors to consume the documented `Mapping`/tuple
  surface. Policy adapter result values are re-frozen by `ObservationContext`,
  providing a defensive boundary even for a custom adapter implementation.
  Records containing immutable mappings serialize through canonicalization
  instead of `dataclasses.asdict`, which cannot safely copy mapping proxies.
- Scientific identity advances from schema 19 to 20 and binds
  `policy-data-immutability-v1` in step semantics; identity-v2 through
  identity-v19 reads remain accepted.
- Added four adversarial cases covering original-alias mutation, nested mapping
  mutation, list mutation, schema/constraint/candidate mutation, action and
  memory mutation, a malicious agent followed by a verifying monitor across
  two episodes, and a malicious monitor followed by a second monitor. Every
  mutation is denied and later plugins/episodes retain their original values.
  The tests also prove immutable runtime values serialize deterministically to
  ordinary JSON shapes.
- The full suite passes 519 tests after compilation. Branch coverage passes at
  82.05% over 7,428 statements and 2,228 branches. Ruff lint/format, strict
  mypy, and `git diff --check` pass.

## Terminal validation

Pending Checkpoints 36–41.

## Phase 5B handoff

Pending terminal validation and final security review.
