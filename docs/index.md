# Reviewer guide

## Start here

1. `docs/metrics/metric-data-dictionary.md` — normative outcomes and denominators.
2. `docs/metrics/claims-to-evidence-ledger.md` — claim status and evidence links.
3. `docs/artifact_manifest.md` — run-bundle artifact families.
4. `docs/analysis_layer.md` — detector, gating, calibration, utility, and reports.
5. `docs/paper.md` and `docs/eval_card.md` — research framing and limitations.
6. `docs/development/phase-6-progress.md` — implementation and validation record.

## Reviewer workflow

```bash
tasb validate-config small
tasb run --config small --seed 42 --run-name review-smoke
tasb analyze --run runs/review-smoke
tasb plot --run runs/review-smoke
tasb report --run runs/review-smoke --html
tasb verify-run --strict runs/review-smoke
```

Inspect `run_manifest.json`, `finalization.json`, metric evidence, scenario
manifests, statistical status, clean competence, and report provenance. Do not
use root historical outputs as v0.4.0 evidence.

## Safety boundary

The benchmark is synthetic and non-operational. Agents and monitors cannot see
hidden evaluator state. A complete-valid bundle establishes artifact integrity
and lifecycle consistency, not production safety.
