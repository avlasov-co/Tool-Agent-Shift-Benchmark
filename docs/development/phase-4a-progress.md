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

Checkpoint 18 — seed-dependent scenarios — in progress.

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
