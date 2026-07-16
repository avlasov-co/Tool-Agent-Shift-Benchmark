# Phase 5A handoff

## Starting point

Start from the Phase 4B terminal handoff commit on branch
`codex/phase-4b-faults-oversight`; its source parent is Checkpoint 35 commit
`fe451a1`. Checkpoints 27–35 are separate revert boundaries and must remain in
their recorded order. Root `results/`, `figures/`, and generated reports are an
untouched historical Phase 4A evidence snapshot, not Phase 4B scientific
evidence and not source input.

## Authoritative Phase 4B contracts

| Surface | Contract/version at handoff |
| --- | --- |
| Scientific identity | schema `16` |
| Episode/action history | episode record `3`; `action-record-v1` |
| Policy memory | `policy-memory-v1` |
| Tool schema evolution | `tool-schema-registry-v1` |
| Fault channels | `fault-channel-v1` |
| Ordered composition | `fault-composition-v1` |
| Monitor treatments | `monitor-composition-v1` |
| Oversight treatments | `oversight-treatment-v1` |
| Counterfactual scoring | `counterfactual-evaluation-v1`; evaluator `2.0.0` |
| Scenarios | `scenario-manifest-v3`; generator `3.0.0` |
| Scenario families/splits | `scenario-family-v1`; `scenario-split-v1` |
| Scenario coverage | `scenario-coverage-v1` |

Identity-v2 through identity-v15 episode reads remain supported. Complete
scenario-manifest v1 records and hashed v2 records migrate to an explicit
legacy family/split. New writers must not relabel old evidence under current
contracts.

## Invariants to preserve

- Agents and monitors receive only `ObservationContext` and policy-visible
  `ToolResponse`; hidden state, fault provenance, authoritative scenario IDs,
  split labels, and counterfactual labels remain evaluator-only.
- Agent policy, monitor composition, and oversight are independent semantic
  dimensions. No behavior may branch on an agent name.
- Proposed actions remain immutable. An intervention may transform execution
  but cannot overwrite the proposal or its explanation.
- Pure counterfactual scoring may not mutate state, clocks, counters, policy
  memory, manifests, or artifacts and may not call the execution path.
- Fault order remains in identity and provenance unless commutativity is
  explicitly proven.
- Development, validation, and challenge use disjoint reserved namespaces.
  Challenge outcomes may evaluate a frozen policy but may not tune policies or
  scenario distributions.
- Scientific serializers remain explicit; do not use string-fallback JSON
  serialization or wall-clock/process order for experiment identities.

## Compatibility and deprecation

- `monitor_gated` is only a parse-time compatibility alias to a base agent plus
  explicit full-monitor/hard-gate treatments; it is not a runtime agent.
- `monitor_policy: record|gate` is only an input alias for
  `record_only|hard_gate`; new configs use `oversight_modes`.
- `compound_shift` is a deprecated compatibility alias for the historical
  stale → missing → conflict → latency chain; new configs use ordered
  `shift_chains`.
- Contract-v1 external environments remain runnable, but those that do not
  declare `pure_counterfactual_v1` receive explicit unavailable scores.
- Compatibility aliases/readers require a separately versioned migration plan
  before removal.

## Validation baseline

At handoff, the focused invariant matrix passes 350 tests and the full suite
passes 501. Branch coverage is 82.02% over 6,973 statements and 2,116 branches.
The isolated distribution smoke and release verifier each pass all 27 checks or
phases. Lint, format-check, strict mypy, compilation, package build, wheel
inspection, isolated installation, installed `tasb --help`, config validation,
planning, deterministic dual-run comparison, and `git diff --check` pass.

The diagnostic audit has one expected finding: historical checked-in evidence
lacks `results/episodes.jsonl`. Do not regenerate root outputs merely to clear
it. A future evidence release must use an explicit named run/config/seed,
record runtime and provenance, verify artifacts in isolation, and avoid making
publication claims not supported by that executed experiment.

## Known limits

- The first-party agents are deterministic synthetic policies, not frontier
  model integrations.
- Plugin contract v1 cannot guarantee memory snapshots, state cloning, or pure
  counterfactual support unless the plugin declares the richer capability.
- The monitor × oversight × agent × fault cross-product can become large; no
  semantic cell may be deduplicated without a proof and explicit identity.
- Parameterized scenario families provide deterministic distribution coverage,
  not empirical deployment representativeness.
- Identifier redaction and label-invariance tests prevent direct first-party
  shortcuts but cannot prove that a future learned model has never seen
  semantically similar data.

## First Phase 5A decisions

Before implementation, write a Phase 5A plan that chooses and versions the next
scientific surface. The highest-value unresolved decisions are:

1. define explicit external-plugin capability tiers for policy memory, schema
   registry, pure counterfactual scoring, and scenario manifests;
2. define principled experiment-size controls that preserve every requested
   semantic treatment and deterministic identity;
3. decide whether the next evidence release will freeze and evaluate optional
   local/model adapters or first expand long-horizon scenario families; and
4. scope a named, run-directory-only Phase 4B evidence campaign before any
   publication artifact refresh or experimental claim.

Phase 5A must not silently broaden the safety boundary, remove compatibility,
use challenge outcomes for tuning, or rewrite historical root evidence.
