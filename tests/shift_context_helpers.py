from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tool_agent_shift_benchmark.core.serialization import stable_hash
from tool_agent_shift_benchmark.core.shift_context import ShiftContext


def shift_context(environment: Any, response: Any, seed: int, *, step: int = 0) -> ShiftContext:
    """Build the same safe direct-call context used by the episode runner."""

    adapter = environment.policy_adapter(response.observation)
    lifecycle = response.observation.data.get("lifecycle")
    phase = str(lifecycle.get("phase", "unknown")) if isinstance(lifecycle, Mapping) else "unknown"
    return ShiftContext.create(
        step_index=step,
        attempt_number=1,
        public_scenario_metadata=environment.public_task_description(),
        visible_schema={
            "tool_name": response.tool_name,
            "observation_schema_version": response.observation.schema_version,
            "top_level_fields": sorted(response.observation.data),
            "required_fields": adapter.required_fields,
            "action_schema": adapter.action_schema,
        },
        timing={
            "clock_unit": "ms",
            "environment_time": environment.current_time,
            "observation_timestamp": response.observation.timestamp,
            "declared_latency_ms": response.latency_ms,
        },
        rng_seed=seed,
        fault_schedule={"schedule_id": "direct_test", "step": step},
        channel_metadata={
            "lifecycle_phase": phase,
            "visible_constraints_reference_hash": stable_hash(
                response.observation.constraints,
                prefix="constraint_reference",
            ),
            "policy_adapter_contract": adapter.contract_version,
        },
    )
