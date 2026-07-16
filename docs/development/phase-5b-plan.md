# Phase 5B orchestration, artifact durability, and resume plan

## Problem statement

The benchmark currently has a deterministic planner and episode runner, but
command entry points still write through mutable workspace directories and then
copy their contents into a run directory. Pairwise and multi-seed execution
also contain bespoke dispatch. This leaves stale-artifact contamination,
non-atomic writes, weak bundle verification, and resume identity gaps.

## Observed behavior

- `tasb run` invokes `run_eval`, which writes `results/` directly before
  `snapshot_outputs` copies it into `runs/<name>/`.
- `run_seeds` and pairwise execution have independently orchestrated loops;
  pairwise constructs planned identities and calls `EpisodeRunner` directly.
- `ArtifactStore` is a thin JSONL facade rather than the sole writer.
- The legacy checkpoint records a run ID and completed IDs only; it cannot
  establish full normalized-config, manifest, plugin, or schema compatibility.

## Invariants

- The canonical normalized plan, `RunCoordinator`, ordered scheduler, and
  `ArtifactStore` define execution semantics for every experiment mode.
- A run bundle is self-contained and is the only runtime output destination.
  Root `results/`, `figures/`, and generated documentation remain historical
  evidence and are never copied from or overwritten by new runs.
- Scientific identity, scenario content, plugin descriptors, policy resources,
  completed IDs, and artifact schemas are durably bound before resume.
- Artifact data is canonically serialized, atomically replaced, checksummed,
  and only marked finalized after all required writes are durable.
- Failed, pending, skipped, and invalid planned episodes remain explicit in
  manifests and denominator-aware analysis.

## Affected modules

- Execution: `run_eval.py`, `run_seeds.py`, `run_sweep.py`, pairwise analysis,
  CLI, planner/coordinator, and legacy wrappers.
- Artifacts: `core/artifacts.py`, `core/run_artifacts.py`, serializers,
  scenario manifests, analysis/report/plot writers, and CLI bundle commands.
- Verification/resume: a versioned verifier/checkpoint contract, CLI, tests,
  and release/distribution smoke coverage.

## Migration strategy

1. Introduce a planner-backed execution request/result boundary and route normal,
   sweeps, seeds, pairwise treatments, replay, and resume through it.
2. Give `ArtifactStore` versioned atomic writers and make it create/own every
   run-relative output. Retain old top-level helpers only as explicitly named
   compatibility readers/wrappers.
3. Add a versioned run manifest/finalization protocol and `verify-run` with
   explicit legacy classification rather than silently accepting old bundles.
4. Version the checkpoint, save deterministic batches, validate resume
   compatibility, deduplicate IDs, and prove canonical resumed output. The
   implemented protocol is `checkpoint-v2`: traces are written before the
   episode row that makes an ID resumable, status follows, and only then does
   the checkpoint advance. `execution_batch_size`, worker count, logging, and
   display are operational; all semantic and artifact compatibility checks are
   strict.

## Compatibility

- Legacy command modules remain importable thin wrappers; new CLI run modes
  require a run bundle and never refresh global evidence.
- Existing historical bundles are classified as `legacy_needing_migration`.
  Read support is preserved where their recorded schemas can be validated.
- Operational changes (workers, display/logging) remain outside scientific
  identity; all semantic changes fail resume validation.

## Tests

- CLI/API normalized-plan and ID parity, worker-order parity, and each mode's
  common execution path.
- Stale global artifact isolation, schema/version checks, atomic write failure
  injection, and all specified corruption modes.
- Resume rejection matrix, deterministic interruption recovery, duplicate-row
  prevention, and canonical uninterrupted-versus-resumed comparison.
- Focused/full tests, lint, format-check, typecheck, coverage, audit, package
  build/install smoke, release verifier, and `git diff --check`.

## Rollout

- Work on `codex/phase-5b-artifacts-resume` from the clean Phase 5A terminal
  commit. Commit Checkpoints 42, 43, 44, and 45 separately.
- Update the matching progress record with contracts, migrations, test evidence,
  compatibility effects, and exact commit IDs before every checkpoint commit.

## Rollback

Each checkpoint is a coherent revert boundary. No rollback may delete run
bundles or rewrite global evidence. Legacy compatibility wrappers are retained
until an explicit migration/deprecation release removes them.

## Unresolved risks

- Atomic rename is filesystem-local; a crash can leave a temporary file, which
  verification must ignore while the finalization marker remains absent.
- Existing root evidence is intentionally incomplete under current schemas and
  must remain a documented legacy state rather than being regenerated.
- A later remote/object-store artifact backend needs its own commit/finalize
  protocol; this phase guarantees local filesystem durability only.
