# Phase 4A experimental-core redesign plan

## Problem statement

Phase 3 made the benchmark reproducibly installable, but its experimental core
still pseudo-replicates scenarios across agent/treatment cells, stores no
generator-independent scenario manifests, terminates nominal multi-step runs on
the first action, treats retry as episode restart or immediate abstention, does
not apply latency to simulated time, and lets several faults ignore severity.
Phase 4A must replace those behaviors while preserving the policy/evaluator
boundary and keeping FileOps, CalendarOps, and RiskOps runnable at every
checkpoint.

## Observed behavior

- On clean Phase 3 commit `ffa7f74`, the planner derives `scenario_seed` from
  run, agent, shift, and severity, and leaves `scenario_pair_id` unset. Thus a
  clean and shifted episode do not share one base experimental unit.
- Environment `reset` methods mostly derive state from `scenario_index`; the
  supplied seed does not create meaningful variation.
- Existing `results/multistep_traces.jsonl` and `runs/smoke` traces contain one
  step per episode. The runner breaks after any successful environment action,
  and environment execution does not advance a meaningful task state machine.
- `RetryAgent` abstains when required fields are absent. Scheduler retry reruns
  an entire failed episode; it is not a policy-visible tool requery.
- `latency_ms` is descriptive only. It neither advances the environment clock
  nor changes execution-time validity. `RiskMonitor` looks for latency on an
  observation object that has no such field.
- Missing-field, schema, conflict, constraint, and corrupted-memory faults do
  not consistently use configured severity; `BaseFault` clamps unsupported
  values instead of rejecting them.
- The Phase 3 baseline full suite passes (166 tests).

## Invariants

- A base scenario is generated only from versioned scenario semantics, the
  root scenario seed stream, environment, and scenario index. Agent, treatment,
  oversight, worker count, filtering, and execution order cannot alter it.
- Clean and shifted treatments reference the same immutable scenario content
  hash and initialize the same agent/execution streams. Only the declared
  treatment stream and schedule may differ.
- Agents, monitors, policy traces, and plugin APIs receive only
  `ObservationContext` plus the current policy-visible `ToolResponse`; manifests
  and hidden evaluator state remain evaluator-side.
- Multi-step episodes contain meaningful immutable transitions and explicit
  terminal or incomplete stop reasons. Failures and budget exhaustion remain
  serialized rather than disappearing.
- Requeries traverse the same scheduled fault channel at the current simulated
  time. No retry path retains or returns a pristine response.
- Configured severity and deterministic realized effect are separate recorded
  values. Unsupported severities fail before execution.
- Scientific identities use canonical serializers and versioned contracts;
  no identity is derived from wall time, global RNG state, thread order, or
  artifact paths.
- Verification remains non-destructive to user-owned runs and root evidence.

## Affected modules

- Core contracts and runtime: `core/identity.py`, `core/types.py`,
  `core/contracts.py`, `core/context.py`, `core/orchestration.py`,
  `core/episode.py`, `core/run_artifacts.py`, plus new scenario, seed, schedule,
  and lifecycle modules.
- Components: all three environments, tools, reference/diagnostic agents,
  monitors, and every fault implementation.
- Planning/config/artifacts: `core/config_schema.py`, packaged YAML configs,
  `run_eval.py`, CLI/run bundle replay, checkpoints, and scenario manifests.
- Analysis/reporting: aggregation, paired deltas, unique-scenario counts,
  competence-gate metadata, severity/effect summaries, and trace exports.
- Tests/docs: deterministic generation and process/worker tests, manifest
  migration/tamper tests, pairing and clean golden tests, lifecycle/retry/
  schedule/latency/severity regressions, this plan/progress record, and the
  scenario/lifecycle ADR.

## Migration strategy

1. Introduce domain-separated deterministic seed streams and seed-dependent
   scenario generators without changing the installed plugin interface.
2. Freeze generator output into scenario schema v2 manifests. New runs write
   manifests before execution; replay reads manifests directly and verifies
   hashes. A typed v1-to-v2 migration handles reconstructible legacy scenario
   records, while legacy runs without sufficient state remain readable but are
   explicitly non-replayable as manifests.
3. Expand scenario units into matched clean/shift episodes, assign stable pair
   IDs, and carry scenario references through filters, workers, checkpoint,
   resume, and replay.
4. Classify diagnostic versus reference agents, repair clean action scaffolding,
   and add environment-specific clean competence gates and a preflight report.
5. Replace one-shot execution with environment state machines and an explicit
   observe/query/apply/advance/consequence/verify/terminal lifecycle.
6. Replace matrix-derived always-on faults with typed persistent, transient,
   intermittent, and late-onset schedules evaluated per tool call and step.
7. Add an agent requery decision and bounded attempt loop. Each attempt obtains
   a new clean environment tool response internally, applies the same current
   fault schedule, then exposes only the shifted/redacted result.
8. Advance simulated time by response latency before action execution and make
   all environments revalidate time-sensitive state at execution time.
9. Enforce a universal `[0, 1]` severity contract and record deterministic
   effect summaries and configured/realized magnitude for every application.

## Compatibility

- Configuration remains schema v2, extended with typed schedule and competence
  settings. Old schema-v2 schedules migrate deterministically from
  `start_step/end_step/cadence` to the richer schedule representation.
- Identity advances from v2 to v3 when scenario content, pair identity, six
  seed streams, and lifecycle meaning become scientific inputs, then to v4
  when exact fault schedules become semantic inputs, and to v5 when the bounded
  per-step requery budget becomes part of policy semantics, then to v6 when the
  causal millisecond clock becomes execution semantics, and to v7 when the
  universal configured-versus-realized fault effect contract becomes semantic.
  Stored earlier identity episodes remain readable as legacy provenance but are
  not silently relabeled as scheduled/requery/causal-clock/effect-v7 units.
- Scenario generator version `2.1.0` introduces generated millisecond deadlines
  and timed hazards. Existing scenario manifests retain their recorded
  generator version and remain the replay authority; they are not regenerated
  into the new timing semantics.
- Scenario manifests start at schema v2 because historical `v1` was a semantic
  label, not a complete reconstructible manifest contract. Explicit migration
  rules are recorded in code and documentation.
- Plugin contract v1 remains accepted through adapters during Phase 4A; new
  first-party environment lifecycle and agent requery capabilities are declared
  in descriptors. A future Phase 4B may make the richer interfaces mandatory.
- `tasb`, packaged config names, existing selectors, and installed-wheel usage
  remain available. Replay by episode ID additionally requires its scenario
  manifest for identity-v3 runs.

## Tests

- Run focused tests continuously and the full suite before each checkpoint
  commit. Each checkpoint also runs lint, formatting, focused strict typing,
  compilation, and `git diff --check`; diagnostic audit findings are recorded.
- Cross-process and worker-count tests compare canonical scenario bytes, plan
  identity, pair membership, and final episode bytes.
- Lifecycle tests cover trajectories longer than one action, intermediate and
  late failure, recovery, abstention, deterministic budget exhaustion, and
  incomplete episodes.
- Schedule/retry/latency tests cover overlap, boundaries, persistent-fault
  non-bypass, attempt provenance and cost, clock composition, stale deadlines,
  and pristine/hidden-state exclusion.
- Severity tests exercise 0.0, low, medium, and 1.0 for every fault and check
  monotonic effect magnitude where the perturbation admits an ordering.
- Final verification adds a small matched all-environment evidence run, trace
  and manifest inspection, coverage, audit, build, isolated wheel smoke,
  release/distribution verification where available, and generated-artifact
  inspection.

## Rollout

- Commit Checkpoints 18 through 26 independently, in order, updating
  `phase-4a-progress.md` with exact evidence before each commit.
- Keep compatibility adapters and the three built-in environments green at
  each boundary. Do not combine checkpoint commits or regenerate root evidence
  to mask a failure.
- The final handoff records contract versions, migration impact, deterministic
  and trajectory evidence, known experimental limits, and Phase 4B work.

## Rollback

- Each numbered checkpoint is a coherent revert boundary. Scenario manifests
  and run bundles are append-only evidence and are never deleted during
  rollback.
- Identity-v2 and legacy episode readers remain available, so reverting a later
  lifecycle/schedule checkpoint cannot require rewriting historical artifacts.
- If a checkpoint gate fails, fix forward within that uncommitted checkpoint or
  revert only its commit; never reset or clean user-owned outputs.

## Unresolved risks

- External v1 plugins cannot express the full lifecycle or requery contract;
  adapters can preserve execution but cannot manufacture strong multi-step
  claims for those plugins.
- Historical runs lack complete scenario manifests and therefore cannot prove
  matched base-state equivalence retrospectively.
- Competence thresholds are benchmark contract choices, not empirical model
  claims; Phase 4A will make them explicit and testable but not universal.
- Full release verification is intentionally expensive and will run at the
  terminal gate rather than before every intermediate commit.
