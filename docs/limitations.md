# Limitations

The benchmark is deliberately synthetic. It models failure mechanisms, not complete real-world deployments. Agent policies are transparent baselines, not frontier LLM agents. Metrics should be interpreted as controlled comparisons, not deployment guarantees.

## v0.1.0 extended release additions

This release includes multi-step rollouts, fault severity sweeps, a deterministic offline LLM-style fixture agent, static-vs-dynamic comparison, and multi-seed confidence intervals. The relevant files are `src/run_seeds.py`, `src/metrics/confidence.py`, `configs/seeds.yaml`, `src/agents/offline_llm_fixture.py`, `fixtures/offline_llm_policy/policy_cases.json`, and `tests/test_multistep_severity_confidence.py`.

Frontier LLM API integration is intentionally out of scope for v0.1.0 because the benchmark must remain open-source, reproducible, and free from paid credential requirements.
