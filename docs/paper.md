# Tool-Agent Shift Benchmark: evidence design for tool-environment shift

## Abstract

Tool-using policies depend on schemas, observations, memory, timing, and
constraints that may change or become unreliable. This benchmark provides
deterministic synthetic environments and evaluator-visible ground truth for
studying those failures. Its v0.4.0 evidence design separates proposed from
executed actions, detector quality from gating outcomes, and planned from
completed episodes. It does not certify deployed systems.

## Design

Each planned episode resolves a versioned scenario manifest, plugin identities,
seed streams, agent, shift chain, severity, monitor composition, and oversight
treatment. Agents and monitors see only policy-visible context. An immutable
action record preserves the proposal, explanation, monitor decision,
intervention, executed action, realized outcome, and evaluator-only
counterfactual score.

The included synthetic environments are FileOps, CalendarOps, and RiskOps.
Faults exercise schema, freshness, missing-data, disagreement, memory, latency,
constraint, and compound-shift behavior. Reference policies are deterministic
mechanism probes, not frontier-model proxies.

## Outcomes

`metric-schema-v2` defines safe success, safe non-success, usefulness,
abstention, intervention, proposal harm, execution harm, constraint violation,
stale-data action, tool/plugin/orchestration failure, incompleteness, and budget
exhaustion. Rates retain explicit numerators and denominators.

Temporal recovery requires a prior hazard, later corrective behavior, and a
later safe useful/successful state. Abstention alone is not recovery. Schema
recovery is separate.

## Statistical design

The hierarchy is scenario family → unique scenario manifest → root seed →
environment → agent → shift → severity → oversight treatment → repeated steps.
Repeated steps do not create independent samples. Clean/shift effects use
matched scenario differences before deterministic paired bootstrap. Absolute
rates use deterministic scenario-clustered bootstrap. Every interval reports
its method, analysis seed, scenario/seed/condition counts, and sufficiency
status; insufficient cells have no numeric bounds.

## Monitor evaluation

Detector truth is the pure counterfactual risk of the proposed action, never
the realized whole-episode outcome. Threshold tables report TP, FP, TN, FN,
precision, recall, specificity, FPR, FNR, and scenario-clustered uncertainty.
Realized gating tables separately report actual interventions, prevented harm,
unnecessary blocks, useful-coverage cost, and executed harm.

Reliability diagrams require scores declared as probabilities under
`probability-score-v1`. Built-in heuristic scores are ordinal and explicitly
ineligible. Eligible probability scores report Brier score, equal-width ECE,
bin counts, and justified clustered uncertainty. Utility weights are
configurable and all raw components remain visible; Pareto membership is
reported separately and is not a benchmark ranking.

## Evidence and reporting

Completed runs are self-contained under `runs/<name>/`. Reports can be generated
only from a `complete_valid` source and embed the pre-report run manifest,
finalization record, checksums, schema versions, sample counts, uncertainty
status, clean competence result, and executed treatments. Plots aggregate raw
numerators and denominators rather than averaging summary rates. Failure-cluster
IDs are content hashes, so changing cluster frequency cannot rename a pattern.

## Current claim status

No numeric v0.4.0 headline claim appears in this paper before the two clean
standard-suite rehearsals are complete. The claims-to-evidence ledger at
`docs/metrics/claims-to-evidence-ledger.md` is authoritative. Historical root
outputs predate the current evidence contracts and are not cited.

## Limitations

The benchmark is synthetic, its scenarios are intentionally small, and its
reference policies are transparent. Scenario-cluster counts may be insufficient
for narrow cells. Counterfactual scoring depends on the synthetic environment's
pure evaluator. These results do not establish real-world safety, robustness,
or model capability. Held-out challenge outcomes must not be used for tuning.
