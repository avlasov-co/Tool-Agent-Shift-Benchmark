# Methodology

Each immutable generated scenario expands into a matched clean episode and its declared shifted treatments. Every treatment runs the same multi-step environment lifecycle and agent initialization. Before each policy-visible tool call, the runner evaluates the current fault schedule, composes active faults on an internal clean response, advances the simulated clock by response latency, redacts evaluator provenance, and builds an `ObservationContext`. An agent may return an environment action, abstain, or request a bounded requery through the same scheduled channel. Monitors inspect only the same visible context, action, and shifted observation. Execution and scoring use hidden ground truth after the decision. Metrics preserve scenario-pair identity and aggregate outcomes by environment, agent, fault, configured severity, monitor composition, and oversight mode.

## Monitor ablations

`monitor-composition-v1` defines five ordered experimental treatments:
`no_monitor`, `schema_only`, `schema_plus_freshness`,
`schema_plus_freshness_plus_consistency`, and `full_composite_monitor`. The
planner crosses every requested composition with every fault treatment in a
fixed canonical order. `no_monitor` has no child checks and always allows the
proposal; the other modes add schema, freshness, consistency, constraint, and
risk checks cumulatively as declared. Monitor composition and oversight policy
are separate identity, artifact, and analysis dimensions.

## Evaluator boundary

Agents and monitors do not receive the full environment object. They receive `ObservationContext`, which exposes visible constraints, visible schema requirements, observation/response timing, and visible-only helper methods. Hidden ground truth, clean unfaulted tool responses, schedule/effect provenance, execution methods, and post-hoc unsafe labels remain evaluator-only.

## Universal fault severity

Configured fault severity must be finite and within `[0, 1]`. `0.0` is policy-equivalent to no perturbation, while evaluator provenance still records the zero realized effect. Intermediate effects are deterministic, and `1.0` is the defined maximum for that fault. Each application records configured severity separately from normalized realized magnitude under `fault-effect-v1`.

| Fault | Intermediate behavior | Maximum endpoint and exact summary |
|---|---|---|
| `normal` | No perturbation at any value | Realized magnitude `0`; reason `normal_channel` |
| `schema_drift` | Schema marker plus severity-quantized field renames | Primary payload and lifecycle renamed; `renamed_fields` and `rename_fraction` |
| `stale_observation` | `ceil(10 × severity)` ms staleness; stale value edits begin at `0.75` | 10 ms plus environment-specific stale values; `staleness_ms` and `altered_values` |
| `latency_spike` | Deterministic maximum draw multiplied by severity | Full 500–550 ms draw; `added_latency_ms` and `maximum_latency_ms` |
| `missing_field` | A severity fraction of deterministic candidate paths is removed | All candidates removed; `removed_paths`, counts, and candidate count |
| `conflicting_tool_output` | A severity fraction of top-level fields differs across sources | Second source omits all candidate fields; `conflicting_fields` and `conflict_fraction` |
| `corrupted_memory` | One to three ordered misleading claims | Three claims; `corrupted_claims` and `corruption_amount` |
| `constraint_shift` | Proportional numeric deltas plus declared thresholded categorical changes | Maximum environment-specific relaxation; exact `constraint_deltas` |
| ordered `shift_chains` | Composes any declared fault components at the scheduled severity, preserving exact order | Component effects plus input/output and policy-visible intermediate hashes |

`compound_shift` remains readable as a deprecated compatibility alias for the
historical stale → missing → conflict → latency chain. New configurations use
ordinary ordered `shift_chains`; no component order is canonicalized unless a
future mechanism supplies a proof of commutativity.

Effect details are deterministic scientific records, not policy hints. They remain in evaluator traces and episode metadata and are stripped from every agent/monitor input.

Visible validation is intentionally weaker than hidden scoring. If stale or missing observations hide a hazard, the monitor may fail to block it and the environment may still score it unsafe after execution. That separation is necessary for a meaningful shift benchmark.

## v0.1.0 extended release additions

This release includes multi-step rollouts, fault severity sweeps, a deterministic offline LLM-style fixture agent, static-vs-dynamic comparison, and multi-seed confidence intervals. The relevant files are `src/tool_agent_shift_benchmark/run_seeds.py`, `src/tool_agent_shift_benchmark/metrics/confidence.py`, packaged `seeds` config, `src/tool_agent_shift_benchmark/agents/offline_llm_fixture.py`, `src/tool_agent_shift_benchmark/resources/policies/offline_llm_policy.json`, and `tests/test_multistep_severity_confidence.py`.

Frontier LLM API integration is intentionally out of scope for v0.1.0 because the benchmark must remain open-source, reproducible, and free from paid credential requirements.
