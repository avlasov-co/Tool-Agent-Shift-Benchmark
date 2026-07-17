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

Preparation complete. The metric dictionary was written before implementation.
Checkpoint 46 is next.

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

Pending.

### Checkpoint 47 — statistical design

Pending.

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
