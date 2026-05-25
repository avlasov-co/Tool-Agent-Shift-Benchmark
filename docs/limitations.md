# Limitations

The benchmark is deliberately synthetic. It models failure mechanisms, not complete real-world deployments. Agent policies are transparent baselines, not frontier LLM agents. Metrics should be interpreted as controlled comparisons, not deployment guarantees.

## Remaining evaluator-boundary limitations

The benchmark now separates visible agent/monitor inputs from hidden evaluator scoring, but it is still a compact synthetic suite. The visible action helper is a deterministic baseline scaffold, not a learned policy. The environments remain small, and hidden scoring is exact because the tasks are synthetic. These properties improve reproducibility, not external validity.

## v0.1.0 extended release additions

This release includes multi-step rollouts, fault severity sweeps, a deterministic offline LLM-style fixture agent, static-vs-dynamic comparison, and multi-seed confidence intervals. The relevant files are `src/run_seeds.py`, `src/metrics/confidence.py`, `configs/seeds.yaml`, `src/agents/offline_llm_fixture.py`, `fixtures/offline_llm_policy/policy_cases.json`, `docs/artifact_manifest.md`, and `tests/test_multistep_severity_confidence.py`.

Frontier LLM API integration is intentionally out of scope for v0.1.0 because the benchmark must remain open-source, reproducible, and free from paid credential requirements.
