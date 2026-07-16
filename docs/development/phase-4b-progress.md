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

Checkpoint 27 — real policy-visible memory channel (in progress).

## Checkpoint evidence

Evidence will be appended after each numbered implementation and committed with
that checkpoint.

## Contract and schema ledger

| Concern | Starting version | Phase 4B version |
| --- | --- | --- |
| Scientific identity | 7 | pending |
| Episode record | legacy aggregate | pending |
| Policy memory | metadata hint only | pending |
| Tool schema registry | none | pending |
| Fault channel/mechanism | implicit | pending |
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
