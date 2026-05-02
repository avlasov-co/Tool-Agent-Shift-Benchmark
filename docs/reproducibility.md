# Reproducibility

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash scripts/run_repro.sh
```

The runner writes seed and config metadata to `results/config.json`. Episode IDs are stable hashes of run configuration, environment, scenario, agent, fault, and seed.

## v0.1.0 extended release additions

This release includes multi-step rollouts, fault severity sweeps, a deterministic offline LLM-style fixture agent, static-vs-dynamic comparison, and multi-seed confidence intervals. The relevant files are `src/run_seeds.py`, `src/metrics/confidence.py`, `configs/seeds.yaml`, `src/agents/offline_llm_fixture.py`, `fixtures/offline_llm_policy/policy_cases.json`, `docs/artifact_manifest.md`, and `tests/test_multistep_severity_confidence.py`.

Frontier LLM API integration is intentionally out of scope for v0.1.0 because the benchmark must remain open-source, reproducible, and free from paid credential requirements.
