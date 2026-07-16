# Phase 4B handoff

## Phase 4A outcome

Phase 4A replaces the Phase 3 pseudo-replicated, effectively one-shot core with
deterministic scenario experimental units. A scenario is generated once from a
domain-separated seed, frozen in a tamper-evident manifest, expanded into one
matched clean/shift pair per agent, executed through an explicit state machine,
and observed only through scheduled policy-visible fault channels. Retry,
latency, and fault magnitude are now causal, bounded, versioned, and recorded.

The three built-in environments remain runnable and meet the terminal
conditions: deterministic variation, shared clean/shift scenarios, clean
reference competence, multi-transition trajectories, persistent-fault-safe
requery, simulated-time latency effects, and configured-versus-realized
severity provenance.

## Checkpoint commits

| Checkpoint | Commit | Result |
| --- | --- | --- |
| 18 | `93c4272` | Add deterministic seeded scenarios |
| 19 | `16e0353` | Add versioned scenario manifests |
| 20 | `2a6813b` | Plan matched clean and shifted pairs |
| 21 | `edca169` | Add clean reference competence gates |
| 22 | `37c06fb` | Implement multi-step environment lifecycles |
| 23 | `b7d8e97` | Add typed fault schedules |
| 24 | `d0a2a3a` | Implement bounded tool requery |
| 25 | `c13789b` | Make latency causally advance time |
| 26 | `4c552aa` | Enforce universal fault severity |

Each checkpoint passed its full relevant suite before commit. The detailed
implementation and test record is in [Phase 4A progress](phase-4a-progress.md),
and the design invariants and rollback boundaries are in
[the Phase 4A plan](phase-4a-plan.md) and
[ADR 001](adr-001-scenario-identity-step-lifecycle.md).

## Current contracts

| Concern | Contract/version | Compatibility boundary |
| --- | --- | --- |
| Scientific and planned identity | schema `7` | Identity-v2 through v6 records remain legacy-readable; they are not relabeled as v7. |
| Seed streams | `sha256-domain-separated-63-v1` | Six streams: scenario, agent, fault, oversight, execution, and analysis. |
| Scenario generator | `deterministic_synthetic_scenarios@2.1.0` | Stored manifests, not the current generator, are replay authority. |
| Scenario manifest | `scenario-manifest-v2` | Complete reconstructible v1 records migrate; incomplete historical state fails explicitly. |
| Scenario pair | `scenario-pair-v1` | Pair identity excludes treatment and operational worker/order settings. |
| Reference agents | `reference-agents-v1` | Diagnostic agents are excluded from resilience claims. |
| Environment lifecycle | `environment-state-machine-v2` | First-party environments implement it; plugin-v1 adapters cannot manufacture equivalent semantics. |
| Fault schedule | `fault-schedule-v2` | Legacy schema-v2 timing fields migrate deterministically. |
| Tool requery | `tool-requery-v1` | Per-step requery attempts are distinct from whole-episode infrastructure retries. |
| Causal time | `causal-latency-v1` | First-party clocks use deterministic simulated milliseconds. |
| Fault effects | `fault-effect-v1` | Built-in faults are version `2.0.0`; configured and realized severity are separate. |
| Config | schema `2` | Extended in place with typed schedules, competence gates, and semantic requery settings. |
| External plugins | contract `1` | Still accepted through adapters; richer capabilities are first-party declarations, not v1 guarantees. |

## Migration impact

- New runs materialize scenario manifests before treatment execution and bind
  manifest content hashes, seed records, pair IDs, schedule IDs, lifecycle,
  requery, clock, and effect contracts into identity-v7.
- A shift-only treatment matrix automatically receives its matched clean
  reference. Episode totals can therefore increase; consumers should use the
  separate unique-scenario and unique-pair counts and the
  `within_scenario_deltas.csv` output.
- Packaged experiments now budget six lifecycle steps. A successful valid
  action is no longer implicitly terminal, and incomplete/budget-exhausted
  episodes are retained with explicit stop reasons.
- `requery_attempts` is a semantic per-lifecycle-step budget. It is independent
  of operational `retry_attempts`, which still retries an episode only after an
  orchestration/plugin exception.
- Latency fields are policy-visible and advance the environment clock before a
  decision is executed. Integrations must not treat `latency_ms` as descriptive
  metadata only.
- Severity must be a finite non-boolean number in `[0, 1]`. Invalid values now
  fail validation instead of being clamped or ignored. A zero-severity fault
  preserves the complete policy-visible response while retaining evaluator
  provenance.
- Replay of identity-v3+ episodes requires the exact manifest directory.
  Tampered or mismatched manifests fail before execution. Historical episodes
  without reconstructible manifests remain readable evidence but are explicitly
  non-replayable under the new scenario contract.
- Policy consumers must continue to use only `ObservationContext` and the
  redacted `ToolResponse`. Evaluator traces contain schedules, realized effects,
  and hidden ground truth; policy traces intentionally do not.

## Terminal evidence

The engineering evidence bundle is `runs/phase-4a-validation/`, generated with:

```text
tasb run --config ablations --agent retry --run-name phase-4a-validation --workers 2
tasb analyze --run runs/phase-4a-validation
tasb plot --run runs/phase-4a-validation
tasb report --run runs/phase-4a-validation --html --output runs/phase-4a-validation/reports/analysis_report.html
```

The bundle contains 27 identity-v7 episodes, three manifests, three nine-member
scenario pairs, all three environments, all eight shifted faults plus clean,
24 paired-delta rows, 27 policy/evaluator trace pairs, a passing competence
report, and no orchestration errors. Its run manifest verifies all recorded
artifact checksums.

Clean FileOps and CalendarOps complete four transitions; clean RiskOps
completes five. Across all conditions, trace lengths are
`{1: 11, 2: 3, 3: 4, 4: 7, 5: 2}`; early shifted termination remains explicit.
Every environment's schema-drift episode makes three faulted tool calls, accepts
two requeries, sees the persistent schedule on every attempt, never exposes a
clean response, and safely abstains at the bound.

Latency-spike evidence records exact observation/latency/resulting-clock tuples:

| Environment | Simulated millisecond tuples |
| --- | --- |
| FileOps | `(1000, 538, 1538)`, `(1538, 531, 2069)`, `(2069, 506, 2575)` |
| CalendarOps | `(2000, 504, 2504)`, `(2504, 544, 3048)`, `(3048, 539, 3587)` |
| RiskOps | `(3000, 513, 3513)`, `(3513, 548, 4061)` |

The evidence spans realized effect magnitude `0.0` through `1.0`. Its 27 policy
traces contain no `hidden_ground_truth`, `fault_schedule_provenance`, or fault
label field. A separate one-worker/four-worker canonical payload comparison
produced the same SHA-256 in both modes:
`08bf5df48edce6b1c5ebdb4a9c95111dd2bd86cac39e078f73034aaf84cee4ae`.

Terminal validation passes 362 tests and 80.96% branch coverage over 5,286
statements and 1,496 branches. Lint, format-check, strict typing, compilation,
`git diff --check`, the 27-check sdist/wheel smoke, and all 27 isolated release
verification phases pass. The release verifier also compares 35 files from two
fixed-seed end-to-end pipelines byte-for-byte.

The non-strict audit retains one known diagnostic: historical checked-in root
evidence predates `results/episodes.jsonl`. Regenerating it without a named
evidence release would violate repository provenance rules, so it remains
untouched. All audit code/package/install/CLI checks pass, and the current Phase
4A structured evidence exists in the run-scoped bundle.

## Known experimental limitations

- The validation bundle is deliberately small: one synthetic scenario per
  environment and one reference agent. It demonstrates mechanism behavior and
  reproducibility, not population estimates or publication-scale resilience.
- The benchmark remains synthetic and does not validate behavior against real
  file systems, calendars, market feeds, network latency, credentials, or
  provider-specific failure distributions.
- Plugin contract v1 cannot require lifecycle, requery, simulated clock, or
  realized-effect capabilities. Adapter execution is compatible, but strong
  Phase 4A causal claims apply only to components declaring and implementing
  the richer contracts.
- Historical identity-v2 evidence lacks complete manifests and cannot prove
  matched base-state equivalence retrospectively. Generator migration is
  intentionally conservative rather than inferential.
- Severity magnitude is deterministic and monotonic at the perturbation layer
  where an ordering is scientifically defined. Agent decisions, unsafe-action
  rates, and downstream harm need not vary linearly or monotonically.
- Intermittent schedules are keyed to lifecycle step. Requery occurs within the
  same step, so retries repeatedly traverse that step's schedule; this is not a
  model of arbitrary wall-time-dependent external recovery.
- Built-in tool observations are regenerated deterministically from current
  environment state. They do not model all forms of evolving external service
  state between same-step calls beyond causal clock/hazard behavior.
- Competence thresholds are explicit benchmark governance choices. Passing
  them establishes the configured clean reference baseline, not universal
  competence of an agent family.

## Phase 4B priorities

1. Design plugin contract v2 with mandatory, machine-verifiable capability
   declarations for state lifecycle, requery, clocks, schedules, effects, and
   policy/evaluator separation. Publish an explicit v1 deprecation and migration
   matrix before changing acceptance defaults.
2. Add a campaign planner for many scenario seeds with power-aware sample sizes,
   pair-preserving sharding, resumable storage, and summary uncertainty based on
   independent scenario units rather than episode counts.
3. Add paired statistical estimators and confidence intervals for safety,
   usefulness, coverage, abstention, recovery, retry cost, and realized-effect
   response curves. Keep competence-gate failures and missing pairs in the
   estimand rather than filtering them away.
4. Add property-based lifecycle and schedule model tests covering transition
   invariants, overlapping/recurring schedules, retry bounds, causal clock
   arithmetic, zero-effect equivalence, and manifest round trips across a broad
   seed range.
5. Add sandboxed real-tool adapters only after defining capability isolation,
   resource ownership, evaluator-side provenance, deterministic fixtures, and
   failure containment. Do not weaken the visible-only plugin boundary to gain
   realism.
6. Establish a versioned migration registry and compatibility corpus for config,
   manifest, identity, episode, trace, and plugin records, including negative
   tests for ambiguous historical data.
7. Calibrate synthetic fault schedules and effect ranges against documented
   operational incident classes or controlled adapter measurements, while
   keeping source evidence and inference boundaries explicit.
8. Extend reporting with pair completeness, scenario-level uncertainty,
   competence eligibility, retry/cost distributions, clock hazards, realized
   effect curves, and prominent separation of engineering validation from
   publication claims.

## Safe starting point

Start Phase 4B from the Phase 4A terminal commit on
`codex/phase-4a-experimental-core`. Do not use root `results/`, `figures/`, or
generated reports as new source inputs. Reuse the versioned contracts and the
run-scoped evidence pattern, preserve identity-v2 through v7 readers, and make
the first Phase 4B checkpoint a contract/migration design change before adding
new experimental claims.
