# Phase 4B fault channels, oversight, and scenario plan

## Problem statement

Phase 4A made scenarios, schedules, retries, clocks, and effect severity causal,
but several treatments remain nominal rather than experimental. Memory
corruption is a response hint instead of a stateful channel, schema drift has a
single rename shape, several faults overlap as generic metadata mutations,
monitor ablations are not planned, `monitor_gated` mixes agent and oversight,
blocked proposals are overwritten, evaluators cannot score interventions
without execution, and scenario splits lack explicit family and isolation
contracts. Phase 4B must redesign these surfaces together without leaking
evaluator state or rewriting publication evidence.

## Observed behavior

- The clean Phase 4A baseline is commit `699e877` on
  `codex/phase-4a-experimental-core`; its full suite passes 362 tests.
- `corrupted_memory` writes `memory_hint` into observation metadata and no
  policy-visible memory persists between lifecycle steps.
- `schema_drift` only renames up to two top-level keys and reports
  `v2_drifted`; there is no registry or compatibility classification.
- `monitor_modes` validates but does not expand the plan. `monitor_policy` is a
  single run-level `record`/`gate` value.
- `EpisodeRunner` branches on the agent name `monitor_gated`, reads
  `last_monitor_decision`, and replaces both the action and decision when a gate
  blocks execution.
- `Episode` schema has one final decision/action and one execution result;
  intervention history is available only through unversioned step dictionaries.
- `HiddenStateEvaluator.score` reads the post-execution environment only; it has
  no pure proposed-action scoring boundary.
- Scenario generation is seeded and parameterized, but the manifest has no
  declared family/distribution fields and split membership is only an index
  filter.

## Invariants

- Every fault declares one primary channel and a distinct causal mechanism.
- Ordered non-commutative fault chains retain component order in identity,
  application provenance, intermediate hashes, and artifacts.
- Agent policy, monitor composition, and oversight policy are independent
  semantic dimensions. No runner behavior depends on an agent name.
- Proposed decisions/actions are immutable records. Oversight records an
  intervention and executed action without overwriting proposal history.
- Counterfactual scoring is deterministic and leaves environment state, clocks,
  counters, policy memory, and artifacts byte-equivalent.
- Agents and monitors receive only `ObservationContext` and redacted
  `ToolResponse`; hidden evaluator state and fault/split labels never enter
  policy traces.
- Development, validation, and challenge scenario units are deterministic,
  non-overlapping, and unavailable as first-party policy shortcuts.
- Root results, figures, and generated reports remain untouched.

## Affected modules

- Contracts and execution: `core/types.py`, `core/context.py`,
  `core/contracts.py`, `core/orchestration.py`, `core/episode.py`,
  `core/evaluator.py`, identity, seeding, serialization, checkpoints, and run
  artifacts.
- Treatments: built-in faults, a schema registry, memory channel, monitor
  composition/oversight modules, agents, and environment pure-evaluation
  support.
- Experiment surface: configuration schema and packaged YAML, planner, CLI and
  sweep paths, analysis grouping, metrics, reports, and documentation.
- Scenarios: generator/manifests, split registry, distribution summaries, and
  anti-memorization checks.
- Tests: focused checkpoint regressions plus the full unit, integration,
  distribution, artifact, release, and audit suites.

## Migration strategy

1. Add a versioned policy-memory channel with immutable reads/writes, separate
   evaluator reference state, scheduled deterministic corruption, and recovery
   actions while preserving stateless agent behavior.
2. Add a versioned schema registry and explicit compatible/breaking migration
   families; expose only declared policy-visible schema information.
3. Give every fault a typed channel/mechanism descriptor and unique severity,
   provenance, detection, and adaptation semantics across all environments.
4. Route ordered chains through one generic composer, deprecating the legacy
   special-case compound component and recording intermediate response hashes.
5. Expand named monitor compositions and oversight treatments in planning,
   identity, execution, and analysis.
6. Remove mixed-agent oversight coupling, retain `monitor_gated` only as an
   explicit compatibility alias if needed, and exercise every base agent with
   custom monitors.
7. Introduce an episode/action-record schema with proposed, monitored,
   intervened, executed, and evaluated fields plus compatibility reads.
8. Add clone-based or otherwise provably pure evaluator scoring at every
   intervention point, with separate proposed, executed, and realized labels.
9. Version scenario families and split manifests, generate coverage summaries,
   and enforce split isolation and first-party anti-shortcut tests.

## Compatibility

- Identity-v2 through identity-v7 episodes and scenario-manifest v1/v2 records
  remain readable. New semantic contracts advance identity and record versions
  rather than relabeling historical evidence.
- Legacy `monitor_policy: record|gate` maps deterministically to
  `record_only|hard_gate`. `monitor_gated` may remain a deprecated config alias
  to a base agent plus hard-gate treatment, but it will not be a runtime agent
  special case.
- New episode writers emit the new action-record schema; compatibility readers
  reconstruct a final action record from legacy decision/execution fields where
  practical.
- External plugin contract v1 remains accepted through explicit adapters, but
  richer memory, lifecycle, schema, and counterfactual guarantees apply only to
  first-party or capability-declaring components.

## Tests

- Checkpoint-focused tests cover clean/corrupt memory persistence and recovery;
  every schema family and adaptation outcome; unique fault mechanisms in all
  environments; compound order and intermediate hashes; monitor plan counts and
  composition; agent/oversight independence; proposed/executed history;
  counterfactual purity/equivalence; and split coverage/isolation.
- Every checkpoint runs its focused tests, the full suite, compilation, Ruff
  lint/format, strict mypy, branch coverage, and `git diff --check` before its
  numbered commit.
- Terminal validation additionally runs clean/shift integration, distribution
  smoke, artifact verification, package build and isolated installed-wheel CLI
  smoke, release verification, and non-destructive audit.

## Rollout

- Commit Checkpoints 27 through 35 separately in numerical order on
  `codex/phase-4b-faults-oversight`.
- Update `phase-4b-progress.md` at every checkpoint with schemas, commands,
  outcomes, compatibility effects, and unresolved risk.
- Generate only named run-scoped engineering smoke evidence after source and
  artifact tests pass. Do not regenerate final publication artifacts.

## Rollback

- Each checkpoint is a coherent revert boundary. Reverting does not delete or
  rewrite run bundles, root results, figures, reports, manifests, or user files.
- Compatibility readers and aliases remain until a separately approved removal
  release. Failed validation is fixed forward within the current checkpoint.

## Unresolved risks

- Plugin contract v1 cannot guarantee state snapshots or pure counterfactual
  execution; Phase 4B must state the exact capability boundary.
- Cross-products of monitor and oversight treatments can grow plans quickly;
  deterministic deduplication is allowed only when two semantic cells are
  proven identical and identity remains explicit.
- Schema adaptation and memory recovery policies must not become fault-label or
  split-label shortcuts.
- Challenge outcomes are validation evidence only and will not tune first-party
  policies or scenario distributions.
