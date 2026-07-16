# Phase 2 identity, serialization, and configuration plan

## Problem statement

Phase 1 left selectors inside the run hash, runtime episode construction able to
recompute planned identity, several scientific writers using permissive JSON
fallbacks, and an unversioned permissive configuration surface. Phase 2 must
make scientific identity independent of execution choices, preserve planned
IDs through every lifecycle state, enforce one strict deterministic serializer,
and move all shipped configurations to a validated version 2 schema.

## Observed behavior

- On the clean Phase 1 head `fb3bd01`, a three-episode plan at seed 11 produced
  run `run_dfb379c348b1cb76` and episode `ep_de1f4d89465060fb`. Passing that
  episode as `episode_ids` produced run `run_38027f281c612505` and zero matches.
- Selecting scenario index 1 produced run `run_e332b26e1a7c93a8` and a different
  episode ID for the same semantic episode.
- `Episode.__post_init__` recomputes its ID from runtime fields instead of
  accepting the planner's authoritative value.
- `json_default`, artifact writers, checkpoints, and result writers permit
  disparate serialization paths; paths are stringified and finite floats are
  not enforced universally.
- Configuration loading falls back to JSON or a tiny YAML parser when PyYAML is
  missing. Version 1 validation constructs `PluginCatalog`, which discovers and
  loads third-party entry points during syntax/schema validation.
- The Phase 1 non-destructive audit passes every source/package check and
  reports only the documented absent checked-in `results/episodes.jsonl`
  evidence.

## Invariants

- Selectors, paths, worker settings, logging, retries, batching, and artifact
  placement never affect scientific identity.
- Semantic generator, environment, agent, shift order, severity, schedule,
  oversight, step, seed-stream, resource, and evaluator changes do affect it.
- The planner is the sole authority for run, scenario, pair, seed, and episode
  identity; runtime descriptors are checked before artifacts are written.
- Canonical data supports only null, booleans, integers, finite floats, strings,
  string-keyed mappings, ordered sequences, registered dataclasses, and
  registered enums. Errors identify the exact field path.
- Syntax and schema validation are pure and do not import or execute arbitrary
  plugin code.
- Existing run artifacts remain readable through explicit compatibility paths;
  generated benchmark corpora are never regenerated or discarded to satisfy a
  check.

## Affected modules

- Planning/runtime: `src/core/orchestration.py`, `src/core/episode.py`,
  `src/core/contracts.py`, `src/core/catalog.py`, environment descriptors, and
  `src/run_eval.py`.
- Identity/serialization: new focused core modules plus
  `src/core/types.py`, `src/core/serialization.py`, `src/core/artifacts.py`, and
  `src/core/run_artifacts.py`.
- Configuration/CLI: `src/core/config.py`, `src/core/config_schema.py`,
  `src/cli.py`, shipped YAML files, and operational scripts that consume them.
- Tests/docs: focused identity, serialization, configuration, CLI, artifact,
  cross-process, resume/replay, and compatibility regressions; this plan and
  `phase-2-progress.md`.

## Migration strategy

1. Build the complete canonical episode matrix before applying ID, scenario,
   pagination, worker-partition, resume, or replay selection. Preserve the
   historical unfiltered hash shape so valid unfiltered v1 IDs remain stable.
2. Introduce a typed identity-v2 document split into semantic and operational
   configuration. Normalize defaults and representations, persist it in run
   manifests, and use only its semantic document for scientific hashes.
3. Add planned identity to runtime records and validate environment/plugin
   descriptors against it with structured mismatch errors before checkpoint or
   artifact writes.
4. Replace scientific JSON paths with a canonical serializer and explicit
   compatibility readers for legacy records.
5. Add a strict typed configuration-v2 model, pure validation, deterministic v1
   migration, `tasb config validate`, and `tasb config migrate`; migrate every
   shipped config and retain the legacy `validate-config` alias.

## Compatibility

- Valid IDs from complete legacy plans remain stable at Checkpoint 5. IDs
  produced by the broken filtered implementation were selector-derived and are
  classified as non-canonical; migrations/readers will preserve them as legacy
  provenance but will not treat them as authoritative v2 IDs.
- Legacy episode/artifact readers accept schema-v1 records and validate any
  stored ID against their declared compatibility mode. New writers emit only
  strict current schemas.
- Python APIs keep compatibility wrappers where practical. Existing
  `tasb validate-config` remains as an alias while the versioned
  `tasb config validate` surface becomes authoritative.
- Config migration is explicit and deterministic. Unknown or ambiguous legacy
  values fail with a path and a remediation message rather than being guessed.

## Tests

- Checkpoint-focused regression suites cover selector combinations, identity
  equivalence/difference, faulty descriptors, lifecycle states, unsupported
  serialization values and paths, cross-process/directory determinism, config
  schema/migration behavior, CLI/API parity, and all shipped configurations.
- Before every checkpoint commit run the full suite, focused identity/config/
  serialization tests, lint, format check, strict typing, branch coverage,
  compilation, `make audit`, and `git diff --check`.
- The final gate additionally builds the package, installs its wheel into a
  fresh temporary environment, and exercises `tasb --help`, both config
  validation commands, migration, and deterministic planning.

## Rollout

- Commit one independently reviewable change for each Checkpoint 5 through 9.
- Update `phase-2-progress.md` with evidence and compatibility notes before each
  checkpoint commit.
- After Checkpoint 9, run the complete validation matrix and conduct a focused
  review for semantic/operational leakage, recomputation, canonicalization,
  list ordering, floating-point behavior, plugin execution, migration
  ambiguity, and selector gaps.

## Rollback

- Each numbered checkpoint is a coherent revert boundary. Reverting never
  deletes run bundles or root evidence.
- Compatibility readers and v1 migration remain available until a separately
  approved removal release. Broken selector-derived IDs are retained only as
  provenance, never rewritten in place.
- If a gate fails, fix forward within the current uncommitted checkpoint or
  revert only that checkpoint; do not reset or clean user-owned artifacts.

## Unresolved risks

- First-party components currently expose limited version metadata, so identity
  v2 must define stable explicit built-in versions without importing external
  plugins during pure validation.
- Existing schema-v1 artifacts do not always declare whether an ID came from a
  filtered plan; compatibility readers can detect mismatches but cannot infer
  lost selector provenance.
- CSV remains an interoperability export rather than the canonical scientific
  encoding; JSON identity-bearing columns embedded in CSV must still be created
  by the strict serializer.
- The audit's generated-evidence check is expected to remain red until a future
  provenance-backed evidence release; it is not repaired in this phase.
