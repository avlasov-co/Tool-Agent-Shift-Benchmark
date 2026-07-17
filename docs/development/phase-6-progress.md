# Phase 6 progress

## Baseline

- Started from clean Phase 5B commit `ebe444f` and created
  `codex/phase-6-evidence-release`.
- Read `AGENTS.md`, `PLANS.md`, every phase progress record, metrics,
  scenario-pair/split contracts, action and counterfactual records, run
  manifests, reports, README/paper-like documents, plots, release scripts, and
  current benchmark outputs.
- The tracked root evidence is historical: it lacks current action records,
  counterfactual labels, scenario splits, artifact v2 verification metadata,
  and Phase 6 metric provenance. It will not support headline claims.
- Visual inspection confirms the checked-in calibration, threshold, pairwise,
  monitor, and static/dynamic images are unlabeled legacy bar renders. Their
  filenames and claims are not reliable evidence.

## Current checkpoint

Checkpoint 47 is complete and ready for its numbered commit.

## Baseline defects to resolve

1. Recovery can be credited without a prior hazard or correction.
2. Aggregate seed rows are treated as independent confidence observations.
3. Monitor labels use realized episode outcomes rather than proposed-action
   counterfactual risk.
4. Aggregate rows are averaged without denominators in reports and plots.
5. Failure-cluster identifiers depend on frequency ordering.
6. Static/dynamic labels actually compare clean and shifted conditions.
7. Confidence plots omit interval bars; calibration and heatmap labels are
   inaccurate.
8. Reports can consume unverified, incomplete, or stale global files.
9. No v0.4.0 versioned suite/performance/rehearsal contract exists.

## Checkpoint evidence

Validation commands, results, compatibility decisions, generated evidence
paths, and commit identifiers will be appended before each numbered commit.

### Checkpoint 46 — outcomes and recovery

- Added `metric-schema-v2` with typed step, episode, definition, and evidence
  records. Every rate evidence row carries numerator, denominator, value/unit,
  inclusion and missing-data rules, formula, status, and condition dimensions.
- Exported bundle-owned `metric_evidence`, `episode_outcomes`, and
  `step_outcomes` CSV/JSONL artifacts and declared their schema in the run
  manifest. `results/config.json` and `run_manifest.json` record the metric
  schema version.
- Separated safe success, safe non-success, useful action, agent abstention,
  executed abstention, oversight intervention, unsafe proposal, unsafe
  execution, constraint violation, stale-data action, tool failure, plugin
  failure, orchestration failure, incompleteness, and budget exhaustion.
- Planned episodes are the denominator for episode outcomes; eligible complete
  action records are the denominator for step outcomes; counterfactual-eligible
  proposals are the denominator for proposal harm. Zero eligible units produce
  a visible `no_eligible_units` status and null evidence value.
- Replaced heuristic recovery with ordered temporal recovery: a prior hazard,
  later corrective behavior, and a later safe useful/successful state.
  Abstention alone fails recovery. Detected schema recovery is separate.
- Removed ambiguous recovery/schema-recovery/oversight-efficiency calculations.
  The old execution hint is exported only as `legacy_recovered_hint`; v2
  calculations ignore it. `safe_completion_rate` remains only as a documented
  deprecated CSV alias to canonical `safe_outcome_rate`.
- Added hand-constructed fixtures covering every outcome category, plugin and
  orchestration classification, numerator/denominator accounting, positive
  temporal/schema recovery, and abstention-only non-recovery.
- Focused outcome/metric/isolation/verification/reporting checks passed 28
  tests. The full suite collected and passed 563 tests after compilation.
  Ruff lint/format-check and strict configured mypy passed; `git diff --check`
  passed.
- Installed editable CLI smoke produced seven planned/completed episodes at
  `/tmp/tasb-phase46-x7GGNy/runs/phase46-smoke`. Strict verification reported
  `complete_valid`, 40 artifacts, and no errors. The manifest declares both
  `metric_schema_version=metric-schema-v2` and the same schema for
  `results/metric_evidence.jsonl`.

### Checkpoint 47 — statistical design

- Added deterministic scenario-clustered percentile bootstrap intervals and
  matched clean/shift paired intervals. Repeated steps are collapsed within a
  scenario before resampling; treatment-minus-clean effects are computed before
  paired resampling; scenario-family strata and sampling populations are
  canonically ordered so row order cannot change results.
- Statistical records report the effect, numeric bounds only when justified,
  method, status, confidence level, independent scenario/family/seed/condition
  counts, missing-pair count, analysis seed, and resample count. Cells with no
  eligible units or fewer than two independent scenarios refuse an interval
  visibly instead of manufacturing one.
- Added Wilson intervals behind an explicit independent-binary-unit guard,
  optional Bonferroni/Holm/Benjamini-Hochberg corrections, and paired
  normal-approximation sample-size planning. The parent bundle persists the
  exact analysis config and plans for 0.05, 0.10, and 0.20 effects under the
  stated standard-deviation assumption.
- Rebuilt multi-seed inference from per-episode v2 outcomes instead of averages
  of aggregate seed rows. Parent multi-seed outputs are first-class analysis
  bundles with stable identities and finalized child evidence bundles rather
  than unverifiable loose directories.
- Confidence plots use the emitted interval endpoints as error-bar whiskers. A
  rendering test spies on `Axes.errorbar` so a title or filename cannot pass as
  interval evidence.
- Synthetic tests cover null/positive paired effects, unbalanced repeated
  observations, missing pairs, insufficient independent units, zero eligible
  cells, input-order determinism, independence guards, correction methods,
  sample-size planning, and hierarchy counts. The focused statistical,
  multi-seed, reporting, reproducibility, and pairing suite passed 22 tests.
  The supported repository lint and format checks passed, configured mypy
  passed, compilation and the full test suite passed, and `git diff --check`
  passed.
- A real 810-episode, three-seed smoke at
  `runs/phase47-statistical-smoke-2` produced 810 confidence rows (666
  estimable, 144 visibly ineligible), 720 paired rows (480 estimable, 240
  visibly ineligible), and a rendered confidence plot with actual whiskers.
  After plot inclusion and refinalization, strict verification reported
  `complete_valid`, 1,739 artifacts, stable run ID
  `run_c3f927d16592cfdd`, and no errors.
- A direct ad hoc file-target mypy invocation was not accepted because the
  repository's Python 3.10 target rejects a Python 3.12 `type` statement in an
  installed NumPy stub. The supported configured `make typecheck` command is
  unaffected and passed.

### Checkpoint 48 — monitor evaluation

Pending.

### Checkpoint 49 — analysis, plots, reports, and claims

Pending.

### Checkpoint 50 — golden suites and v0.4.0 preparation

Pending.

## Release rehearsals

Pending. Two clean standard-suite reproductions and a second complete rehearsal
are terminal requirements.

## Known limitations

- Synthetic environments and transparent reference policies do not establish
  production safety or frontier-model capability.
- Challenge split outcomes are reserved from tuning; only structural integrity
  checks may run before release.
- Independent scenario counts may be too small for justified interval claims;
  those cells will remain visibly insufficient.
