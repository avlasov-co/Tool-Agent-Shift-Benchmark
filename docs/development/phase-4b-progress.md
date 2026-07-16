# Phase 4B progress

## Baseline

- Started from clean Phase 4A terminal commit `699e877` on branch
  `codex/phase-4a-experimental-core`.
- Read `AGENTS.md`, `PLANS.md`, all Phase 1–4A plans/progress records, the Phase
  4B handoff, ADR 001, serialization policy, contracts, identity, planning,
  orchestration, agents, monitors, evaluator, faults, environments, action
  records, ablation configuration, reporting/analysis, and regression tests.
- Baseline `make test PYTHON=.venv/bin/python` passed all 362 tests after byte
  compilation.
- Created branch `codex/phase-4b-faults-oversight`. Root generated evidence was
  not read as a source and will not be regenerated for this phase.

## Current checkpoint

Checkpoints 27–29 complete; Checkpoint 30 — generic ordered compound shifts (in
progress).

## Checkpoint evidence

### Checkpoint 27 — real policy-visible memory channel

- Added immutable `policy-memory-v1` records for policy views, entries, writes,
  operations, corruption requests, corruption evidence, and evaluator-only
  pristine-reference hashes. The episode-local `PolicyMemoryChannel` never
  returns its pristine mapping to policy code.
- Scientific identity advanced to schema `8`; step semantics now bind
  `policy-memory-v1`, `RetryAgent` is version `3.0.0`, and the real memory fault
  is version `3.0.0`. Identity-v2 through identity-v7 episode reads remain
  supported.
- Implemented deletion, substitution, staleness, source confusion, and
  confidence corruption. Schedule activation selects whether the memory channel
  is touched; scheduled severity deterministically selects one through five
  corruption families, with fault-stream-local RNG selecting targets/order.
- `corrupted_memory` no longer manufactures `memory_hint` observation metadata.
  It declares the `policy_memory` channel, leaves current tool observations
  intact, and records evaluator-only effect provenance.
- Agents opt in with `stateful_memory`. Stateless agents receive `memory=None`;
  clean and corrupted-memory action/execution trajectories are equal for the
  stateless baseline. `RetryAgent` now validates prior entries, overwrites from
  a trustworthy current response, ignores suspicious memory when safe,
  requeries when both memory and the current observation are suspect, and
  abstains after the bounded requery path.
- Policy traces contain only the view actually read plus declared writes and
  operations. Evaluator attempts separately retain corruption type, target,
  before/after hashes, the policy-visible before/after values, and the pristine
  reference hash. Tests prove those evaluator fields and hidden ground truth do
  not enter policy traces.
- Focused memory/agent/requery/severity/platform suite passed 178 tests. The full
  suite passed 374 tests. Branch coverage passed at 81.30% over 5,496 statements
  and 1,558 branches. Ruff lint/format, strict mypy, compilation, and
  `git diff --check` passed.

### Checkpoint 28 — versioned schema-drift families

- Added `tool-schema-registry-v1` with immutable source/target schemas, typed
  fields, typed deltas, compatibility classes, stable schema/delta hashes, and
  a deterministic reverse-adaptation result. Machine-readable schema
  information is exposed only as declared `schema_info`; it contains schema
  structure and migration operations, never hidden environment values or fault
  labels.
- Implemented all seven families in FileOps, CalendarOps, and RiskOps: additive
  compatible fields, type widening, alias/rename, nested moves, unit changes,
  required-field removal, and breaking type changes. Severity monotonically
  selects one through seven change families; compatibility progresses from
  `compatible` through `requires_adaptation` to `breaking`.
- Added exact reverse migrations for compatible/repairable deltas. Numeric unit
  and widening repairs reject booleans, strings, fractional integer values, and
  tampered delta hashes rather than coercing them silently. Required removal and
  breaking type changes explicitly return failed adaptation.
- `ValidateThenActAgent` and `RetryAgent` consume only validated registry
  deltas. They adapt compatible changes, explicitly repair aliases/nesting/
  units, and fail closed on unsupported or tampered migrations. `SchemaMonitor`
  allows valid compatible/repairable declarations and blocks breaking or
  unknown drift.
- Scientific identity advanced to schema `9` and binds
  `tool-schema-registry-v1`. Schema drift is version `3.0.0`,
  `ValidateThenActAgent` is `2.0.0`, `RetryAgent` is `4.0.0`, and the composite
  monitor is `2.0.0`; identity-v2 through identity-v8 records remain readable.
- Focused schema/agent/monitor/severity/requery tests passed 209 tests. The full
  suite passed 418 tests. Branch coverage passed at 82.09% over 5,873 statements
  and 1,736 branches. Ruff lint/format, strict mypy, compilation, and
  `git diff --check` passed.

### Checkpoint 29 — distinct fault mechanisms

- Added `fault-channel-v1` and an immutable descriptor for fault name, primary
  channel, causal mechanism, unique severity meaning, schedule behavior,
  detection path, and adaptation path. Every built-in fault records these fields
  in evaluator-only effect provenance, and schedule traces bind the ordered
  component channel descriptors.
- `missing_field` now omits only scenario/task-relevant leaf paths from an
  otherwise valid payload and preserves the declared schema version and
  enclosing encoding. Policy validation now checks nested FileOps, CalendarOps,
  and RiskOps requirements, so low-severity omissions have a real detection
  path without fault labels.
- `conflicting_tool_output` now presents two named snapshots with distinct
  source IDs, content-derived snapshot IDs, explicit disagreement paths, and
  asymmetric reliability. Consistency and risk monitors consume this visible
  evidence shape rather than a generic metadata marker.
- `constraint_shift` now creates a temporal visible constraint revision tied to
  lifecycle phase and simulated time. Evaluator provenance separates visible
  before/after constraints, changed keys, and a hash-only pristine constraint
  reference; policy context receives only the changed visible revision.
  Environment ground truth remains unchanged.
- Unsafe stale-data outcomes no longer automatically set
  `constraint_violation=true`; the three environments classify stale-only harm
  separately from actual constraint violations.
- Scientific identity advanced to schema `10`, binds `fault-channel-v1`, and
  built-in fault components are version `3.0.0`. Identity-v2 through
  identity-v9 episode reads remain supported.
- Focused fault/environment/agent/monitor/severity/requery tests passed 220
  tests. The full suite passed 456 tests. Branch coverage passed at 82.18% over
  6,078 statements and 1,806 branches. Ruff lint/format, strict mypy,
  compilation, and `git diff --check` passed.

## Contract and schema ledger

| Concern | Starting version | Phase 4B version |
| --- | --- | --- |
| Scientific identity | 7 | 10 |
| Episode record | legacy aggregate | pending |
| Policy memory | metadata hint only | `policy-memory-v1` |
| Tool schema registry | none | `tool-schema-registry-v1` |
| Fault channel/mechanism | implicit | `fault-channel-v1` |
| Fault composition | schedules plus special case | pending |
| Monitor composition | declared names only | pending |
| Oversight treatment | `record` / `gate` | pending |
| Counterfactual evaluator | none | pending |
| Scenario manifest/families | manifest v2 | pending |

## Known baseline limitations

- `corrupted_memory` is not stateful.
- Schema drift has one rename mechanism.
- Monitor modes are not experimental treatments.
- `monitor_gated` couples agent and oversight and can overwrite proposals.
- No pure intervention scorer exists.
- Scenario manifests do not declare family coverage or isolated split
  namespaces.

## Phase 5A handoff

Pending completion of Checkpoints 27–35 and the terminal validation matrix.
