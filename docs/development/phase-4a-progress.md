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

Checkpoint 20 — matched clean/shift pairs — complete; preparing Checkpoint 21.

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

## Contract versions

- Starting identity schema: `2`.
- Starting planned-identity schema: `2`.
- Starting configuration schema: `2`.
- Starting plugin contract: `1`.
- Starting canonical serialization schema: `1`.
- Starting scenario semantic label: `v1` (not a complete manifest schema).

## Remaining risks

- Root generated evidence is historical and must not be regenerated merely to
  satisfy validation.
- Existing external plugin contracts are one-shot; compatibility adapters will
  be required until a separately managed contract deprecation.
