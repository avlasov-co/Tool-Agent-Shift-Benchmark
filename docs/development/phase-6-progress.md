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

Checkpoints 46–50, both clean-sdist release rehearsals, and the final sequential
review are complete. The repository is ready for a local v0.4.0 tag; no tag,
push, upload, GitHub release, or other publication action has been executed.

## Baseline defects to resolve

1. Recovery can be credited without a prior hazard or correction.
1. Aggregate seed rows are treated as independent confidence observations.
1. Monitor labels use realized episode outcomes rather than proposed-action
   counterfactual risk.
1. Aggregate rows are averaged without denominators in reports and plots.
1. Failure-cluster identifiers depend on frequency ordering.
1. Static/dynamic labels actually compare clean and shifted conditions.
1. Confidence plots omit interval bars; calibration and heatmap labels are
   inaccurate.
1. Reports can consume unverified, incomplete, or stale global files.
1. No v0.4.0 versioned suite/performance/rehearsal contract exists.

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

- Added packaged `suite-contract-v1` manifests and schema-v2 configs for smoke,
  standard regression, research, and held-out challenge suites. Their fixed
  plan counts are 28, 240, 3,375, and 120 respectively. The challenge contract
  explicitly prohibits development use of its outcomes.
- Added `tasb suite list|plan|run|validate`. Golden validation checks exact
  plan/completion accounting, scientific identity stability, split integrity,
  clean competence, activation of every shifted episode, trace bounds, retry
  execution, plugin descriptor/isolation boundaries, broad rate ranges, and
  strict artifact verification without brittle exact-float snapshots.
- Ordinary run analysis now emits deterministic scenario-clustered confidence
  and matched-effect tables, exact statistical config, and power plans. A
  standard suite can therefore produce a complete report lifecycle directly.
- Added `performance-evidence-v1` measurement and suite-owned budgets for
  runtime, process peak RSS, Python allocation peak, artifact size, worker
  scaling, and comparable-platform runtime regression. Smoke measured 3.00 s
  with one worker, 2.95 s with two, 63.3 MiB peak RSS, 9.08 MiB artifacts, and
  a 0.985 two/one-worker ratio on Python 3.14.6/macOS; every budget passed.
- Standard performance measured 26.64 s with one worker, 28.15 s with two,
  221.7 MiB peak RSS, 78.7 MiB Python allocation peak, 77.12 MiB artifacts,
  and a 1.057 scaling ratio on the same platform; every standard budget passed.
- The initial 810-episode standard draft was stopped after 272 episodes in 287
  seconds because its projected runtime violated the declared 300-second
  budget. The incomplete diagnostic is preserved at
  `runs/phase50-standard-budget-diagnostic`. The corrected matrix retains all
  three environments, all five agents, both oversight treatments, clean plus
  three core shifts, and two independent validation scenarios per cell; a
  batch checkpoint interval of 20 removed quadratic persistence overhead.
- The corrected 240-episode standard run completed evaluation in 17.5 seconds
  at `runs/phase50-standard-golden`. All 240 episodes completed, all 180
  shifted episodes activated, 48 retry episodes reached up to three attempts,
  2,836 bounded rate rows passed, and strict verification reported
  `complete_valid`, 550 artifacts, and run ID `run_983adda8465a5778`.
- Standard analysis produced 720 confidence rows, 540 paired-effect rows,
  2,541 counterfactual threshold/utility rows, 121 realized-gating rows, and 12
  rendered plots plus verified Markdown/HTML reports. Visual review found the
  original 30-cell vertical interval plot unreadable; it was replaced with a
  20-cell horizontal dot-and-whisker layout before release rehearsal.
- Added the v0.4.0 migration guide, benchmark card, suite/performance guide,
  changelog entry, release notes, citation metadata, sdist rehearsal driver,
  and local tag/publish command record. No challenge outcomes, tags, pushes, or
  publication actions were used or executed.
- Checkpoint validation passed 589 tests, 78.52% branch coverage, Ruff lint and
  format checks, configured strict mypy, compilation, `git diff --check`, and
  29 independent installed sdist/wheel smoke checks. The diagnostic audit
  passed compilation, tests, coverage, config/planning, package build, wheel
  inspection, isolated installation, CLI smokes, and release metadata. Its two
  expected pre-commit findings were the intentionally dirty checkpoint
  worktree and the known historical root evidence missing v2
  `results/episodes.jsonl`; current claims do not consume that root evidence.

## Release rehearsals

- The first attempted output path was accidentally placed below the source
  root, exposing recursive-copy behavior before any build or benchmark phase.
  The command was interrupted, its generated directory was moved to Trash, and
  commit `737253c` added a tested hard refusal for output at or below the source
  root. Both actual rehearsals use external retained directories.
- Rehearsal 1 at
  `/Users/aleksander/Documents/TASB-v0.4.0-release-rehearsal-1` passed all 29
  phases (225.099 summed phase-seconds). Rehearsal 2 at
  `/Users/aleksander/Documents/TASB-v0.4.0-release-rehearsal-2` passed all 29
  phases (228.383 summed phase-seconds).
- Each rehearsal built the sdist, installed locked dependencies and that sdist
  into a fresh environment, planned the challenge suite without executing its
  outcomes, and ran the complete smoke/standard lifecycle. Smoke verified at
  122 artifacts; both standard reproductions verified at 550 artifacts with
  stable run IDs `run_9b919ff0c2abc28f` and `run_983adda8465a5778`.
- Both canonical comparisons matched 541 deterministic files exactly. The
  installed standard interval plot SHA-256 is identical across rehearsals:
  `be514672f5e6685e18c586872d0a43f7672cbefadef3bce3cca1a8e07b0a940b`.
  Visual inspection confirmed the horizontal point/whisker and
  counterfactual precision/recall figures are readable; report inspection
  confirmed 240/240 completion, clean competence, both executed oversight
  modes, uncertainty, provenance, and limitations. Both HTML reports are
  nonempty at 11,002 bytes.
- Installed performance budgets passed twice. Rehearsal smoke one/two-worker
  runtimes were 3.06/2.92 and 3.16/3.00 seconds; standard runtimes were
  25.34/26.89 and 26.22/27.97 seconds. Maximum RSS was 64.0 MiB for smoke and
  265.1 MiB for standard; artifact sizes were 9.08 and 77.12 MiB; all worker
  scaling ratios were below 1.07.
- Rehearsal 2 final-candidate SHA-256 values are
  `bc734ee2c3a09c64616a51a9b4b93e81483be79ecfc0c57487a259c3df438ab0`
  (CycloneDX SBOM),
  `5c3b014f5df2bf7d0a699e6f4ec500639fdf570cf084988cd43be4e8bcdf1a2e`
  (wheel), and
  `4d9e07af8ee38dc7d8dfb6f87f972ee7ba91fe6af1b73176a03779ccba96ef93`
  (sdist). `SHA256SUMS`, the artifacts, SBOM, all phase logs, performance JSON,
  verified bundles, and unexecuted local release commands are retained below
  the rehearsal directory.
- Neither rehearsal executed a tag, push, package upload, GitHub release, or
  challenge outcome. Archive checksums differ between rehearsals because the
  standard build backend embeds build-time archive metadata; canonical
  scientific outputs and the reproducible SBOM match. Rehearsal 2 is the
  designated final local artifact candidate.
- The final non-destructive release verifier passed all 34 phases in retained
  workspace
  `/var/folders/1b/427nbdg92l14r0j71032l_5r0000gn/T/tasb-release-verification-s9m3cffo`.
  It passed 590 tests, 78.52% branch coverage, config/suite validation,
  deterministic planning, a 70-file analyzed/plotted/reported canonical
  comparison, performance, locked browser rendering, and 29-check independent
  sdist/wheel smoke. The machine-readable record is
  `release-verification.json` at that path.
- A final clean-tree `make audit` passed cleanliness, junk detection,
  compilation, 590 tests, branch coverage, config/planning, package and wheel
  checks, isolated installs, all CLI smokes, and release metadata. Its sole
  diagnostic failure is the intentionally preserved historical root evidence
  lacking `results/episodes.jsonl`; `.audit/report.json` records it, and no
  v0.4.0 report or claim consumes that legacy root directory.

## Known limitations

- Synthetic environments and transparent reference policies do not establish
  production safety or frontier-model capability.
- Challenge split outcomes are reserved from tuning; only structural integrity
  checks may run before release.
- Independent scenario counts may be too small for justified interval claims;
  those cells will remain visibly insufficient.

## Final sequential review

- Denominator audit recomputed all 3,000 standard metric-evidence rows from
  their numerators and denominators and confirmed every formula/inclusion/
  missing-data field is populated. All 240 planned episodes are completed;
  failed, pending, invalid, and skipped counts are zero and remain explicit.
- Independence audit confirmed every successful confidence interval uses at
  least two unique scenario manifests. Repeated steps are not samples. All 360
  core matched-effect cells have zero missing pairs. Recovery eligibility
  produces 152 visible unmatched eligibility units; those conditional cells
  refuse inference rather than silently repairing or dropping the mismatch.
- All 572 monitor events preserve proposed-action counterfactual scoring. The
  2,541 detector-threshold rows declare
  `counterfactual_proposed_action_unsafe`; 121 realized-gating rows use a
  separate analysis type. Built-in ordinal scores produce zero calibration
  bins and no reliability figure.
- Report validation is `valid` with no errors, golden validation passed every
  invariant, both executed oversight treatments are disclosed, and the claims
  ledger records the observed zero prevented harms rather than an unsupported
  hard-gate benefit.
- Root historical outputs remain excluded from v0.4.0 evidence. All current
  plots/reports are bundle-local, canonical scientific outputs reproduce, and
  timestamp-bound report provenance is explicitly validated instead of
  misclassified as deterministic scientific content.
