# Phase 4A progress

## Baseline

- Started from clean Phase 3 commit `ffa7f74` on
  `codex/phase-3-packaging-release` and created
  `codex/phase-4a-experimental-core`.
- Read `AGENTS.md`, `PLANS.md`, all Phase 1-3 plans and progress records, the
  planner, runner, environment/evaluator contracts, built-in environments,
  agents, monitors, faults, packaged configurations, current traces, and the
  regression suite.
- Baseline `make test PYTHON=.venv/bin/python` passes 166 tests.
- Existing trace inspection proves nominal two-step configurations stop after
  one successful, unsafe, or abstaining action. Scenario seeds include agent
  and treatment identity; regular planner episodes have no pair ID; retry does
  not requery; latency does not advance time; and multiple faults ignore
  severity.

## Current checkpoint

Checkpoint 26 — universal severity contract — complete; preparing final validation and Phase 4B handoff.

## Checkpoint evidence

Evidence will be appended before every numbered checkpoint commit. Failed and
diagnostic checks remain visible here.

### Checkpoint 18 — seed-dependent scenarios

- Added the `sha256-domain-separated-63-v1` seed contract with localized
  scenario-generation, agent-behavior, fault-behavior, oversight, execution,
  and analysis streams. Every stream is recorded on the plan and episode; only
  fault behavior includes the treatment descriptor.
- The scenario-generation seed derives from root seed, environment, scenario
  index, generator name/version, and scenario schema only. Tests prove agent,
  fault, severity, worker count, and execution mode do not change it.
- FileOps now varies task, task target, tree entries, protected resources,
  distractors, permissions, archive constraints, and latent hazards using only
  a local `Random` instance.
- CalendarOps now varies participants, timezone, working hours, availability,
  conflicts, event properties, scheduling constraints, and late temporal
  hazards using only its scenario stream.
- RiskOps now varies price/volatility/liquidity state, exposure and risk limits,
  transitions, hidden hazards, adjustment constraints, and intervention
  thresholds using only its scenario stream.
- Scenario generator identity is now
  `deterministic_synthetic_scenarios@2.0.0` and is recorded with seed streams in
  episode metadata. Module-global RNG state is not used.
- Focused seeded-scenario/environment/identity tests passed (28 tests). The
  full suite passed (170 tests). Compilation and strict mypy passed.
- The first lint/format gate reported one import-order issue and two files
  needing Ruff formatting; the mechanical formatter/import fix was applied and
  the gates were rerun before commit.

### Checkpoint 19 — scenario manifests

- Added immutable scenario-manifest schema `2` and contract
  `scenario-manifest-v2`. Every `ScenarioSpec` keeps public task description,
  policy-visible initial state, hidden evaluator state, constraints, and
  transition parameters in distinct deeply frozen mappings.
- Manifests bind generator name/version, environment/scenario identity, seed
  stream contract, and all five structural state sections with a full canonical
  SHA-256 content hash. Files include that hash in their names so multiple root
  seeds can coexist without overwriting evidence.
- New runs materialize each unique scenario once, before treatment execution,
  and write one manifest per unique content hash. Public planner serialization
  exposes only a manifest reference and hash; hidden state and hazards are not
  present.
- Replay now requires a manifest directory, selects the exact scenario seed,
  validates its hash and identity, restores all three built-in environments
  from the manifest, and never invokes the current generator. A regression
  test replaces FileOps generation with an exception and proves replay still
  succeeds.
- Tampered manifests fail before execution. Existing manifest paths are never
  overwritten with different content. Explicit reconstructible schema-v1
  manifest records migrate deterministically; incomplete historical episode
  state fails rather than being guessed.
- Scenario manifest hashes are included in episode identity and episode
  metadata, so generator changes cannot silently alter stored scenario meaning.
- Focused manifest/identity/config/cross-process/seed tests passed (64 tests).
  The full suite passed (175 tests). Compilation, strict mypy, Ruff lint and
  format, and `git diff --check` passed after four files were mechanically
  formatted.

### Checkpoint 20 — matched clean/shift pairs

- Rebuilt canonical planning around scenario units. Each environment/scenario
  is materialized once, then expanded for each agent into one clean reference
  and every configured shifted severity treatment. A shift-only config now
  receives its required clean match automatically.
- Added stable `scenario-pair-v1` identifiers derived from scenario manifest
  content, agent identity, agent-behavior seed, and execution seed. Pair IDs do
  not depend on run ID, fault selection, severity, worker count, selectors, or
  execution order.
- Every member of a pair carries byte-identical hidden ground truth, task and
  constraints, initial state, manifest hash, scenario seed, agent seed, and
  execution seed. Only fault descriptor, severity, fault stream, and episode
  ID differ by declared treatment.
- Scientific identity advanced to schema `3`. Its seed-stream contract now
  names all six domain-separated streams, planned identity binds the scenario
  manifest hash and complete seed record, and identity-v2 episodes remain
  readable as legacy provenance.
- Worker partitions now assign complete scenario pairs rather than individual
  treatment episodes. Pair identity and manifest hashes persist through
  episode/scenario filters, pagination, checkpoint, resume, replay, and sorted
  parallel results. Checkpoints record completed pair IDs and manifest hashes.
- Added treatment-minus-clean `within_scenario_deltas.csv`, per-group unique
  scenario counts, and run metadata that reports total episodes, unique
  scenarios, and unique scenario pairs separately.
- Focused pairing/identity/manifest/pairwise tests passed (55 tests). The full
  suite passed (180 tests). Compilation, strict mypy, Ruff lint and formatting,
  and `git diff --check` passed after mechanical formatting/import ordering.

### Checkpoint 21 — clean competence gates

- Classified `naive` and `offline_llm_fixture` as diagnostic agents and
  `validate_then_act`, `monitor_gated`, `conservative`, and `retry` as reference
  agents under `reference-agents-v1`. Resilience eligibility no longer treats a
  deliberately naive baseline as a reference policy.
- Added explicit clean safety, usefulness, and coverage requirements for every
  built-in environment. Safety is required to equal `1.0`; usefulness and
  coverage must each meet `0.8`. Expected-but-missing episodes count against
  every metric, and orchestration errors fail the report.
- A clean preflight now runs reference agents on the configured scenario set
  before the main experiment. It never suppresses a failure: detailed rows,
  failed gate names, and orchestration errors are written to
  `results/competence_report.json`, copied into run metadata, propagated into
  analysis metadata, and surfaced in the Markdown report.
- Repaired FileOps policy scaffolding to use the public declared task target and
  exclude visibly protected candidates. Archive targets are generated old
  enough for all declared thresholds. Calendar conflicts no longer overlap the
  declared clean common slot, and RiskOps recommendations obey visible maximum
  adjustments and risk headroom.
- Clean golden tests span all four reference agents and all three environments;
  they pass with safety `1.0`. Separate regressions prove protected FileOps
  resources are never selected on clean scenarios and failed/incomplete gates
  remain visible.
- Focused competence/context/environment/reporting tests passed (27 tests).
  The full suite passed (185 tests). Compilation, strict mypy, Ruff lint and
  formatting, and `git diff --check` passed after mechanical formatting/import
  ordering.

### Checkpoint 22 — genuine multi-step environments

- Added step-lifecycle contract `environment-state-machine-v2`, frozen
  `StateTransition` records, and explicit completed, abstained, unsafe-action,
  invalid-action, orchestration-error, and budget-exhausted stop reasons.
- FileOps now executes inspect → select → act → verify. Its action phase mutates
  the file tree (delete, archive, or move), and completion requires a separate
  verification transition against the resulting state.
- CalendarOps now executes query → resolve conflict → schedule → verify. The
  selected slot is policy-visible state, scheduling mutates the event state,
  and verification is separate from the scheduling action.
- RiskOps now executes observe → adjust → advance → reassess → complete. It
  mutates exposure, applies a deterministic market/limit transition, makes the
  changed state visible, permits a corrective reassessment, and verifies the
  final execution-time risk envelope.
- The runner no longer treats the first valid action as terminal. It records
  before/after phase and revision, consequence, observation/execution time,
  safety, and terminal status for every action. Non-terminal invalid actions
  leave the revision unchanged and can recover; exhausted budgets remain
  serialized as incomplete outcomes.
- Packaged experiment configs now budget six steps. The identity step-semantics
  version records the state-machine contract, while the legacy run-ID helper
  preserves the historical implicit one-step default for compatibility.
- Pairwise compound execution now uses the same six-step `EpisodeRunner`
  lifecycle rather than its former one-shot side path.
- Tests cover trajectories of four or five meaningful transitions in every
  environment, recoverable intermediate failure, late unsafe action at step 2,
  budget exhaustion, abstention, immutable transitions, and byte-deterministic
  termination. Focused lifecycle/environment/competence tests passed (18
  tests); the full suite passed (190 tests). Compilation, strict mypy, Ruff
  lint/format, and `git diff --check` passed after mechanical formatting and
  import ordering.

### Checkpoint 23 — fault schedules

- Added typed immutable `FaultSchedule` records under contract
  `fault-schedule-v2`. Schedules bind one ordered fault chain to configured
  severity, onset, optional duration, persistent or transient behavior,
  optional intermittent recurrence, and a deterministic per-active-step
  severity profile. Each canonical schedule has a stable schedule ID.
- Configuration schema v2 now accepts the richer schedule representation and
  deterministically maps legacy `start_step`/`end_step`/`cadence` schedules to
  finite transient windows. It validates timing, recurrence, profiles, known
  fault components, severity range, and exact treatment-matrix coverage while
  permitting multiple schedules for one treatment so windows can overlap.
- Planning attaches all matching schedules to each treatment episode, includes
  their full definitions in episode hashes, and records their IDs in planned
  identity. The automatically matched clean condition receives an explicit
  persistent zero-effect `normal` schedule.
- Scientific identity advanced to schema `4`. Semantic identity now records
  schedule contract and ID, versioned fault descriptors, configured severity,
  onset, duration, persistence, recurrence, and per-step profile. Stored
  identity-v2 and identity-v3 episodes remain readable; identity-v4 readback
  verifies the serialized schedule IDs.
- The runner starts each call from the clean environment tool channel, then
  evaluates every schedule for the current lifecycle step and composes all
  active faults before redaction and policy exposure. Fault randomness derives
  from the fault stream, schedule ID, step, and component position.
- Exact active/inactive and scheduled-severity provenance is retained in the
  evaluator trace for every step. Schedule provenance and ordinary fault labels
  are stripped from the policy response and therefore cannot enter agents,
  monitors, or policy traces.
- Tests cover persistent, finite transient, intermittent, and late-onset
  activation; variable severity profiles; invalid timing and matrix coverage;
  overlapping windows; inactive → active → recovered boundaries; application
  on every persistent step; policy redaction; and run/episode identity changes.
  Focused schedule/config/identity tests passed (67 tests); the full suite
  passed (195 tests). Compilation, strict mypy, Ruff lint/format, and
  `git diff --check` passed after mechanical formatting and import ordering.

### Checkpoint 24 — real retry and requery

- Added versioned `tool-requery-v1` semantics. `AgentAction` can now represent
  `requery_tool` as a policy decision that is neither an environment action nor
  an abstention; targeted or abstaining requeries are rejected at construction.
  RetryAgent advanced to component version `2.0.0` and declares this capability
  in its plugin descriptor.
- Added semantic config `requery_attempts` (default `2`) independently of the
  pre-existing operational `retry_attempts`, which continues to govern whole-
  episode infrastructure retries after plugin exceptions. The per-step requery
  budget is part of step semantics and scientific identity advanced to schema
  `5`; identity-v2 through identity-v4 episode records remain readable.
- The runner now executes a bounded tool-attempt loop inside each lifecycle
  step. Every attempt requests a new internal clean environment response, then
  evaluates and composes the same current fault schedule before redaction. Only
  the shifted, redacted response is passed to the agent or monitor; a requery
  never calls `execute` or creates a state transition.
- Each deterministic `ToolAttemptRecord` records step, attempt/max attempt,
  stable call ID, decision and reason, outcome, unit tool cost, response
  latency, and a hash of the policy-visible shifted response. Evaluator-only
  provenance records the exact schedule evaluations and realized faults and
  explicitly records that no clean response was exposed. Policy traces omit
  this evaluator provenance.
- Episode traces and metadata now report per-step attempt lists, total tool
  calls, accepted requeries, tool cost units, and the enforced budget. A policy
  that requests beyond the final attempt is converted to an explicit safe
  `requery_budget_exhausted` abstention.
- RetryAgent requests another shifted observation for incomplete observations,
  invalid schema, and conflicting output. It fingerprints visible responses,
  detects repetition and suspected persistent faults, can act when a later
  response recovers, and safely abstains after exhaustion without retaining an
  environment handle or accessing pristine state.
- Tests prove every persistent-fault attempt has the same active schedule and
  remains shifted, clean/evaluator provenance is absent from policy records,
  retry counts are bounded even for a non-compliant agent, recovery and
  repeated-response paths work, cost/latency/provenance are recorded, requery
  budget changes scientific identity, and traces are byte-deterministic across
  worker counts. Focused requery/config/identity tests passed (83 tests); the
  full suite passed (207 tests). Compilation, strict mypy, Ruff lint/format,
  and `git diff --check` passed.

### Checkpoint 25 — causal latency

- Added `causal-latency-v1` and formalized every first-party environment clock
  as deterministic simulated milliseconds. A response is timestamped before
  service, then the environment advances by exactly `ToolResponse.latency_ms`
  before policy decision or execution. Zero latency preserves the clock.
- Every visible response now carries timing with clock unit, observation
  timestamp, response latency, pre-response environment clock, and response-
  received timestamp. `ObservationContext` exposes the same documented visible
  fields. Step traces additionally record execution timestamp and final
  environment clock; evaluator attempt provenance keeps the full causal timing
  record for every original query and requery.
- Latency composes across requeries. Each subsequent call observes the clock
  left by the preceding response, while the schedule remains on the same
  lifecycle step. Tests prove the final clock delta equals the sum of attempt
  latencies and all combined latency+schema responses remain shifted.
- Freshness monitoring now computes age against the post-latency context clock.
  RiskMonitor consumes `context.response_latency_ms` rather than probing the
  `Observation` for a nonexistent latency attribute, and records the visible
  latency contribution to its score.
- FileOps now revalidates a generated operation deadline at execution.
  CalendarOps activates late conflicts as time advances, removes invalidated
  availability, and revalidates its scheduling deadline. RiskOps activates
  deterministic liquidity, volatility, or limit hazards and revalidates the
  current risk envelope; its explicit market-advance transition advances the
  same clock by one simulated second.
- Scenario generator identity advanced to
  `deterministic_synthetic_scenarios@2.1.0` because generated deadlines and
  timed hazard semantics changed. Scientific identity advanced to schema `6`
  and records the causal clock contract. Stored manifests remain authoritative
  under their recorded generator version, and identity-v2 through identity-v5
  episode records remain readable.
- A newly reachable clean Calendar distractor collision under the new scenario
  seed stream was retained as a diagnostic failure until the generator was
  repaired: only the declared target slot can now contain all required
  attendees, while distractor variation remains.
- Tests cover exact clock arithmetic, negative/inconsistent timing rejection,
  policy-visible timing, deterministic latency traces, all three environment
  runners, File deadline expiry, Calendar conflict/deadline activation, Risk
  limit tightening, monitor field use, latency/requery/fault composition, and
  identity/generator versioning. The full suite passed (216 tests).
  Compilation, strict mypy, Ruff lint/format, and `git diff --check` passed
  after mechanical formatting.

### Checkpoint 26 — universal severity contract

- Added immutable `FaultEffect` records under `fault-effect-v1`. Every fault
  application now records fault name, configured application severity,
  normalized realized magnitude, effect type, explicit no-op status, and a
  canonical deterministic detail mapping. Fault provenance remains evaluator-
  only and is removed before policy or monitor exposure.
- All fault constructors and serialized `FaultConfig` records now reject
  booleans, non-numeric values, non-finite values, and values outside `[0, 1]`;
  the previous `BaseFault` severity clamp was removed. Built-in fault components
  advanced to version `2.0.0` and declare the effect contract capability.
- Severity `0.0` preserves the complete policy-visible tool response for every
  fault, including compound faults. The automatically matched zero-severity
  treatment produces the same observations, visible response hashes, actions,
  execution, and trajectory length as its clean pair while retaining evaluator
  provenance that its realized magnitude was zero.
- Defined deterministic intermediate and maximum behavior for every fault:
  quantized schema renames; bounded timestamp staleness and stale-value edits;
  proportional added milliseconds; deterministic removed-field paths;
  conflict fractions; bounded corrupted-memory claims; proportional/thresholded
  constraint deltas; and composed component effects. `normal` is explicitly a
  zero-effect channel at every configured severity.
- Episode metadata now separates treatment-level configured severity from all
  per-call realized effects, retains the canonical effect list, and reports
  application count and maximum realized magnitude. Episode/analysis rows add
  configured and realized fields; aggregate metrics add mean realized effect;
  within-pair deltas retain the treatment realized magnitude.
- Scientific identity advanced to schema `7` and records
  `fault-effect-v1`; fault component version changes therefore alter semantic
  identity. Identity-v2 through identity-v6 episode records remain readable.
- Tests exercise zero, `0.25`, `0.5`, and `1.0` for all nine faults in all three
  environments; prove deterministic monotonic realized magnitude; inspect every
  exact summary family and maximum endpoint; prove hidden state preservation;
  reject negative, over-one, boolean, string, NaN, and infinity severities; and
  verify episode/analysis/identity propagation. Focused severity tests passed
  (158 tests); the full suite passed (362 tests). Compilation, strict mypy,
  Ruff lint/format, and `git diff --check` passed after mechanical formatting.

## Contract versions

- Starting identity schema: `2`.
- Starting planned-identity schema: `2`.
- Starting configuration schema: `2`.
- Starting plugin contract: `1`.
- Starting canonical serialization schema: `1`.
- Starting scenario semantic label: `v1` (not a complete manifest schema).
- Current identity and planned-identity schema: `7`.
- Current fault-schedule contract: `fault-schedule-v2`.
- Current tool-requery contract: `tool-requery-v1`.
- Current causal-latency contract: `causal-latency-v1`.
- Current fault-effect contract: `fault-effect-v1`.
- Current built-in fault component version: `2.0.0`.
- Current scenario generator: `deterministic_synthetic_scenarios@2.1.0`.
- Current scenario-manifest contract: `scenario-manifest-v2`.
- Current step-lifecycle contract: `environment-state-machine-v2`.

## Remaining risks

- Root generated evidence is historical and must not be regenerated merely to
  satisfy validation.
- Existing external plugin contracts are one-shot; compatibility adapters will
  be required until a separately managed contract deprecation.
