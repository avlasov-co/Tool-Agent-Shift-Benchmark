# Historical generated report placeholder

The former report in this root path predated metric-schema-v2, scenario-clustered
uncertainty, counterfactual monitor labels, and verified report provenance. Its
numeric claims were removed.

Generate a current evidence-bearing report inside a named run bundle:

```bash
tasb report --run runs/<name> --html
tasb verify-run --strict runs/<name>
```

Current reports are written below `runs/<name>/reports/` and include a verified
source snapshot, checksums, metric formulas, sample counts, uncertainty status,
clean competence, and executed-treatment disclosure.
