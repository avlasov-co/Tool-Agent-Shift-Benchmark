# Phase 5A progress

## Baseline

- Started from clean Phase 4B terminal commit `a59629f` on
  `codex/phase-4b-faults-oversight` and created
  `codex/phase-5a-plugin-security`.
- Read `AGENTS.md`, `PLANS.md`, every prior phase progress record, the Phase 4B
  plan/handoff and Phase 5A handoff, public contracts/base classes, plugin
  registration/discovery and CLI entry points, environment adapters, shift
  invocation/composition, artifact descriptors/manifests, boundary and threat
  documentation, and related contract/context/environment/agent/monitor tests.
- Baseline `make test PYTHON=.venv/bin/python` passed all 501 tests after byte
  compilation.
- The observed v1 gaps are eager entry-point import, partial one-method
  validation, descriptor override after weaker registration, environment-name
  dispatch in `ObservationContext`, full environment access from shifts,
  mutable nested policy records, and unbounded in-process external execution.

## Current checkpoint

Checkpoint 36 — plugin contract v2 — in progress.

## Checkpoint evidence

Evidence, contract/schema changes, compatibility effects, test results, and
commit identifiers will be recorded here before every checkpoint commit.

## Terminal validation

Pending Checkpoints 36–41.

## Phase 5B handoff

Pending terminal validation and final security review.

