# ADR-001: Scenario identity and step lifecycle

- Status: accepted for Phase 4A
- Date: 2026-07-16

## Context

The Phase 3 planner expands environment, agent, fault, severity, and scenario
index together, then derives a seed from the entire episode cell. Consequently,
nominally corresponding clean and shifted observations are generated from
different seeds. Environments expose a snapshot and a one-shot `execute`; the
runner repeats that shape but stops after the first outcome. Retry and latency
therefore cannot have causal semantics.

## Decision

Scenario generation precedes treatment expansion. A scenario unit is identified
by the versioned generator descriptor, scenario schema version, root scenario
stream, environment descriptor, split, and scenario index. Its immutable
`ScenarioSpec` is canonicalized and content-hashed. Agent, fault, oversight,
workers, selectors, and execution order are excluded from that content.

Every scenario unit expands into treatment episodes. The stable pair identifier
hashes the scenario content reference plus agent initialization semantics. Clean
and shifted members carry the same scenario hash, agent seed, execution seed,
and initial environment state; the treatment descriptor, fault seed, and fault
schedule are the only permitted treatment differences.

Six domain-separated deterministic streams are recorded: scenario generation,
agent behavior, fault behavior, oversight, execution, and analysis. Stream
derivation uses canonical SHA-256 inputs and local `random.Random` instances.
Module-global random state is forbidden.

New scenario manifests use schema v2 and contain structurally distinct public
task description, policy-visible initial state, hidden evaluator state,
constraints, and transition parameters. The manifest content hash excludes the
hash field itself. Replay loads and validates stored manifest bytes and never
calls the current generator.

The rollout lifecycle is:

1. observe or requery through the current scheduled treatment channel;
2. choose a policy decision;
3. apply an environment action or bounded requery request;
4. advance simulated time and environment state;
5. observe the consequence;
6. verify task progress and safety against evaluator-only state;
7. determine terminal, recoverable, or incomplete status;
8. record an immutable `StateTransition` and final outcome.

A successful intermediate action advances the state machine; it does not imply
episode completion. Terminal reasons are explicit and versioned. Tool latency
advances simulated time before execution, so execution-time validation can
invalidate an action that was safe when observed. Requeries occur at the same
step until their budget is exhausted and are charged latency/cost independently;
each request passes through the current schedule and never receives a pristine
response.

## Consequences

- Scientific identity advances to v3 for matched scenario/lifecycle semantics
  and to v4 when exact fault schedules become semantic inputs, then to v5 when
  the bounded per-step requery budget changes policy semantics. Stored earlier
  identity records remain legacy provenance rather than scheduled,
  requery-capable experimental units.
- Generator changes cannot silently change replay meaning because manifests are
  authoritative after planning and their hashes are verified.
- Parallelism and filtering operate on already materialized scenario/treatment
  units and cannot affect scenario bytes or pair membership.
- First-party environments gain explicit lifecycle/state-transition methods.
  Plugin contract v1 is temporarily adapted, but strong Phase 4A claims apply
  only to components declaring the richer capabilities.
- Traces grow and analysis must count unique scenarios separately from episode
  treatments and support within-pair deltas.

## Rejected alternatives

- Deriving a second seed after episode expansion still permits accidental
  treatment leakage and does not make the base unit auditable.
- Regenerating scenarios during replay binds old evidence to current code and
  cannot detect semantic generator drift.
- Treating repeated one-shot episodes as steps provides no state transitions,
  causal timing, or recovery semantics.
- Returning the clean response after a failed shifted observation lets retry
  bypass persistent faults and invalidates resilience measurement.
