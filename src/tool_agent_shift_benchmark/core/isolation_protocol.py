"""Typed values for the bounded plugin subprocess protocol.

The wire format deliberately avoids pickle and arbitrary object reconstruction.
Only benchmark contract records and JSON values cross the process boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.core.counterfactual import (
    CounterfactualInterventionScore,
    PureActionScore,
    RealizedOutcomeScore,
)
from tool_agent_shift_benchmark.core.fault_channels import FaultChannelDescriptor
from tool_agent_shift_benchmark.core.memory import MemoryEntry, MemoryOperation, MemoryWrite, PolicyMemoryView
from tool_agent_shift_benchmark.core.policy_adapter import BasePolicyAdapter
from tool_agent_shift_benchmark.core.scenarios import ScenarioFamilyDescriptor, ScenarioSpec
from tool_agent_shift_benchmark.core.shift_context import ShiftContext
from tool_agent_shift_benchmark.core.types import (
    AgentAction,
    AgentDecision,
    ExecutionResult,
    MonitorDecision,
    Observation,
    ToolResponse,
)

PLUGIN_RPC_CONTRACT = "plugin-rpc-v1"
TYPE_KEY = "__tasb_type__"


class ProtocolValueError(ValueError):
    """A value is outside the public subprocess wire contract."""


def _record(tag: str, value: Any) -> dict[str, Any]:
    return {TYPE_KEY: tag, "value": encode_value(value.to_dict())}


def encode_value(value: Any, *, result_handles: Callable[[object], Mapping[str, Any]] | None = None) -> Any:
    """Encode a supported benchmark value into strict JSON-compatible data."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, ObservationContext):
        return {TYPE_KEY: "ObservationContext", "value": encode_value(value.to_dict())}
    if isinstance(value, Observation):
        return _record("Observation", value)
    if isinstance(value, ToolResponse):
        return _record("ToolResponse", value)
    if isinstance(value, AgentAction):
        return _record("AgentAction", value)
    if isinstance(value, AgentDecision):
        return _record("AgentDecision", value)
    if isinstance(value, MonitorDecision):
        return _record("MonitorDecision", value)
    if isinstance(value, ExecutionResult):
        return _record("ExecutionResult", value)
    if isinstance(value, MemoryWrite):
        return _record("MemoryWrite", value)
    if isinstance(value, MemoryOperation):
        return _record("MemoryOperation", value)
    if isinstance(value, MemoryEntry):
        return _record("MemoryEntry", value)
    if isinstance(value, PolicyMemoryView):
        return _record("PolicyMemoryView", value)
    if isinstance(value, ShiftContext):
        return _record("ShiftContext", value)
    if isinstance(value, ScenarioFamilyDescriptor):
        return _record("ScenarioFamilyDescriptor", value)
    if isinstance(value, ScenarioSpec):
        return _record("ScenarioSpec", value)
    if isinstance(value, FaultChannelDescriptor):
        return _record("FaultChannelDescriptor", value)
    if isinstance(value, PureActionScore):
        return _record("PureActionScore", value)
    if isinstance(value, RealizedOutcomeScore):
        return _record("RealizedOutcomeScore", value)
    if isinstance(value, CounterfactualInterventionScore):
        return _record("CounterfactualInterventionScore", value)
    if isinstance(value, Mapping):
        encoded: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProtocolValueError("plugin protocol mappings require string keys")
            encoded[key] = encode_value(item, result_handles=result_handles)
        return encoded
    if isinstance(value, (list, tuple)):
        return [encode_value(item, result_handles=result_handles) for item in value]
    if result_handles is not None:
        return dict(result_handles(value))
    raise ProtocolValueError(f"unsupported plugin protocol value: {type(value).__module__}.{type(value).__qualname__}")


def _plain(value: Any, callback: Callable[[str, tuple[Any, ...], dict[str, Any]], Any] | None) -> Any:
    return decode_value(value, callback=callback)


def _mapping(value: Any, callback: Callable[[str, tuple[Any, ...], dict[str, Any]], Any] | None) -> dict[str, Any]:
    decoded = _plain(value, callback)
    if not isinstance(decoded, dict):
        raise ProtocolValueError("typed plugin protocol record must contain a mapping")
    return decoded


class CallbackPolicyAdapter(BasePolicyAdapter):
    """Worker-side adapter whose pure helpers call the parent-side visible adapter."""

    def __init__(
        self,
        payload: Mapping[str, Any],
        callback: Callable[[str, tuple[Any, ...], dict[str, Any]], Any],
    ) -> None:
        super().__init__(
            environment_name=str(payload["environment_name"]),
            required_fields=tuple(str(item) for item in payload["required_fields"]),
            constraints=payload["constraints"],
            task_metadata=payload["task_metadata"],
            action_schema=payload["action_schema"],
            capabilities=tuple(str(item) for item in payload["capabilities"]),
        )
        object.__setattr__(self, "_callback", callback)

    def visible_candidates(self, observation: Observation) -> tuple[Mapping[str, Any], ...]:
        return tuple(self._callback("visible_candidates", (observation,), {}))

    def validate_observation_data(self, data: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(self._callback("validate_observation_data", (data,), {}))

    def validate_action(
        self, action: AgentAction, observation: Observation | None = None
    ) -> tuple[bool, tuple[str, ...]]:
        allowed, reasons = self._callback("validate_action", (action, observation), {})
        return bool(allowed), tuple(str(reason) for reason in reasons)

    def abstain(self, reason: str) -> AgentAction:
        return self._callback("abstain", (reason,), {})

    def recommend_action(self, data: Mapping[str, Any]) -> AgentAction:
        return self._callback("recommended_action", (data,), {})


def decode_value(
    value: Any,
    *,
    callback: Callable[[str, tuple[Any, ...], dict[str, Any]], Any] | None = None,
    remote_handle: Callable[[Mapping[str, Any]], Any] | None = None,
) -> Any:
    """Decode only values declared by :func:`encode_value`."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return tuple(decode_value(item, callback=callback, remote_handle=remote_handle) for item in value)
    if not isinstance(value, dict):
        raise ProtocolValueError("plugin protocol value must be JSON-compatible")
    tag = value.get(TYPE_KEY)
    if tag is None:
        return {
            str(key): decode_value(item, callback=callback, remote_handle=remote_handle) for key, item in value.items()
        }
    if set(value) != {TYPE_KEY, "value"}:
        raise ProtocolValueError(f"malformed typed plugin protocol value for {tag!r}")
    if tag == "RemoteHandle":
        if remote_handle is None:
            raise ProtocolValueError("remote handle is not valid in this protocol direction")
        payload = _mapping(value["value"], callback)
        return remote_handle(payload)
    payload = _mapping(value["value"], callback)
    if tag == "Observation":
        return Observation(**payload)
    if tag == "ToolResponse":
        return ToolResponse(
            payload["tool_name"],
            bool(payload["ok"]),
            Observation(**payload["observation"]),
            int(payload["latency_ms"]),
            tuple(payload["errors"]),
            payload["metadata"],
        )
    if tag == "AgentAction":
        return AgentAction(**payload)
    if tag == "MemoryWrite":
        return MemoryWrite(**payload)
    if tag == "MemoryOperation":
        return MemoryOperation(**payload)
    if tag == "MemoryEntry":
        return MemoryEntry(**payload)
    if tag == "PolicyMemoryView":
        entries = tuple(MemoryEntry(**item) for item in payload["entries"])
        return PolicyMemoryView(payload["contract"], int(payload["revision"]), entries, payload["view_hash"])
    if tag == "AgentDecision":
        return AgentDecision(
            payload["agent_name"],
            AgentAction(**payload["action"]),
            float(payload["confidence"]),
            tuple(payload["reasons"]),
            payload["metadata"],
            tuple(MemoryWrite(**item) for item in payload.get("memory_writes", ())),
            tuple(MemoryOperation(**item) for item in payload.get("memory_operations", ())),
        )
    if tag == "MonitorDecision":
        return MonitorDecision(
            payload["monitor_name"],
            bool(payload["allow_action"]),
            float(payload["risk_score"]),
            tuple(payload["reasons"]),
            payload["metadata"],
        )
    if tag == "ExecutionResult":
        return ExecutionResult(
            bool(payload["success"]),
            bool(payload["unsafe"]),
            bool(payload["constraint_violation"]),
            bool(payload["stale_data_action"]),
            tuple(payload["unsafe_reasons"]),
            payload["metadata"],
        )
    if tag == "ShiftContext":
        return ShiftContext(**payload)
    if tag == "ScenarioFamilyDescriptor":
        return ScenarioFamilyDescriptor.from_dict(payload)
    if tag == "ScenarioSpec":
        return ScenarioSpec.from_dict(payload)
    if tag == "FaultChannelDescriptor":
        return FaultChannelDescriptor(**payload)
    if tag == "PureActionScore":
        return PureActionScore(
            payload["contract"],
            payload["status"],
            payload["action_hash"],
            payload["state_hash"],
            payload["success"],
            payload["unsafe"],
            payload["constraint_violation"],
            payload["stale_data_action"],
            tuple(payload["unsafe_reasons"]),
            payload["score_hash"],
        )
    if tag == "RealizedOutcomeScore":
        return RealizedOutcomeScore(
            payload["action_hash"],
            bool(payload["success"]),
            bool(payload["unsafe"]),
            bool(payload["constraint_violation"]),
            bool(payload["stale_data_action"]),
            tuple(payload["unsafe_reasons"]),
            payload["outcome_hash"],
        )
    if tag == "CounterfactualInterventionScore":
        proposed = decode_value({TYPE_KEY: "PureActionScore", "value": payload["proposed_action"]})
        executed = decode_value({TYPE_KEY: "PureActionScore", "value": payload["executed_action"]})
        realized = decode_value({TYPE_KEY: "RealizedOutcomeScore", "value": payload["realized_outcome"]})
        return CounterfactualInterventionScore(
            payload["contract"],
            int(payload["sequence"]),
            proposed,
            executed,
            realized,
            bool(payload["monitor_evaluated"]),
            payload["monitor_predicted_unsafe"],
            payload["proposed_action_risk_label"],
            payload["intervention_effect"],
            payload["execution_equivalent"],
        )
    if tag == "ObservationContext":
        if callback is None:
            raise ProtocolValueError("observation context requires a callback channel")
        adapter_payload = payload["policy_adapter"]
        adapter = CallbackPolicyAdapter(adapter_payload, callback)
        memory_payload = payload.get("memory")
        memory = None
        if memory_payload is not None:
            entries = tuple(MemoryEntry(**item) for item in memory_payload["entries"])
            memory = PolicyMemoryView(
                memory_payload["contract"],
                int(memory_payload["revision"]),
                entries,
                memory_payload["view_hash"],
            )
        return ObservationContext(
            adapter,
            int(payload["current_time"]),
            int(payload["observation_timestamp"]),
            int(payload["response_latency_ms"]),
            int(payload["response_received_at"]),
            memory,
        )
    raise ProtocolValueError(f"unknown typed plugin protocol value: {tag!r}")
