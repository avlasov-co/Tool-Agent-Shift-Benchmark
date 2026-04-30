from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List
from .types import AgentDecision, ExecutionResult, FailureCase, FaultConfig, MonitorDecision, ToolResponse, stable_hash


@dataclass
class Episode:
    env_name: str
    scenario_id: str
    agent_name: str
    fault: FaultConfig
    seed: int
    run_id: str
    tool_response: ToolResponse
    decision: AgentDecision
    monitor_decisions: List[MonitorDecision]
    execution: ExecutionResult
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.episode_id = stable_hash(
            {
                "env": self.env_name,
                "scenario": self.scenario_id,
                "agent": self.agent_name,
                "fault": self.fault.name,
                "severity": self.fault.severity,
                "seed": self.seed,
                "run_id": self.run_id,
            },
            prefix="ep",
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["episode_id"] = self.episode_id
        return d

    def to_row(self) -> Dict[str, Any]:
        recovered = bool(self.metadata.get("recovered", False))
        return {
            "episode_id": self.episode_id,
            "run_id": self.run_id,
            "env_name": self.env_name,
            "environment": self.env_name,
            "scenario_id": self.scenario_id,
            "agent_name": self.agent_name,
            "agent": self.agent_name,
            "fault_name": self.fault.name,
            "fault": self.fault.name,
            "fault_severity": self.fault.severity,
            "seed": self.seed,
            "action_type": self.decision.action.action_type,
            "target": self.decision.action.target or "",
            "outcome": "unsafe" if self.execution.unsafe else ("success" if self.execution.success else "abstained" if self.decision.action.abstain else "incomplete"),
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
            case_id=stable_hash({"episode_id": self.episode_id, "unsafe": self.execution.unsafe_reasons}, prefix="case"),
            episode_id=self.episode_id,
            env_name=self.env_name,
            agent_name=self.agent_name,
            fault_name=self.fault.name,
            unsafe_reasons=list(self.execution.unsafe_reasons),
            trace=self.to_dict(),
            seed=self.seed,
        )
