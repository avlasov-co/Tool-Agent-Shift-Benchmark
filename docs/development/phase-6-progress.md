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

Checkpoint 49 is complete and ready for its numbered commit.

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

- Added `monitor-evaluation-v1` event, detector, gating, calibration, utility,
  and manifest schemas. Monitor events now carry scenario hierarchy,
  counterfactual proposal/execution labels, realized execution labels,
  intervention state, and explicit score semantics.
- Removed the monitor-quality join to whole-episode realized safety. Detector
  TP/FP/TN/FN use only pure counterfactual proposed-action unsafe truth;
  unsupported and not-evaluated proposals remain ineligible and visible.
- Threshold tables jointly stratify by monitor, environment, fault, severity,
  agent, oversight mode, monitor mode, and threshold. They report all four
  confusion cells, precision, recall, specificity, FPR, FNR, projected block
  rate, useful-coverage cost, explicit numerators/denominators, and
  scenario-clustered intervals or visible refusal statuses.
- Realized gating tables are separate and use the recorded monitor decision and
  actual intervention/executed action. They report intervention rate,
  prevented harm, unnecessary blocks, useful-coverage cost, executed unsafe
  rate, and clustered intervals. Threshold-sweep rows mark actual intervention
  and prevented-harm fields not applicable so a simulated decision rule cannot
  be described as an executed oversight treatment.
- Calibration requires both `score_semantics=probability` and the explicit
  `probability-score-v1` contract. Eligible scores receive equal-width bin
  counts, proposed-action unsafe frequencies, Brier score, documented ECE, and
  clustered bin/Brier intervals. Built-in ordinal monitor scores produce an
  ineligibility record, no calibration bins, and no reliability diagram.
- Replaced the opaque fixed ranking with configurable raw benefit/cost
  components and a separate recall/specificity/coverage Pareto frontier. All
  five utility weights are CLI configurable and the exact config is persisted.
- Hand-built tests cover TP/FP/TN/FN, inverted realized labels, blocked safe and
  blocked unsafe actions, prevented harm, unnecessary blocks, useful-coverage
  cost, clustered intervals and insufficiency, missing counterfactual labels,
  probability-contract refusal, Brier/ECE/bin counts, raw utility components,
  Pareto membership, and reliability-diagram gating. The focused monitor,
  analysis, reporting, action/counterfactual, CLI-artifact, and verification
  suite passed 44 tests. Repository lint, format-check, configured mypy,
  compilation, the full test suite, and `git diff --check` passed.
- A real 28-episode smoke at `runs/phase48-monitor-smoke-2` produced 64 monitor
  events, 315 joint threshold rows, 15 realized gating rows, 315 utility/Pareto
  rows, and two explicit calibration-ineligibility rows. Custom CLI utility
  weights were persisted. Plot generation correctly omitted a reliability
  diagram for ordinal scores. Strict verification reported `complete_valid`,
  109 artifacts, run ID `run_9b919ff0c2abc28f`, and no errors.

### Checkpoint 49 — analysis, plots, reports, and claims

- Renamed the false static/dynamic treatment to `clean_vs_shifted` throughout
  runtime outputs, analysis, plots, reports, tests, README, reviewer docs, and
  paper framing. Both compared values are safe-success rates and preserve their
  clean/shifted episode counts.
- Plots now pool disjoint raw numerator/denominator evidence instead of taking
  unweighted means of condition rates. A deliberately unbalanced regression
  fixture verifies the pooled result. Confidence figures show at most the 30
  widest estimable cells with actual whiskers; the subtitle discloses that
  selection.
- Replaced the recall-only plot with a true counterfactual precision-recall
  plot, replaced the arbitrary calibration bar with a contract-gated
  reliability diagram, renamed compound bars so they are not called heatmaps,
  and removed the fixed weighted agent-ranking plot. Raw safe-useful agent
  rates remain available without ranking semantics.
- Failure-cluster IDs are stable content hashes over the cluster definition,
  not frequency ranks. A regression test changes another cluster's frequency
  and confirms the original pattern keeps its identifier.
- Added `report-provenance-v1`. Analysis, plot, Markdown-report, and HTML-report
  CLI paths require a `complete_valid` source and embed its pre-mutation run
  manifest/finalization records and hashes. The final refinalized manifest then
  checksums the snapshot and generated artifacts, avoiding self-referential
  provenance.
- Reports sum raw evidence counts and link each headline metric to its schema,
  formula, numerator, denominator, and metric-evidence checksum. They disclose
  planned/completed/failed counts, clean competence, executed monitor/oversight
  treatments, and uncertainty method/status; absence of intervals is stated as
  not estimated, never zero-width evidence.
- Report validation rejects incomplete sources, pending/invalid episodes,
  missing clean-competence disclosure, missing treatment disclosure,
  incomplete metric provenance, and interval claims without methods. Loose
  root report generation is refused; fixture analysis reports are prominently
  labeled unverified diagnostics.
- Removed unsupported numeric claims from root reports and paper-like docs,
  replaced stale root generated reports with historical placeholders, rewrote
  current README/reviewer/artifact/analysis documentation for named run
  bundles, and updated stale version/treatment/metric references. Historical
  development records remain intentionally unchanged.
- Populated the claims ledger with exact Checkpoint 49 artifact readiness and
  hashes while leaving C001-C007 pending where standard/rehearsal or executed
  hard-gate evidence is still absent. In particular, `record_only` results are
  not promoted to hard-gate claims.
- Focused provenance, reporting, analysis, incomplete-run, isolation,
  verification, context, and outcome tests passed 46 tests. Repository lint,
  format-check, configured mypy, compilation, the full test suite, and
  `git diff --check` passed.
- The final lifecycle smoke at `runs/phase49-report-smoke-2` ran 28 episodes,
  analysis, 11 corrected plots, Markdown and HTML reports, and report
  validation. Strict verification reported `complete_valid`, 116 artifacts,
  stable run ID `run_9b919ff0c2abc28f`, and no errors. The final manifest and
  finalization hashes are recorded in the claims ledger. Visual inspection
  confirmed correct titles, axes, dimensions, and absence of a reliability
  diagram for ordinal scores.

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
