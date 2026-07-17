# Phase 6 evidence and v0.4.0 release plan

## Problem statement

The benchmark has deterministic execution and self-contained run bundles, but
its evidence layer still mixes ambiguous episode outcomes, pseudo-replicated
uncertainty, realized outcomes in monitor labels, stale global reports, and
unsupported chart names. Phase 6 must make every headline result traceable to a
verified run and prepare a reproducible, local-only v0.4.0 release candidate.

## Observed behavior

- The clean Phase 5B baseline is commit `ebe444f` on
  `codex/phase-5b-artifacts-resume`; Phase 6 starts on
  `codex/phase-6-evidence-release`.
- `metrics.aggregation` credits recovery for abstention or a safe shifted
  outcome without proving a prior hazard and later correction.
- `metrics.confidence` applies a normal interval to already aggregated seed
  rows and treats those rows as independent.
- Monitor threshold and calibration analysis joins monitor scores to realized
  episode safety instead of proposed-action counterfactual risk.
- Plotting averages aggregate rows without denominator weights, draws no
  interval bars, calls a bar chart a heatmap, and calls absolute-error bars a
  calibration curve.
- Checked-in root results and plots predate the current action-record,
  counterfactual, scenario-split, and run-bundle contracts. They are historical
  examples, not Phase 6 evidence.
- The Phase 5B release verifier proves deterministic minimal runs but does not
  define versioned smoke/standard/research/challenge suites or retain the full
  two-pass standard-suite reproduction and performance evidence requested here.

## Invariants

- Agents and monitors receive only policy-visible context; evaluator labels,
  hidden ground truth, scenario split, and shift provenance remain evaluator
  only.
- Planned, started, completed, failed, pending, and incomplete work remains
  explicit. Missing episodes never improve a rate.
- Scientific identities use canonical content and stable hashes, never process
  order or wall-clock values.
- Clean-versus-shifted effects use matched scenario pairs. Repeated steps and
  treatment cells from one scenario are not independent samples.
- Monitor detector quality uses the pure counterfactual risk of the proposed
  action. Realized execution safety is a separate outcome family.
- Release work is non-destructive and local. Root evidence, user run bundles,
  tags, remotes, and publication systems are not overwritten or mutated.
- The challenge suite is structural and held out; its outcome results are not
  used to tune implementation or thresholds.

## Affected modules

- Metrics: `metrics/aggregation.py`, `metrics/confidence.py`, new outcome and
  statistical contracts, and their tests.
- Evidence export: `run_eval.py`, `run_seeds.py`, action/counterfactual-derived
  analysis records, manifests, and verification.
- Analysis/reporting: `analysis/run_analysis.py`, pairwise analysis, plots,
  Markdown/HTML reports, failure clustering, provenance validation, and docs.
- Suites/release: packaged suite manifests, CLI surfaces, release verification,
  distribution smoke, artifact builder, metadata, SBOM/checksums, performance
  budgets, and migration/release documents.
- Evidence: new named Phase 6 run bundles only. Historical root outputs remain
  untouched unless an explicit evidence-release commit is justified by the
  ledger and recorded commands.

## Migration strategy

1. Publish `metric-schema-v2` definitions before changing calculations.
2. Replace ambiguous outcome helpers with typed step/episode classifications;
   retain old names only where their v2 formula is explicit and compatible.
3. Generate long-form metric records containing numerator, denominator, unit,
   eligibility, missing-data rule, formula, and schema version.
4. Replace seed-row normal intervals with deterministic scenario-clustered and
   matched-pair bootstrap estimates, with visible insufficiency status.
5. Rebuild monitor tables from proposed-action counterfactual scores and keep
   realized execution outcomes in separate columns/artifacts.
6. Make plots and reports consume verified bundle metadata and validated
   long-form evidence; reject incomplete or unsupported claims.
7. Add versioned suite manifests and performance/reproduction checks, then
   advance release metadata to v0.4.0 with a migration guide.
8. Run one full release rehearsal, conduct a sequential bias/pairing/label/
   claims/reproducibility review, fix findings, and run the complete rehearsal
   again.

## Compatibility

- Python 3.10 through 3.14 and the `tasb`/module CLIs remain supported.
- Config schema v2, identity v2-compatible readers, plugin contract v2,
  action-record v1, counterfactual-evaluation v1, scenario-manifest v3,
  checkpoint v2, and run-bundle v2 remain explicit boundaries.
- Ambiguous legacy aggregate CSVs remain readable only as historical input and
  are never silently promoted to metric-schema-v2 evidence.
- `monitor_recall`, `monitor_precision`, and monitor false-positive rate change
  meaning intentionally: v2 uses eligible proposed-action counterfactual labels
  rather than realized episode outcomes.
- `recovery_rate` changes intentionally: v2 requires a prior hazard, later
  correction, and a later safe/useful state. Schema repair is reported
  separately as `schema_recovery_rate`.

## Tests

- Hand-built category and denominator fixtures for every metric dictionary
  outcome.
- Synthetic null, positive, clustered, unbalanced, missing, and paired
  statistical fixtures plus interval determinism and insufficiency tests.
- Monitor TP/FP/TN/FN, safe/unsafe block, threshold, calibration eligibility,
  Brier/ECE, and interval fixtures.
- Report/plot provenance, sample count, interval method, clean competence,
  incomplete-run, supported-treatment, stable-cluster, and stale-global tests.
- Suite identity, plan counts, split integrity, artifact verification,
  performance thresholds, installed sdist smoke, standard reproduction, and
  canonical comparison tests.
- Full lint, format, typing, tests, branch coverage, build, installed smoke,
  audit, docs, artifact, release, performance, and diff checks.

## Rollout

- Commit this plan/dictionary baseline first.
- Commit Checkpoints 46, 47, 48, 49, and 50 separately and record exact
  validation evidence in `phase-6-progress.md` before each commit.
- Keep release rehearsals and generated release bundles local and record their
  absolute retained log paths, checksums, and SBOM locations.
- Prepare exact local tag and publication commands as documentation only.

## Rollback

Each checkpoint is independently revertible. Generated runs and release
artifacts live in ignored, named paths and are never required to roll back
source. Historical root evidence is not rewritten. If a schema migration fails,
retain the old reader and reject promotion to v2 evidence rather than coercing
records.

## Unresolved risks

- Small built-in suites may be insufficient for narrow confidence intervals;
  the correct result is a visible insufficiency flag, not a zero-width interval.
- Deterministic synthetic scenarios support internal validity but not deployment
  representativeness.
- Python subprocess isolation is not a kernel sandbox; Phase 5A limitations
  remain.
- Full suite/release rehearsal runtime may require budget adjustments based on
  measured local performance; thresholds will be evidence-based and documented.
