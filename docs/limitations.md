# Limitations

The benchmark is deliberately synthetic. It models failure mechanisms, not complete real-world deployments. Agent policies are transparent baselines, not frontier LLM agents. Metrics should be interpreted as controlled comparisons, not deployment guarantees.

## Remaining evaluator-boundary limitations

The benchmark now separates visible agent/monitor inputs from hidden evaluator scoring, but it is still a compact synthetic suite. The visible action helper is a deterministic baseline scaffold, not a learned policy. The environments remain small, and hidden scoring is exact because the tasks are synthetic. These properties improve reproducibility, not external validity.

## v0.4.0 evidence limitations

The current design includes multi-step rollouts, fault severity sweeps, a deterministic offline fixture, clean-versus-shifted comparison, and scenario-clustered intervals. Small independent-scenario counts can still make narrow cells inestimable.

Frontier LLM API integration remains out of scope for v0.4.0 evidence because the benchmark must remain open-source, reproducible, and free from paid credential requirements.
