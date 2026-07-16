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

Checkpoints 27–35 complete; terminal validation and the Phase 5A handoff are
next.

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

### Checkpoint 30 — generic ordered compound shifts

- Added `fault-composition-v1` as the sole runtime application path for active
  fault schedules. Single components, arbitrary ordered chains, overlapping
  schedules, and pairwise compound analysis now all use the same composer.
- Every application records its schedule ID, exact declared order, scheduled
  severity, local component seed, evaluator-response input/output hashes,
  policy-visible output hash, effect hash, and a composition hash. Adjacent
  component hashes form a contiguous chain. Composition provenance remains in
  evaluator attempts and is absent from policy traces.
- Component RNG seeds are derived independently of containing-chain name and
  position while remaining bound to scenario, agent, schedule window/profile,
  component occurrence, step, and attempt. Matched single and compound cells
  therefore share component realizations without sharing mutable RNG state.
- No component order is canonicalized: all registered mechanisms are treated
  as non-commutative until a future contract proves otherwise. Scientific
  identity already preserves chain order and now advances to schema `11` to
  bind `fault-composition-v1`; identity-v2 through identity-v10 reads remain
  supported.
- Replaced `compound_shift` in packaged experiment matrices with an explicit
  stale → missing → conflict → latency `shift_chain`. The historical component
  remains a version `4.0.0`, explicitly deprecated compatibility alias and
  delegates its fixed chain through the generic composer.
- Tests prove schema→missing differs from missing→schema, latency and staleness
  compose causally, component histories reproduce exactly, intermediate hashes
  are contiguous, and matched singles/compounds share the intended seeds and
  first-component outputs. The full suite passed 461 tests. Branch coverage
  passed at 82.11% over 6,172 statements and 1,832 branches. Ruff lint/format,
  strict mypy, compilation, and `git diff --check` passed.

### Checkpoint 31 — monitor ablation treatments

- Added `monitor-composition-v1` with five exact ordered modes: no monitor;
  schema only; schema plus freshness; schema plus freshness plus consistency;
  and the full schema/freshness/consistency/constraint/risk composite.
- `ExperimentSpec` resolves omitted modes to the full composite, rejects
  duplicates and unknown names, and canonicalizes requested mode order.
  Planning crosses every monitor composition with every clean/shift treatment,
  retains one matched scenario pair, preserves agent/fault streams across
  modes, derives a mode-specific oversight stream, and binds the mode into each
  episode ID and planned identity.
- Scientific identity advanced to schema `12` and records the composition
  contract, named modes, and their ordered component descriptors. Episode
  compatibility reads retain identity-v2 through identity-v11 support and
  identity-v12 verifies the serialized monitor treatment against metadata.
- Runtime composition now emits the named mode as the monitor decision identity
  plus its ordered child decisions. `no_monitor` has zero children, risk zero,
  and always allows. Monitor mode and the still-legacy oversight policy are
  stored independently in episode metadata, CSV rows, monitor events, summary
  groups, and matched within-scenario deltas.
- The ordinary sweep path needs no special branching: `run_sweep` calls the
  planner-backed evaluator, so every requested ablation cell executes. Tests
  prove plan counts, canonical order, exact composition, no-monitor behavior,
  unknown/duplicate rejection, seed matching, and analysis separation.
- The full suite passed 471 tests. Branch coverage passed at 82.17% over 6,227
  statements and 1,850 branches. Ruff lint/format, strict mypy, compilation,
  and `git diff --check` passed.

### Checkpoint 32 — independent agent and oversight treatments

- Added `oversight-treatment-v1` with exactly three canonical treatments:
  `no_oversight`, `record_only`, and `hard_gate`. Planning crosses oversight
  with agent, monitor composition, and fault treatments while preserving the
  same scenario pair and agent/fault streams.
- The runner now calls one explicit, stateless oversight function for every
  agent. No oversight does not call the monitor; record-only records the visible
  monitor result without enforcement; hard gate replaces a denied execution
  with abstention. The agent proposal remains unchanged in the existing episode
  decision and step trace pending the versioned action record in Checkpoint 33.
- Removed `MonitorGatedAgent`, its `last_monitor_decision` state, every
  name-based runner branch, and the reporting filter encoded around that agent
  name. First-party matrices now contain five base agents. The deprecated
  `monitor_gated` config name remains a parse-time alias to `naive` plus explicit
  full-monitor/hard-gate cells; it is never registered or instantiated.
- `monitor_policy: record|gate` remains a deprecated input alias to singleton
  `record_only|hard_gate`. New configs use `oversight_modes`, duplicate/unknown
  modes fail at exact paths, and the CLI accepts repeatable `--monitor-mode` and
  `--oversight-mode` overrides for both `run` and `plan`.
- Custom monitor plugins receive the internal `configured_monitor` composition
  identity and run through the same oversight function for every base agent.
  Tests prove all base agents accept a custom monitor, no-oversight skips even a
  monitor that would raise, matched proposals remain equal across treatments,
  and record-only versus hard-gate execution diverges as declared.
- Scientific identity advanced to schema `13`, binds the oversight contract and
  descriptors, and planned episodes bind both monitor and oversight modes.
  Identity-v2 through identity-v12 reads remain supported; identity-v13 checks
  both treatment dimensions during rehydration.
- The full suite passed 476 tests. Branch coverage passed at 82.04% over 6,317
  statements and 1,900 branches. Ruff lint/format, strict mypy, compilation,
  and `git diff --check` passed.

### Checkpoint 33 — immutable proposed-through-evaluated action records

- Added `action-record-v1` and episode record version `3`. Every rollout step
  now stores a separately typed proposed decision, immutable proposed action,
  policy explanation, monitor decision, intervention, executed action,
  execution result, stop reason, and evaluator labels. Action parameters and
  nested evidence are recursively immutable after capture.
- Oversight substitution is represented by authoritative proposed/executed
  action hashes and an explicit intervention type. Hard-gate blocks preserve
  the denied proposal and execute a new abstention action; record-only and
  no-oversight cells retain identical proposal/execution hashes. Agent-authored
  abstention remains distinct from oversight intervention.
- Policy traces receive only the proposal, explanation, monitor, intervention,
  and executed-action identity. Execution results, unsafe labels, hidden ground
  truth, and evaluator transition consequences remain only in the evaluator
  action record and evaluator trace.
- Writers now emit `results/action_records.csv` and
  `results/action_records.jsonl`. Episode JSONL, evaluator traces, monitor
  events, failure cases, checkpoint metadata, run config, run manifests, and
  failure replay all bind or expose the new record fields as appropriate.
  Infrastructure errors carry a non-fabricated failure record rather than a
  synthetic proposal or execution.
- Compatibility readers retain episode identity-v2 through identity-v13 and
  reconstruct one explicitly labeled aggregate action record for legacy
  episode record v2. Scientific identity advances to schema `14` and binds the
  action-record contract plus episode record version; strict v3 reads reject
  missing action histories.
- Tests cover allowed safe actions, blocked unsafe and safe proposals,
  agent-authored abstention, hard-gate transformation, infrastructure failure,
  immutability, policy/evaluator separation, JSONL/CSV exports, checkpoints,
  manifests, failure replay, and legacy reads. The full suite passed 482 tests.
  Branch coverage passed at 82.09% over 6,538 statements and 1,950 branches.
  Ruff lint/format, strict mypy, compilation, and `git diff --check` passed.

### Checkpoint 34 — pure counterfactual intervention scoring

- Added `counterfactual-evaluation-v1` and evaluator version `2.0.0`.
  Scientific identity advances to schema `15` and binds the counterfactual
  contract. Identity-v2 through identity-v14 episode records remain readable.
- Every first-party environment declares `pure_counterfactual_v1` and implements
  a non-executing action-outcome function over hidden ground truth. The
  evaluator calls that function only on an isolated state clone, compares the
  clone before/after, and verifies the original environment state hash remains
  unchanged. It never calls `execute` to score a proposal.
- At every multi-step intervention point, proposed and executed actions are
  scored separately from the same pre-execution state. The actual execution is
  then stored as a third realized-outcome score. Any disagreement between the
  pure executed-action score and the realized safety/success/staleness fields is
  a structured orchestration failure rather than a silently trusted label.
- Evaluated monitor decisions receive exact proposed-action classifications:
  `true_positive`, `false_positive`, `false_negative`, or `true_negative`.
  `no_oversight` is explicitly `not_evaluated`, and external contract-v1
  environments without the capability are explicitly `unavailable` without
  fabricated outcomes. Intervention effects distinguish reduced, increased,
  unchanged, and unavailable risk.
- Counterfactual scores remain evaluator-only. Action-record CSV and JSONL,
  evaluator traces, config, checkpoints, and run manifests expose or bind the
  contract; policy traces contain none of the scores or hidden risk labels.
- Tests prove side-effect freedom and determinism in FileOps, CalendarOps, and
  RiskOps; exact equivalence to actual execution from the same state; rejection
  of a mutating scorer without touching original state; safe and unsafe blocks;
  transformed actions; all four confusion labels; and complete multi-step
  coverage. The full suite passed 494 tests. Branch coverage passed at 82.24%
  over 6,786 statements and 2,054 branches. Ruff lint/format, strict mypy,
  compilation, and `git diff --check` passed.

### Checkpoint 35 — parameterized scenario families and isolated splits

- Added `scenario-family-v1`, `scenario-split-v1`, and
  `scenario-coverage-v1`; scenario manifests advance to schema `3` and
  `scenario-manifest-v3`. Complete v1 and hashed v2 manifests migrate to a
  declared legacy family/split, while malformed historical records still fail
  explicitly.
- FileOps now samples parameterized resource-lifecycle tasks, hazards,
  protected object types, constraints, and deadlines. CalendarOps samples
  attendee count, duration, priority, privacy, time-zone/working-hour
  constraints, scheduling deadlines, and late conflicts. RiskOps samples
  balanced, defensive, and growth-constrained review modes alongside market
  transitions, execution-time limits, and timed hidden hazards.
- Omitted split declarations create deterministic `development`, `validation`,
  and `challenge` splits from reserved, disjoint one-million-index namespaces
  beginning at 0, 1,000,000, and 2,000,000. Explicit custom split indices must
  be non-empty, unique, and globally non-overlapping. The selected split and
  every descriptor are bound into scientific identity schema `16`.
- Policy-visible responses replace the authoritative scenario identifier with
  `policy_visible_scenario`; `ObservationContext` contains neither scenario nor
  split identity, and response metadata redaction removes split/family labels.
  First-party-agent tests prove invariant decisions under label substitution
  and reject source references to scenario IDs, split IDs, challenge labels, or
  fixed behavior seeds.
- Run outputs now include `results/scenario_coverage.json` and
  `results/scenario_coverage.csv`. Config, checkpoints, and run manifests bind
  their coverage hash and all scenario contracts. Coverage summaries are
  deterministic under input reordering.
- The representative 108-scenario integrity fixture contains 36 scenarios per
  environment/family and 36 per development/validation/challenge split. It
  covers 17 task types, 9 hazard types, 8 protected-object types, 18 constraint
  dimensions, 9 temporal behaviors, and all 7 applicable first-party fault
  channels. Challenge outcomes were used only for structural integrity and
  label-invariance tests, never to select or tune agent behavior.
- Split/family/manifests and compatibility tests joined the full suite, which
  passed all 501 tests. Branch coverage passed at 82.02% over 6,973 statements
  and 2,116 branches. Ruff lint/format, strict mypy, compilation, and
  `git diff --check` passed; audit, distribution smoke, and artifact
  verification are recorded after the terminal matrix.

## Contract and schema ledger

| Concern | Starting version | Phase 4B version |
| --- | --- | --- |
| Scientific identity | 7 | 16 |
| Episode record | legacy aggregate | v3 plus `action-record-v1` |
| Policy memory | metadata hint only | `policy-memory-v1` |
| Tool schema registry | none | `tool-schema-registry-v1` |
| Fault channel/mechanism | implicit | `fault-channel-v1` |
| Fault composition | schedules plus special case | `fault-composition-v1` |
| Monitor composition | declared names only | `monitor-composition-v1` |
| Oversight treatment | `record` / `gate` | `oversight-treatment-v1` |
| Counterfactual evaluator | none | `counterfactual-evaluation-v1` |
| Scenario manifest/families | manifest v2 | `scenario-manifest-v3` plus `scenario-family-v1` |
| Scenario splits | implicit repeated indices | `scenario-split-v1` with disjoint reserved namespaces |
| Scenario coverage | none | `scenario-coverage-v1` JSON and CSV |

## Known baseline limitations

- The deterministic first-party agents remain synthetic benchmark policies, not
  frontier model integrations.
- Contract-v1 external environments without `pure_counterfactual_v1` receive
  explicit unavailable counterfactual scores.
- Scenario families are parameterized synthetic distributions; this checkpoint
  establishes isolation and coverage contracts but does not claim empirical
  deployment representativeness.
- Split isolation prevents identifier-based shortcuts but cannot prove that a
  future learned policy has not memorized semantically similar external data.

## Phase 5A handoff

Pending completion of Checkpoints 27–35 and the terminal validation matrix.
