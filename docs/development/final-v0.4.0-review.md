# Final v0.4.0 pre-release review

## Scope and baseline

- **Reviewed range:** `origin/main` (`c1572db6ca7158a00fc47ae774f0c606d76beb78`) through
  `codex/phase-6-evidence-release` (`65c12746881f053b83dcf3889bcfc02012e5e5f0`), 60 commits.
- **Baseline:** the worktree was clean before this review. `origin/main` is an
  ancestor of `HEAD`. The range contains the recorded Phase 1 through Phase 6
  checkpoints, including the Phase 6 release rehearsal records.
- **Documentation read before review:** repository instructions and plans; all
  Phase 1--6 progress and handoff records; the metric data dictionary;
  claims-to-evidence ledger; v0.4.0 migration guide; benchmark card; release
  notes; and release process.
- **Diff inspection:** 319 files, 41,640 insertions, and 4,422 deletions.
  `git diff --check origin/main...HEAD` currently fails as recorded below.

## Review method and confirmed invariants

I reviewed the cumulative design and implementation boundaries against the
release contracts, with particular attention to the following:

- semantic identity excludes operational selectors/workers while planned
  identities, scenario manifests, matched-pair identifiers, schedules, and
  treatment dimensions remain authoritative;
- metric-schema-v2 uses planned episodes or eligible records as named
  denominators, retains failed/incomplete work, uses scenario clusters rather
  than repeated steps as independent units, and makes missing pairs visible;
- monitor detector labels are proposed-action pure-counterfactual labels and
  remain separate from realized gating outcomes; calibration is restricted to
  declared probability scores;
- policy-visible inputs are frozen/redacted and plugin execution is descriptor
  validated, lazily discovered, bounded, and represented as orchestration
  failure rather than fabricated safety data;
- run bundles own artifacts, finalization binds manifests/checksums, resume
  validates scientific identity, and reports require complete-valid sources;
- release metadata, package resources, isolated install paths, and rehearsal
  documentation consistently describe v0.4.0 as synthetic-benchmark evidence,
  not a production-safety claim.

No additional high-confidence scientific-validity, trust-boundary,
reproducibility, or release-metadata defect was confirmed in this pre-fix
review. The final validation section of this document will be updated with the
post-fix command evidence.

## Findings

### F001 -- release blocker: audit requires obsolete root evidence

- **Location/symbol:** `src/tool_agent_shift_benchmark/audit.py`,
  `_artifact_consistency`.
- **Failure mode:** the check unconditionally requires
  `results/episodes.jsonl` alongside historical root artifacts. v0.4.0
  reports and claims instead require complete-valid, checksum-bound run
  bundles. Consequently a clean v0.4.0 checkout has a persistent failed audit
  diagnostic despite having no valid reason to regenerate or fabricate root
  evidence.
- **Reproducible evidence:** `make audit` records
  `generated_artifact_consistency` as failed solely because root
  `results/episodes.jsonl` is absent; `docs/metrics/claims-to-evidence-ledger.md`,
  `docs/migrations/v0.4.0.md`, and Phase 6 records require verified bundles and
  explicitly exclude root historical outputs from C001--C007 evidence.
- **Affected invariant:** current claims must be tied to complete-valid
  verified run bundles; historical artifacts must not force regeneration or be
  promoted as current evidence.
- **Smallest correct fix:** replace the root-artifact requirement with a
  read-only bundle-evidence check that validates every current verified ledger
  claim references an existing complete-valid bundle and treats incomplete
  root material as a historical diagnostic/warning, not a failed executable
  audit check.
- **Required regression tests:** a clean checkout without root
  `results/episodes.jsonl` passes the audit evidence check; stale root material
  is reported as a warning; verified claims without a complete-valid referenced
  bundle fail; and the shipped verified claim references pass.

### F002 -- release blocker: whitespace validation fails

- **Location/symbol:** `docs/development/phase-5a-plan.md`, end of file.
- **Failure mode:** a new blank line at end of file causes
  `git diff --check origin/main...HEAD` to fail.
- **Reproducible evidence:** `git diff --check origin/main...HEAD` reports
  `docs/development/phase-5a-plan.md:154: new blank line at EOF`.
- **Affected invariant:** final release validation requires a clean diff
  whitespace check.
- **Smallest correct fix:** remove the superfluous final blank line.
- **Required regression test:** the repository-wide `git diff --check` release
  validation is the applicable regression check.

## Classification summary

| Classification | Findings |
| --- | --- |
| Release blocker | F001, F002 |
| Important but non-blocking | None confirmed |
| Cleanup | None proposed |
| False positive | None recorded |

## Post-fix validation record

- Focused audit regressions: `9 passed`; Ruff lint and format-check passed.
- Full repository test suite and branch coverage passed (599 tests; 78.57%
  branch coverage).
- `make lint`, `make format-check`, `make typecheck`, byte compilation, and
  `scripts/check_docs.py` passed.
- `make audit` passed every executable check, including
  `claim_bound_evidence_consistency`; its detail records stale root material as
  a warning rather than a failure.
- Package build and isolated sdist/wheel distribution smoke passed. Strict
  `tasb verify-run` reports `complete_valid` for the retained smoke bundle
  `runs/phase49-report-smoke-2` (116 artifacts) and standard bundle
  `runs/phase50-standard-golden` (550 artifacts).
- `make verify-release` passed all 34 non-destructive phases in
  `/var/folders/1b/427nbdg92l14r0j71032l_5r0000gn/T/tasb-release-verification-ux2up8_q`.
- `git diff --check` passed after F002. A final clean-tree audit and status
  check remain the last handoff operation after this review record is amended.
