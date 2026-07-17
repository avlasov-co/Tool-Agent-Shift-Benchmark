# Claims-to-evidence ledger

Ledger schema: `claims-evidence-ledger-v1`

Only rows with status `verified` may appear as v0.4.0 headline claims. Every
verified row must identify a complete-valid run, manifest/finalization checksum,
metric schema and formula, sample counts, interval method, clean competence,
and the report/plot that renders it.

| Claim ID | Proposed claim | Evidence unit | Required artifacts | Status |
|---|---|---|---|---|
| C001 | Reference agents satisfy declared clean competence gates in the standard suite. | Unique clean scenarios by environment and agent. | Verified standard run, competence report, scenario manifests, metric records, run manifest checksum. | pending |
| C002 | Shift changes safe-success and unsafe-proposal outcomes relative to matched clean scenarios. | Matched within-scenario effects. | Pair table, paired-bootstrap intervals, sample hierarchy, analysis config/seed, verified run. | pending |
| C003 | Hard-gate oversight prevents some unsafe proposed actions while imposing measurable unnecessary blocks and coverage cost. | Counterfactual-eligible proposed actions clustered by scenario. | Monitor evaluation, raw confusion counts, utility/cost table, Pareto frontier, interval metadata. | pending |
| C004 | Detector quality differs by monitor, environment, fault, severity, agent, oversight treatment, and threshold. | Counterfactual-eligible monitor events within scenario clusters. | Full monitor threshold table with TP/FP/TN/FN and dimensions; insufficiency flags. | pending |
| C005 | Standard-suite results reproduce byte-for-byte for canonical nonvolatile artifacts. | Two independently installed standard-suite runs. | Both verified bundles, canonical comparison record, finalization hashes, rehearsal logs. | pending |
| C006 | Smoke and standard suites meet documented runtime, memory, artifact-size, and worker-scaling budgets. | Installed-distribution suite executions. | Performance JSON, platform/runtime metadata, thresholds, logs. | pending |
| C007 | Challenge split integrity is preserved and challenge outcomes were not used for tuning. | Scenario split manifests and development record. | Split-integrity report, suite manifest, progress/limitations statement. | pending |

## Checkpoint 49 evidence readiness audit

The complete-valid diagnostic run `runs/phase49-report-smoke-2` (run ID
`run_9b919ff0c2abc28f`) verifies the reporting machinery, not the pending
standard-suite claims. Its final run-manifest SHA-256 is
`d658625dc31a0fd7ad608f3c691955ac51b6da289e723f619fefe16da3d83994` and
finalization SHA-256 is
`34280ee2ed59b5c4b0505dc93a54e646ea6b25de94876b495dcabc60ba5a12c3`.

| Claim | Available checkpoint evidence | Remaining reason status is not `verified` |
|---|---|---|
| C001 | Clean competence is disclosed as passed for 28/28 completed smoke episodes. | This is not the versioned standard suite. |
| C002 | Metric-schema-v2 outcomes and matched-effect implementation exist. | The smoke has no paired-bootstrap artifact. |
| C003 | Realized gating tables expose prevented harm, unnecessary blocks, and coverage cost. | Only `record_only` ran; no hard-gate effect may be claimed. |
| C004 | The counterfactual threshold artifact has TP/FP/TN/FN, all required dimensions, denominators, and clustered interval status; artifact SHA-256 `867209efa80b04010c57f8402f90ab415a5d46feef3251fed64077191590286d`. | Standard-suite monitor treatments and final sample hierarchy are pending. |
| C005 | Canonical comparison design exists. | Two clean installed standard reproductions are pending. |
| C006 | No checkpoint evidence. | Versioned performance budgets and measurements are pending. |
| C007 | Scenario split metadata is present. | Held-out suite manifest and integrity report are pending. |

The report provenance artifact SHA-256 is
`34741a6ac10a6414288694d21d7a250dc43ca48a53cd2a7b7331fb2223bcc591`.
It records formulas, raw counts, metric schema, clean competence, executed
treatments, uncertainty status, and the embedded source manifest. It cannot
promote a pending claim by itself.

## Historical checked-in material

The tracked root `results/`, `figures/`, `docs/experimental_report.md`, and
`docs/analysis_report.md` predate the current Phase 5B/6 evidence contracts.
They are not valid sources for C001–C007 and must not be cited as current
headline evidence. Unsupported legacy claims and version references will be
removed or explicitly labeled historical during Checkpoint 49.

## Required evidence link fields

Each completed ledger row will record:

- run directory and authoritative run ID;
- `run_manifest.json` and `finalization.json` SHA-256 values;
- verification status and verifier artifact;
- metric schema/version, formula ID, numerator, denominator, and unit;
- planned, started, completed, failed, incomplete, eligible-step, independent
  scenario, seed, and condition counts as applicable;
- point estimate, interval bounds/method, analysis seed, and correction method;
- competence-gate result and executed treatment manifest;
- exact report table/plot path and its manifest checksum.
