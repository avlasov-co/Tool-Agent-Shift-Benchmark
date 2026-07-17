# Reproducibility

```bash
python -m venv .venv
source .venv/bin/activate
make setup
bash scripts/run_repro.sh
```

`make setup` installs the reviewed, hash-checked development resolution in
`requirements/development.txt` and then installs this checkout without asking
the resolver to select a second graph.

The runner writes seed and config metadata to `results/config.json`. Episode IDs are stable hashes of run configuration, environment, scenario, agent, fault, and seed.

## v0.4.0 evidence workflow

The current workflow uses named, complete-valid run bundles, clean-versus-shifted comparison, deterministic scenario-clustered intervals, and embedded report provenance. See `docs/artifact_manifest.md`.

Frontier LLM API integration remains out of scope for v0.4.0 evidence because the benchmark must remain open-source, reproducible, and free from paid credential requirements.
