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

Checkpoint 27 complete; Checkpoint 28 — schema-drift families (in progress).

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

## Contract and schema ledger

| Concern | Starting version | Phase 4B version |
| --- | --- | --- |
| Scientific identity | 7 | 8 |
| Episode record | legacy aggregate | pending |
| Policy memory | metadata hint only | `policy-memory-v1` |
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
