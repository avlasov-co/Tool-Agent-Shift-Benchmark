from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from tool_agent_shift_benchmark.core.action_records import EPISODE_RECORD_VERSION, ActionRecord
from tool_agent_shift_benchmark.core.memory import MemoryOperation, MemoryWrite
from tool_agent_shift_benchmark.core.serialization import canonicalize, register_dataclass

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
    episode_record_version: str = "2"
    action_records: List[ActionRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name, value in (
            ("run_id", self.run_id),
            ("scenario_id", self.scenario_id),
            ("episode_id", self.episode_id),
            ("identity_schema_version", self.identity_schema_version),
            ("episode_record_version", self.episode_record_version),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if self.episode_record_version == EPISODE_RECORD_VERSION and not self.action_records:
            raise ValueError("episode record v3 requires at least one action record")

    def to_dict(self) -> Dict[str, Any]:
        normalized = canonicalize(self)
        if not isinstance(normalized, dict):
            raise RuntimeError("episode did not normalize to a mapping")
        return normalized

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Episode":
        """Rehydrate a structured episode from a run bundle."""
        response = value["tool_response"]
        observation = Observation(**response["observation"])
        tool_response = ToolResponse(**{**response, "observation": observation})
        decision = value["decision"]
        action = AgentAction(**decision["action"])
        memory_writes = tuple(MemoryWrite(**item) for item in decision.get("memory_writes", ()))
        memory_operations = tuple(MemoryOperation(**item) for item in decision.get("memory_operations", ()))
        agent_decision = AgentDecision(
            **{
                **decision,
                "action": action,
                "memory_writes": memory_writes,
                "memory_operations": memory_operations,
            }
        )
        monitors = [MonitorDecision(**item) for item in value.get("monitor_decisions", [])]
        execution = ExecutionResult(**value["execution"])
        fault = FaultConfig(**value["fault"])
        episode_record_version = str(value.get("episode_record_version", "2"))
        if episode_record_version not in {"2", EPISODE_RECORD_VERSION}:
            raise ValueError(f"unsupported episode record version: {episode_record_version!r}")
        action_records = [ActionRecord.from_dict(item) for item in value.get("action_records", [])]
        if not action_records:
            if episode_record_version == EPISODE_RECORD_VERSION:
                raise ValueError("episode record v3 is missing action_records")
            legacy_monitor = (
                monitors[-1]
                if monitors
                else MonitorDecision(
                    "legacy_unrecorded_monitor",
                    True,
                    0.0,
                    [],
                    {"legacy_reconstructed": True},
                )
            )
            action_records = [
                ActionRecord.from_legacy(
                    agent_decision,
                    legacy_monitor,
                    execution,
                    str(value.get("metadata", {}).get("stop_reason", "legacy_unknown")),
                )
            ]
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
        elif identity_schema_version not in {
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
            "17",
            "18",
            "19",
        }:
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
            if identity_schema_version in {
                "3",
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                "10",
                "11",
                "12",
                "13",
                "14",
                "15",
                "16",
                "17",
                "18",
                "19",
            }:
                manifest_hash = (value.get("metadata", {}).get("scenario_manifest") or {}).get("content_hash")
                if planned_identity.get("scenario_manifest_hash") != manifest_hash:
                    raise ValueError("serialized planned identity mismatch for scenario_manifest_hash")
                if planned_identity.get("seed_streams") != value.get("metadata", {}).get("seed_streams"):
                    raise ValueError("serialized planned identity mismatch for seed_streams")
            if identity_schema_version in {
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                "10",
                "11",
                "12",
                "13",
                "14",
                "15",
                "16",
                "17",
                "18",
                "19",
            }:
                schedule_ids = fault.metadata.get("schedule_ids", [])
                if planned_identity.get("fault_schedule_ids") != schedule_ids:
                    raise ValueError("serialized planned identity mismatch for fault_schedule_ids")
            if identity_schema_version in {"12", "13", "14", "15", "16", "17", "18", "19"} and planned_identity.get(
                "monitor_mode"
            ) != value.get("metadata", {}).get("monitor_mode"):
                raise ValueError("serialized planned identity mismatch for monitor_mode")
            if identity_schema_version in {"13", "14", "15", "16", "17", "18", "19"} and planned_identity.get(
                "oversight_mode"
            ) != value.get("metadata", {}).get("oversight_mode"):
                raise ValueError("serialized planned identity mismatch for oversight_mode")
        return cls(
            env_name=value["env_name"],
            scenario_id=value["scenario_id"],
            agent_name=value["agent_name"],
            fault=fault,
            seed=int(value["seed"]),
            run_id=value["run_id"],
            episode_id=episode_id,
            tool_response=tool_response,
            decision=agent_decision,
            monitor_decisions=monitors,
            execution=execution,
            metadata=value.get("metadata", {}),
            scenario_pair_id=value.get("scenario_pair_id"),
            identity_schema_version=identity_schema_version,
            planned_identity=planned_identity,
            episode_record_version=episode_record_version,
            action_records=action_records,
        )

    def to_row(self) -> Dict[str, Any]:
        recovered = bool(self.metadata.get("recovered", False))
        final_record = self.action_records[-1] if self.action_records else None
        proposed_action = final_record.proposed_action if final_record else None
        executed_action = final_record.executed_action if final_record else None
        intervention = final_record.intervention if final_record else None
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
            "action_type": executed_action.action_type if executed_action else self.decision.action.action_type,
            "target": (executed_action.target if executed_action else self.decision.action.target) or "",
            "proposed_action_type": proposed_action.action_type
            if proposed_action
            else self.decision.action.action_type,
            "proposed_target": (proposed_action.target if proposed_action else self.decision.action.target) or "",
            "executed_action_type": executed_action.action_type
            if executed_action
            else self.decision.action.action_type,
            "executed_target": (executed_action.target if executed_action else self.decision.action.target) or "",
            "intervention_type": intervention.intervention_type if intervention else "legacy_unknown",
            "outcome": "unsafe"
            if self.execution.unsafe
            else (
                "success"
                if self.execution.success
                else "abstained"
                if (executed_action.abstain if executed_action else self.decision.action.abstain)
                else "incomplete"
            ),
            "abstain": executed_action.abstain if executed_action else self.decision.action.abstain,
            "abstained": executed_action.abstain if executed_action else self.decision.action.abstain,
            "proposed_abstain": proposed_action.abstain if proposed_action else self.decision.action.abstain,
            "success": self.execution.success,
            "unsafe": self.execution.unsafe,
            "constraint_violation": self.execution.constraint_violation,
            "stale_data_action": self.execution.stale_data_action,
            "latency_ms": self.tool_response.latency_ms,
            "unsafe_reasons": ";".join(self.execution.unsafe_reasons),
            "monitor_blocked": intervention.blocked
            if intervention
            else any(not m.allow_action for m in self.monitor_decisions),
            "monitor_reasons": ";".join(r for m in self.monitor_decisions for r in m.reasons),
            "monitor_mode": self.metadata.get("monitor_mode", "full_composite_monitor"),
            "oversight_mode": self.metadata.get("oversight_mode", "gate"),
            "recovered": recovered,
            "episode_steps": self.metadata.get("episode_steps", 1),
            "steps_taken": self.metadata.get("steps_taken", 1),
            "multi_step": self.metadata.get("multi_step", False),
            "unsafe_step_count": self.metadata.get("unsafe_step_count", int(self.execution.unsafe)),
            "failure_step": self.metadata.get("failure_step", ""),
            "stop_reason": self.metadata.get("stop_reason", ""),
            "episode_record_version": self.episode_record_version,
            "action_record_contract": final_record.contract if final_record else "legacy",
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
