from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from tool_agent_shift_benchmark.core.serialization import register_dataclass

from .types import (
    AgentAction,
    AgentDecision,
    ExecutionResult,
    FailureCase,
    FaultConfig,
    MonitorDecision,
    Observation,
    ToolResponse,
    stable_hash,
)


@dataclass
class Episode:
    env_name: str
    scenario_id: str
    agent_name: str
    fault: FaultConfig
    seed: int
    run_id: str
    episode_id: str
    tool_response: ToolResponse
    decision: AgentDecision
    monitor_decisions: List[MonitorDecision]
    execution: ExecutionResult
    metadata: Dict[str, Any] = field(default_factory=dict)
    scenario_pair_id: str | None = None
    identity_schema_version: str = "2"
    planned_identity: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (
            ("run_id", self.run_id),
            ("scenario_id", self.scenario_id),
            ("episode_id", self.episode_id),
            ("identity_schema_version", self.identity_schema_version),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Episode":
        """Rehydrate a structured episode from a run bundle."""
        response = value["tool_response"]
        observation = Observation(**response["observation"])
        tool_response = ToolResponse(**{**response, "observation": observation})
        decision = value["decision"]
        action = AgentAction(**decision["action"])
        agent_decision = AgentDecision(**{**decision, "action": action})
        monitors = [MonitorDecision(**item) for item in value.get("monitor_decisions", [])]
        execution = ExecutionResult(**value["execution"])
        fault = FaultConfig(**value["fault"])
        identity_schema_version = str(value.get("identity_schema_version", "1"))
        episode_id = value.get("episode_id")
        if not isinstance(episode_id, str) or not episode_id:
            raise ValueError("serialized episode is missing its authoritative episode_id")
        if identity_schema_version == "1":
            expected_legacy_id = stable_hash(
                {
                    "env": value["env_name"],
                    "scenario": value["scenario_id"],
                    "agent": value["agent_name"],
                    "fault": fault.name,
                    "severity": fault.severity,
                    "seed": int(value["seed"]),
                    "run_id": value["run_id"],
                },
                prefix="ep",
            )
            if episode_id != expected_legacy_id:
                raise ValueError(f"legacy episode_id mismatch: expected {expected_legacy_id!r}, got {episode_id!r}")
        elif identity_schema_version not in {"2", "3", "4", "5", "6", "7"}:
            raise ValueError(f"unsupported episode identity schema: {identity_schema_version!r}")
        planned_identity = value.get("planned_identity", {})
        if planned_identity:
            declared = {
                "run_id": value["run_id"],
                "scenario_id": value["scenario_id"],
                "scenario_pair_id": value.get("scenario_pair_id"),
                "scenario_seed": int(value["seed"]),
                "episode_id": episode_id,
            }
            for name, actual in declared.items():
                expected = planned_identity.get(name)
                if expected != actual:
                    raise ValueError(
                        f"serialized planned identity mismatch for {name}: expected {expected!r}, got {actual!r}"
                    )
            if identity_schema_version in {"3", "4", "5", "6", "7"}:
                manifest_hash = (value.get("metadata", {}).get("scenario_manifest") or {}).get("content_hash")
                if planned_identity.get("scenario_manifest_hash") != manifest_hash:
                    raise ValueError("serialized planned identity mismatch for scenario_manifest_hash")
                if planned_identity.get("seed_streams") != value.get("metadata", {}).get("seed_streams"):
                    raise ValueError("serialized planned identity mismatch for seed_streams")
            if identity_schema_version in {"4", "5", "6", "7"}:
                schedule_ids = fault.metadata.get("schedule_ids", [])
                if planned_identity.get("fault_schedule_ids") != schedule_ids:
                    raise ValueError("serialized planned identity mismatch for fault_schedule_ids")
        return cls(
            value["env_name"],
            value["scenario_id"],
            value["agent_name"],
            fault,
            int(value["seed"]),
            value["run_id"],
            episode_id,
            tool_response,
            agent_decision,
            monitors,
            execution,
            value.get("metadata", {}),
            value.get("scenario_pair_id"),
            identity_schema_version,
            planned_identity,
        )

    def to_row(self) -> Dict[str, Any]:
        recovered = bool(self.metadata.get("recovered", False))
        return {
            "episode_id": self.episode_id,
            "run_id": self.run_id,
            "env_name": self.env_name,
            "environment": self.env_name,
            "scenario_id": self.scenario_id,
            "scenario_pair_id": self.scenario_pair_id or "",
            "scenario_manifest_hash": (self.metadata.get("scenario_manifest") or {}).get("content_hash", ""),
            "agent_name": self.agent_name,
            "agent": self.agent_name,
            "fault_name": self.fault.name,
            "fault": self.fault.name,
            "fault_severity": self.fault.severity,
            "configured_fault_severity": self.metadata.get("configured_fault_severity", self.fault.severity),
            "maximum_realized_effect_magnitude": self.metadata.get("maximum_realized_effect_magnitude", 0.0),
            "fault_effect_applications": self.metadata.get("fault_effect_applications", 0),
            "seed": self.seed,
            "action_type": self.decision.action.action_type,
            "target": self.decision.action.target or "",
            "outcome": "unsafe"
            if self.execution.unsafe
            else (
                "success" if self.execution.success else "abstained" if self.decision.action.abstain else "incomplete"
            ),
            "abstain": self.decision.action.abstain,
            "abstained": self.decision.action.abstain,
            "success": self.execution.success,
            "unsafe": self.execution.unsafe,
            "constraint_violation": self.execution.constraint_violation,
            "stale_data_action": self.execution.stale_data_action,
            "latency_ms": self.tool_response.latency_ms,
            "unsafe_reasons": ";".join(self.execution.unsafe_reasons),
            "monitor_blocked": any(not m.allow_action for m in self.monitor_decisions),
            "monitor_reasons": ";".join(r for m in self.monitor_decisions for r in m.reasons),
            "recovered": recovered,
            "episode_steps": self.metadata.get("episode_steps", 1),
            "steps_taken": self.metadata.get("steps_taken", 1),
            "multi_step": self.metadata.get("multi_step", False),
            "unsafe_step_count": self.metadata.get("unsafe_step_count", int(self.execution.unsafe)),
            "failure_step": self.metadata.get("failure_step", ""),
            "stop_reason": self.metadata.get("stop_reason", ""),
        }

    def failure_case(self) -> FailureCase:
        return FailureCase(
            case_id=stable_hash(
                {
                    "episode_id": self.episode_id,
                    "unsafe": self.execution.unsafe_reasons,
                },
                prefix="case",
            ),
            episode_id=self.episode_id,
            env_name=self.env_name,
            agent_name=self.agent_name,
            fault_name=self.fault.name,
            unsafe_reasons=list(self.execution.unsafe_reasons),
            trace=self.to_dict(),
            seed=self.seed,
        )


register_dataclass(Episode)
