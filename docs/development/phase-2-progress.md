# Phase 2 progress

## Baseline

- Started from clean Phase 1 commit `fb3bd01` on branch
  `codex/phase-2-identity-config`.
- Retained `backup/phase-1-pre-preservation` and
  `backup/phase-1-generated-evidence` plus their named stashes.
- Provisioned the ignored `.venv` from declared development dependencies.
- Baseline `make audit PYTHON=.venv/bin/python` passed cleanliness, junk
  detection, compilation, tests, branch coverage, config validation,
  deterministic planning, build/wheel/install/CLI smoke, and metadata checks.
  It reported only the documented missing checked-in
  `results/episodes.jsonl` evidence.

## Current checkpoint

Checkpoint 8 complete and pending commit: strict canonical serialization.

## Checkpoint evidence

### Checkpoint 5 — episode filtering

- Reproduced the defect: selecting copied episode
  `ep_de1f4d89465060fb` changed run `run_dfb379c348b1cb76` to
  `run_38027f281c612505` and returned zero episodes.
- Reproduced scenario selector leakage: scenario index 1 changed the run to
  `run_e332b26e1a7c93a8` and changed the episode ID.
- Canonical construction now completes before episode-ID, scenario-index,
  pagination, worker-partition, resume, or replay selection.
- Complete-plan compatibility is preserved: the reproduced run and episode IDs
  remain `run_dfb379c348b1cb76` and `ep_de1f4d89465060fb`; selecting that ID now
  returns exactly the canonical episode.
- Unknown episode and resume IDs raise `UnknownEpisodeSelectionError`; a valid
  combination may intentionally produce an empty selection without changing
  run identity.
- CLI and Python planning share the same selectors and return identical
  matrices. Partition union/disjointness and canonical ordering are covered.

### Checkpoint 6 — semantic identity v2

- Added typed identity schema version `2` with separate semantic and
  operational documents. Run IDs and config digests hash only the normalized
  semantic document.
- Matrix order for environments, agents, severities, and distinct shift chains
  is normalized because it changes execution order only. Order within each
  shift chain is preserved and changes identity because composition is
  non-commutative.
- The normalized semantic identity and operational settings are saved in
  `results/config.json` and copied into each run manifest with the authoritative
  run ID and config digest.
- Identity-v2 run/episode IDs intentionally differ from schema-v1 IDs. The
  selector-neutral complete-plan v1 run ID is retained as `legacy_run_id` for
  explicit compatibility provenance.

### Checkpoint 7 — authoritative planned identity

- Each episode plan now carries a typed `PlannedEpisodeIdentity` containing the
  run ID, scenario ID, scenario seed, optional scenario-pair ID, episode ID,
  and planned component descriptors. The complete planned identity is embedded
  in the runtime episode record.
- `Episode` no longer computes an ID in `__post_init__`. New records require an
  authoritative ID; the explicit schema-v1 reader validates a stored legacy ID
  rather than silently replacing it.
- Runtime validates environment name/scenario/seed/index, optional component
  runtime descriptors, response identity after environment and shift calls,
  agent decision identity, and final episode fields against the plan.
- Mismatches produce structured errors with episode ID, phase, field, expected
  value, actual value, and the planned plugin descriptor. Deterministic identity
  failures are not retried as infrastructure work.
- Checkpoints from a different run fail before rewrite. Completed, failed,
  skipped, resumed, replayed, and serialized flows retain the planned IDs.
- Pairwise compound planning now assigns a planned identity-v2 run ID,
  authoritative episode/scenario seeds, and a `scenario_pair_id` shared by the
  clean, single-fault, and paired-fault variants of the same scenario.

### Checkpoint 8 — strict canonical serialization

- Added canonical serialization schema version `1`. One recursive validator and
  UTF-8 encoder now supplies scientific JSON, JSON Lines, nested CSV values, and
  hash bytes.
- Supported values are limited to null, booleans, integers, finite binary64
  floats, strings, string-keyed mappings, ordered lists/tuples, and explicitly
  registered dataclasses/enums. Paths, bytes, sets, arbitrary objects,
  non-string keys, unregistered types, NaN, and infinities fail with an exact
  field path.
- Hashes, identities, normalized run metadata, plugin descriptors, traces,
  checkpoints, failure records, episodes, analysis JSON, manifests, artifact
  metadata, and audit reports use the canonical implementation. No scientific
  writer uses `default=str`, `default=json_default`, or permissive malformed
  record swallowing.
- JSON files end with one newline; JSONL uses compact canonical records.
  Mapping keys are sorted while ordered sequences retain order. The finite-float
  and UTF-8 policies are documented in
  `docs/development/serialization-policy.md`.
- Compatibility readers accept JSON-shaped legacy values but apply the same
  finite/type validation. Unsupported legacy data now fails explicitly.

## Identity field matrix

| Field group | Scientific identity | Normalization |
| --- | --- | --- |
| Scenario generator/name/version/schema/split | Yes | Defaults explicit; strings preserved |
| Environment and agent descriptors | Yes | Sorted matrix collections; versions and contract versions included |
| Shift chains | Yes | Outer matrix sorted; component order inside a chain preserved |
| Severity and effective fault schedules | Yes | Numeric floats sorted; schedule boundaries/cadence explicit |
| Oversight treatment and monitor descriptor/modes | Yes | Defaults explicit; mode matrix sorted |
| Step and seed-stream semantics | Yes | Versioned algorithm names and root seed explicit |
| Policy resource SHA-256 hashes | Yes | Resource names sorted; hashes validated |
| Evaluator descriptor and episodes per combination | Yes | Version/name/count explicit |
| Paths, workers, selectors, replay/resume | No | Recorded in operational settings |
| Logging, artifacts, progress, retry/failure policy, batch size | No | Recorded in operational settings |

## Schema versions

- Identity schema: `2`.
- Plugin contract schema: `1` (recorded per component).
- Scenario schema default: `v1` (semantic and configurable).
- Artifact/config schemas remain at their Phase 1 versions until Checkpoints 8
  and 9.
- Episode planned-identity schema: `2`; schema-v1 compatibility reads validate
  the stored legacy ID.
- Canonical serialization schema: `1`.

## Compatibility decisions

- Preserve historical IDs from complete unfiltered plans at Checkpoint 5.
- Treat IDs emitted by the broken filtered implementation as non-canonical;
  document and retain them as legacy provenance rather than silently mapping
  them to a potentially different semantic episode.

## Validation log

- Baseline audit: all checks passed except the expected generated-artifact
  consistency finding for absent `results/episodes.jsonl`.
- Checkpoint 5 focused identity/platform/CLI/reproducibility suite: 26 passed.
- Checkpoint 5 full suite and branch coverage: 72 passed; 74.46% branch
  coverage against the 73% floor.
- Ruff lint and format check, strict mypy, compilation, and `git diff --check`:
  passed.
- Pre-commit diagnostic audit passed junk detection, compilation, tests,
  coverage, config validation, deterministic planning, package build, wheel
  inspection/install, CLI smoke, and release metadata. It reported the
  expected in-progress dirty worktree and the baseline absent structured
  evidence; both are recorded rather than hidden.
- Checkpoint 6 focused identity/selection/platform/CLI/reproducibility suite:
  46 passed.
- Checkpoint 6 full suite and branch coverage: 78 passed; 75.73% branch
  coverage against the 73% floor.
- Checkpoint 6 Ruff lint/format, strict mypy, compilation, and
  `git diff --check`: passed.
- Checkpoint 6 pre-commit audit passed every executable/source/package check;
  it recorded only the expected in-progress dirty tree and unchanged absent
  evidence corpus.
- Checkpoint 7 focused authoritative identity/selection/semantic
  identity/platform/core/pairwise/reproducibility suite: 54 passed.
- Checkpoint 7 full suite and branch coverage: 85 passed; 76.57% branch
  coverage against the 73% floor.
- Checkpoint 7 Ruff lint/format, strict mypy, compilation, and
  `git diff --check`: passed.
- Checkpoint 7 pre-commit audit passed every executable/source/package check;
  it recorded only the expected in-progress dirty tree and unchanged absent
  evidence corpus.
- Checkpoint 8 focused canonical serialization/identity/artifact/analysis/
  reporting/reproducibility suite: 80 passed.
- Checkpoint 8 full suite and branch coverage: 116 passed; 77.08% branch
  coverage against the 73% floor.
- Checkpoint 8 Ruff lint/format, strict mypy, compilation, cross-process and
  cross-directory hashing, and `git diff --check`: passed.
- Checkpoint 8 pre-commit audit passed every executable/source/package check;
  it recorded only the expected in-progress dirty tree and unchanged absent
  evidence corpus.

## Remaining work

- Complete and commit Checkpoints 5, 6, 7, 8, and 9 sequentially.
- Run the final installed-wheel, audit, deterministic identity, compatibility,
  and focused leakage review gates.
