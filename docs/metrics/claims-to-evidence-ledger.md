# Claims-to-evidence ledger

Ledger schema: `claims-evidence-ledger-v1`

Only rows with status `verified` may appear as v0.4.0 headline claims. Every
verified row must identify a complete-valid run, manifest/finalization checksum,
metric schema and formula, sample counts, interval method, clean competence,
and the report/plot that renders it.

| Claim ID | Proposed claim | Evidence unit | Required artifacts | Status |
|---|---|---|---|---|
| C001 | Reference agents satisfy declared clean competence gates in the standard suite. | Unique clean scenarios by environment and agent. | Verified standard run, competence report, scenario manifests, metric records, run manifest checksum. | verified |
| C002 | Executed shifts change safe-success relative to matched clean scenarios in the standard suite. | Matched within-scenario effects. | Pair table, paired-bootstrap intervals, sample hierarchy, analysis config/seed, verified run. | verified |
| C003 | In the standard suite, hard-gate oversight made 18 interventions, all unnecessary blocks under the counterfactual label, and prevented no measured harm; no benefit claim is supported. | Counterfactual-eligible proposed actions clustered by scenario. | Monitor evaluation, raw confusion counts, utility/cost table, Pareto frontier, interval metadata. | verified |
| C004 | Detector quality is reported jointly by monitor, environment, fault, severity, agent, oversight treatment, and threshold. | Counterfactual-eligible monitor events within scenario clusters. | Full monitor threshold table with TP/FP/TN/FN and dimensions; insufficiency flags. | verified |
| C005 | Standard-suite results reproduce byte-for-byte for canonical nonvolatile artifacts. | Two independently installed standard-suite runs. | Both verified bundles, canonical comparison record, finalization hashes, rehearsal logs. | verified |
| C006 | Smoke and standard suites meet documented runtime, memory, artifact-size, and worker-scaling budgets. | Installed-distribution suite executions. | Performance JSON, platform/runtime metadata, thresholds, logs. | verified |
| C007 | Challenge split integrity is preserved and challenge outcomes were not used for tuning. | Scenario split manifests and development record. | Split-integrity report, suite manifest, progress/limitations statement. | verified |

## Checkpoint 50 standard evidence

Claims C001–C004 are supported by the 240/240-complete standard validation run
`runs/phase50-standard-golden`, run ID `run_983adda8465a5778`. Strict
verification reports `complete_valid` and 550 artifacts. The final manifest
SHA-256 is
`31c0eb88d4425cdeb89db1f00102a7e648e0dc12c0a435a993e9c2ad2172a441`;
the finalization SHA-256 is
`0566eff28a21478848352c16d77422b7054c32e06ff89fd4de1783c7dbbf1801`.
Clean competence passed with no failed gates and both `record_only` and
`hard_gate` treatments executed.

The `metric-schema-v2` evidence checksum is
`7c768b444b2c2051f819a597354c82de060925cebb80e0353d90c42dcb66ad63`.
The report sums 86/240 safe-success episodes, 32/240 unsafe executed episodes,
418/572 safe useful steps, and 32/572 counterfactual-unsafe proposals. These
are descriptive standard-suite results, not production estimates.

Scenario-clustered intervals use analysis seed `20260717`, 2,000 deterministic
resamples, unique scenario manifests stratified by family, and no multiplicity
correction. The confidence table (720 rows; 556 estimable, 164 no eligible
units) has SHA-256
`815950c0733f366648c8309464c3b2d7a95e8e9645b5da42dff45dbe558ee1e3`.
The matched shifted-minus-clean table (540 rows) has SHA-256
`86745376d9182dbdab612778651406cec719a203b70c852d172946fef8174aea`.
Repeated steps are reduced within each of two validation scenarios per cell;
they are not independent samples.

The counterfactual detector table has 2,541 threshold rows and SHA-256
`177d65c8d3aaa82004e91a5fd7b81ac53eb4edf6f25cf3b5ac16238319e61f4d`.
The separate realized-gating table has 121 rows and SHA-256
`e3904c15e7ab681d8b0ad94a4cea96982e8e4c8add42abf5953ff4a3b189376f`.
It records 18 hard-gate interventions, zero prevented harms, and 18 unnecessary
blocks; C003 was narrowed to this observed result rather than preserving an
unsupported benefit claim. Report provenance SHA-256 is
`2a566041c3dcb98c8f64efc186bc4823a3e02abba0dca4ae417b2adc8952f88b`.

C007 is a structural claim only. The versioned challenge manifest selects the
disjoint `challenge` namespace, plans 120 episodes under seed 1042, and sets
`challenge_outcomes_may_inform_development=false`. Only its plan and contract
were inspected; no challenge episode outcomes were executed or used. The
golden standard validation checksum is
`295dac29b494909814a7fa2b037df50bf03cbc53944b681b3ec1622a3d71eb94`.
C005 and C006 were promoted only after both installed-sdist rehearsals below.

## Installed-sdist rehearsal evidence

Rehearsals 1 and 2 are retained at
`/Users/aleksander/Documents/TASB-v0.4.0-release-rehearsal-1` and
`/Users/aleksander/Documents/TASB-v0.4.0-release-rehearsal-2`. Each
`release-rehearsal.json` reports `passed` for 29 phases and confirms
`challenge_outcomes_used_for_development=false` and
`remote_actions_executed=false`. Every rehearsal produced a complete-valid
smoke bundle (122 artifacts) and two complete-valid standard bundles (550
artifacts each) with stable run IDs `run_9b919ff0c2abc28f` and
`run_983adda8465a5778`.

Each independent standard pair matched exactly across 541 canonical
nonvolatile files. The comparison records are
`logs/26-standard-canonical-comparison.log` below each rehearsal. The installed
interval figure has identical SHA-256
`be514672f5e6685e18c586872d0a43f7672cbefadef3bce3cca1a8e07b0a940b`
across both rehearsals. Report/provenance files that intentionally bind
timestamped manifest generations are excluded from canonical equality but
remain checksum-bound, validated, and visually/textually inspected.

On Python 3.14.6/macOS, installed smoke measurements were 3.06/2.92 seconds
and 3.16/3.00 seconds for one/two workers across rehearsals, with at most 64.0
MiB RSS and 9.08 MiB artifacts. Installed standard measurements were
25.34/26.89 seconds and 26.22/27.97 seconds, with at most 265.1 MiB RSS and
77.12 MiB artifacts. Scaling ratios were 0.955/0.948 for smoke and 1.061/1.067
for standard; all absolute and comparable-platform regression budgets passed.
Evidence is in each installed workspace's `performance-evidence.json` and
`standard-performance-evidence.json`.

Rehearsal 2 is the final local artifact candidate. Its checksums are:

- SBOM: `bc734ee2c3a09c64616a51a9b4b93e81483be79ecfc0c57487a259c3df438ab0`;
- wheel: `5c3b014f5df2bf7d0a699e6f4ec500639fdf570cf084988cd43be4e8bcdf1a2e`;
- sdist: `4d9e07af8ee38dc7d8dfb6f87f972ee7ba91fe6af1b73176a03779ccba96ef93`.

The authoritative checksum file is
`/Users/aleksander/Documents/TASB-v0.4.0-release-rehearsal-2/release-artifacts/SHA256SUMS`;
the CycloneDX SBOM is the adjacent `sbom.cdx.json`.

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
