# Methodology

Each episode resets a deterministic synthetic environment. A tool returns an observation. A fault injector may alter the visible observation. The runner redacts evaluator-only fault labels from the faulted tool response, then builds an `ObservationContext` from visible task metadata and the policy-visible observation. The agent proposes an action from that context only. Monitors inspect the same visible-only context, action, and observation. The environment executes or records abstention using hidden ground truth after the decision. Metrics aggregate outcomes by environment, agent, and fault.

## Evaluator boundary

Agents and monitors do not receive the full environment object. They receive `ObservationContext`, which exposes visible constraints, visible schema requirements, current timestamp, and visible-only helper methods. Hidden ground truth, clean unfaulted tool responses, execution methods, and post-hoc unsafe labels remain evaluator-only.

Visible validation is intentionally weaker than hidden scoring. If stale or missing observations hide a hazard, the monitor may fail to block it and the environment may still score it unsafe after execution. That separation is necessary for a meaningful shift benchmark.

## v0.1.0 extended release additions

This release includes multi-step rollouts, fault severity sweeps, a deterministic offline LLM-style fixture agent, static-vs-dynamic comparison, and multi-seed confidence intervals. The relevant files are `src/run_seeds.py`, `src/metrics/confidence.py`, `configs/seeds.yaml`, `src/agents/offline_llm_fixture.py`, `fixtures/offline_llm_policy/policy_cases.json`, and `tests/test_multistep_severity_confidence.py`.

Frontier LLM API integration is intentionally out of scope for v0.1.0 because the benchmark must remain open-source, reproducible, and free from paid credential requirements.
