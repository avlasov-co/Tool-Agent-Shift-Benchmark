# Agent and Monitor Boundary

The benchmark now passes agents and monitors an `ObservationContext`, not the full synthetic environment object.

This is a benchmark-validity guardrail. Each environment now supplies a
versioned `environment-policy-adapter-v1`; `ObservationContext` delegates only
the adapter's documented safe capabilities and contains no environment-name
dispatch. Agents and monitors can inspect only:

- the current environment name (not the authoritative scenario or split id);
- the visible observation returned by the tool after fault injection;
- visible constraints attached to that observation;
- the environment-provided action schema and visible schema requirements;
- the benchmark's current timestamp;
- visible candidate extraction, safe abstention, and helper methods that
  recommend or validate actions using visible observation data only.

They cannot access:

- `hidden_ground_truth()`;
- `execute()`;
- unfaulted `tool_response()` calls after a fault has been applied;
- private environment fields such as hidden protected files, hidden meetings, or hidden market state;
- post-hoc unsafe labels or metric outputs.

## Why this matters

The evaluator owns hidden ground truth. The policy being evaluated should not see it, otherwise the benchmark measures leakage, not robustness. A real deployed tool agent usually sees a tool response, task constraints, timestamps, and maybe schema metadata. It does not get a perfect clean copy of the world after the shifted observation has already failed.

## Visible validation vs hidden scoring

`ObservationContext.validate_action(...)` performs visible-only checks through
the environment's policy adapter. It can catch things visible in the
observation, such as a visible protected file flag, visible working-hours
mismatch, or visible risk-limit violation. It intentionally cannot catch
hidden-only hazards. Adapters contain immutable public task/configuration data;
they do not retain the environment or expose execution/evaluator methods.

The synthetic environment still performs hidden scoring through `execute(...)` after the agent decision. That is where evaluator-only facts are allowed to determine whether an action was unsafe.

This means a monitor may allow an action that looks safe from visible data, while the hidden evaluator later marks it unsafe. That is not a bug. That is the point of testing agents under stale, missing, conflicting, or shifted observations.

## Regression coverage

`tests/test_context.py` checks that the context exposes no hidden evaluator
methods and that all agents and monitors run through the visible-only context.
`tests/test_environment_policy_adapters.py` proves all first-party environments
provide the generic adapter and a new plugin environment participates without a
central dispatch change. `tests/test_agents.py` also checks that the retry
baseline no longer bypasses a fault by calling a clean `tool_response()` after
the shifted observation is received.

## Fault-label redaction

Fault injectors may store evaluator provenance in `observation.metadata["faults"]` so reports can explain what happened after evaluation. `redact_response_for_policy()` removes those labels before agent or monitor decisions. Tests cover both the redaction function and runner-level policy inputs.

## Shift boundary

Shift plugins receive the policy-visible `ToolResponse` and immutable
`shift-context-v1`, never the environment. The context exposes only the
step/attempt, public scenario metadata, visible schema, declared timing,
deterministic component-local RNG, active fault schedule, and explicitly
allowed channel metadata. It has no evaluator, execution, ground-truth,
filesystem, network, or credential handle. Scientific identity and schedule
provenance record the context schema version.

`tests/test_shift_context.py` exercises this boundary with a malicious shift
that probes former authority and attempts nested and top-level mutation.
# Runtime boundary implementation

The runtime enforces the boundary through `ObservationContext`, `redact_response_for_policy`, `PolicyTraceVisible`, and `EvaluatorTrace`. Agents and monitors receive only the policy-visible response/context; hidden oracle values and shift provenance are emitted by `HiddenStateEvaluator` into evaluator traces and never enter the policy trace.
