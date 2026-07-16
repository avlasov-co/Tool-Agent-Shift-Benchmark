"""Immutable proposed-through-evaluated action records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from tool_agent_shift_benchmark.core.serialization import canonicalize, register_dataclass, stable_hash
from tool_agent_shift_benchmark.core.types import (
    AgentAction,
    AgentDecision,
    ExecutionResult,
    MonitorDecision,
)

ACTION_RECORD_CONTRACT = "action-record-v1"
EPISODE_RECORD_VERSION = "3"


def _freeze(value: Any) -> Any:
    normalized = canonicalize(value)
    if isinstance(normalized, dict):
        return MappingProxyType({key: _freeze(item) for key, item in normalized.items()})
    if isinstance(normalized, list):
        return tuple(_freeze(item) for item in normalized)
    return normalized


@dataclass(frozen=True)
class ActionSnapshot:
    action_type: str
    target: str | None
    params: Mapping[str, Any]
    abstain: bool
    reason: str
    action_hash: str

    def __post_init__(self) -> None:
        if not self.action_type or not self.action_hash.startswith("action_"):
            raise ValueError("action snapshot requires a type and authoritative hash")
        object.__setattr__(self, "params", _freeze(self.params))

    @classmethod
    def from_action(cls, action: AgentAction) -> "ActionSnapshot":
        payload = action.to_dict()
        return cls(
            action.action_type,
            action.target,
            action.params,
            action.abstain,
            action.reason,
            stable_hash(payload, prefix="action"),
        )

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)


@dataclass(frozen=True)
class ProposedDecisionRecord:
    agent_name: str
    confidence: float
    decision_hash: str

    def __post_init__(self) -> None:
        if not self.agent_name or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("proposed decision identity and confidence must be valid")
        if not self.decision_hash.startswith("decision_"):
            raise ValueError("proposed decision requires an authoritative hash")

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)


@dataclass(frozen=True)
class PolicyExplanationRecord:
    reasons: tuple[str, ...]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(str(reason) for reason in self.reasons))
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)


@dataclass(frozen=True)
class MonitorDecisionRecord:
    monitor_name: str
    allow_action: bool
    risk_score: float
    reasons: tuple[str, ...]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.monitor_name or not 0.0 <= self.risk_score <= 1.0:
            raise ValueError("monitor decision identity and risk must be valid")
        object.__setattr__(self, "reasons", tuple(str(reason) for reason in self.reasons))
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    @classmethod
    def from_decision(cls, decision: MonitorDecision) -> "MonitorDecisionRecord":
        return cls(
            decision.monitor_name,
            decision.allow_action,
            decision.risk_score,
            tuple(decision.reasons),
            decision.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)


@dataclass(frozen=True)
class InterventionRecord:
    oversight_mode: str
    intervention_type: str
    intervened: bool
    blocked: bool
    transformed: bool
    reason: str
    proposed_action_hash: str
    executed_action_hash: str
    proposal_preserved: bool = True

    def __post_init__(self) -> None:
        if not self.oversight_mode or not self.intervention_type or not self.reason:
            raise ValueError("intervention mode, type, and reason must be non-empty")
        if not self.proposed_action_hash.startswith("action_") or not self.executed_action_hash.startswith("action_"):
            raise ValueError("intervention action hashes must be authoritative")
        if self.intervened != (self.proposed_action_hash != self.executed_action_hash):
            raise ValueError("intervention flag must agree with proposed/executed action hashes")
        if self.transformed != self.intervened:
            raise ValueError("transformed flag must agree with action substitution")
        if self.blocked and not self.intervened:
            raise ValueError("blocked interventions must substitute execution")
        if not self.proposal_preserved:
            raise ValueError("oversight must preserve the original proposal")

    @classmethod
    def from_actions(
        cls,
        oversight_mode: str,
        monitor: MonitorDecision,
        proposed: ActionSnapshot,
        executed: ActionSnapshot,
    ) -> "InterventionRecord":
        intervened = proposed.action_hash != executed.action_hash
        blocked = intervened and executed.abstain
        intervention_type = (
            "block_to_abstain"
            if blocked
            else "transformed"
            if intervened
            else "not_evaluated"
            if oversight_mode == "no_oversight"
            else "recorded_only"
            if oversight_mode == "record_only"
            else "allowed"
            if monitor.allow_action
            else "denied_abstention_preserved"
        )
        reason = executed.reason or ";".join(monitor.reasons) or "proposal_allowed_without_transformation"
        return cls(
            oversight_mode,
            intervention_type,
            intervened,
            blocked,
            intervened,
            reason,
            proposed.action_hash,
            executed.action_hash,
        )

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)


@dataclass(frozen=True)
class ExecutionResultRecord:
    success: bool
    unsafe: bool
    constraint_violation: bool
    stale_data_action: bool
    unsafe_reasons: tuple[str, ...]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "unsafe_reasons", tuple(str(reason) for reason in self.unsafe_reasons))
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    @classmethod
    def from_result(cls, result: ExecutionResult) -> "ExecutionResultRecord":
        return cls(
            result.success,
            result.unsafe,
            result.constraint_violation,
            result.stale_data_action,
            tuple(result.unsafe_reasons),
            result.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)


@dataclass(frozen=True)
class ActionRecord:
    contract: str
    record_version: str
    sequence: int
    status: str
    proposed_decision: ProposedDecisionRecord | None
    proposed_action: ActionSnapshot | None
    policy_explanation: PolicyExplanationRecord | None
    monitor_decision: MonitorDecisionRecord | None
    intervention: InterventionRecord | None
    executed_action: ActionSnapshot | None
    execution_result: ExecutionResultRecord | None
    stop_reason: str
    evaluator_labels: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.contract != ACTION_RECORD_CONTRACT or self.record_version != EPISODE_RECORD_VERSION:
            raise ValueError("unsupported action record contract or version")
        if self.status not in {"complete", "infrastructure_failure", "legacy_reconstructed"}:
            raise ValueError(f"unknown action record status: {self.status!r}")
        if self.sequence < -1 or not self.stop_reason:
            raise ValueError("action record sequence and stop reason must be valid")
        object.__setattr__(self, "evaluator_labels", _freeze(self.evaluator_labels))
        required = (
            self.proposed_decision,
            self.proposed_action,
            self.policy_explanation,
            self.monitor_decision,
            self.intervention,
            self.executed_action,
            self.execution_result,
        )
        if self.status in {"complete", "legacy_reconstructed"} and any(value is None for value in required):
            raise ValueError("completed action records require every proposed-through-executed field")
        if self.status == "infrastructure_failure" and any(value is not None for value in required):
            raise ValueError("pre-proposal infrastructure failures must not fabricate action fields")

    @classmethod
    def complete(
        cls,
        *,
        sequence: int,
        decision: AgentDecision,
        monitor: MonitorDecision,
        oversight_mode: str,
        executed_action: AgentAction,
        execution: ExecutionResult,
        stop_reason: str,
        evaluator_labels: Mapping[str, Any],
        status: str = "complete",
    ) -> "ActionRecord":
        proposed = ActionSnapshot.from_action(decision.action)
        executed = ActionSnapshot.from_action(executed_action)
        return cls(
            ACTION_RECORD_CONTRACT,
            EPISODE_RECORD_VERSION,
            sequence,
            status,
            ProposedDecisionRecord(
                decision.agent_name,
                decision.confidence,
                stable_hash(decision.to_dict(), prefix="decision"),
            ),
            proposed,
            PolicyExplanationRecord(tuple(decision.reasons), decision.metadata),
            MonitorDecisionRecord.from_decision(monitor),
            InterventionRecord.from_actions(oversight_mode, monitor, proposed, executed),
            executed,
            ExecutionResultRecord.from_result(execution),
            stop_reason,
            evaluator_labels,
        )

    @classmethod
    def infrastructure_failure(cls, *, error_type: str, message: str, phase: str) -> "ActionRecord":
        return cls(
            ACTION_RECORD_CONTRACT,
            EPISODE_RECORD_VERSION,
            -1,
            "infrastructure_failure",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "orchestration_error",
            {"error_type": error_type, "message": message, "phase": phase},
        )

    @classmethod
    def from_legacy(
        cls,
        decision: AgentDecision,
        monitor: MonitorDecision,
        execution: ExecutionResult,
        stop_reason: str,
    ) -> "ActionRecord":
        return cls.complete(
            sequence=0,
            decision=decision,
            monitor=monitor,
            oversight_mode="legacy_aggregate",
            executed_action=decision.action,
            execution=execution,
            stop_reason=stop_reason or "legacy_unknown",
            evaluator_labels={
                "unsafe": execution.unsafe,
                "unsafe_labels": list(execution.unsafe_reasons),
                "legacy_reconstructed": True,
            },
            status="legacy_reconstructed",
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ActionRecord":
        def nested(name: str, record_type: type[Any]) -> Any:
            item = value.get(name)
            return None if item is None else record_type(**item)

        return cls(
            str(value["contract"]),
            str(value["record_version"]),
            int(value["sequence"]),
            str(value["status"]),
            nested("proposed_decision", ProposedDecisionRecord),
            nested("proposed_action", ActionSnapshot),
            nested("policy_explanation", PolicyExplanationRecord),
            nested("monitor_decision", MonitorDecisionRecord),
            nested("intervention", InterventionRecord),
            nested("executed_action", ActionSnapshot),
            nested("execution_result", ExecutionResultRecord),
            str(value["stop_reason"]),
            value.get("evaluator_labels", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_dict(self)

    def policy_dict(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("execution_result", None)
        value.pop("evaluator_labels", None)
        return value


def _dataclass_dict(value: object) -> dict[str, Any]:
    normalized = canonicalize(value)
    if not isinstance(normalized, dict):
        raise RuntimeError("action record did not normalize to a mapping")
    return normalized


for _record in (
    ActionSnapshot,
    ProposedDecisionRecord,
    PolicyExplanationRecord,
    MonitorDecisionRecord,
    InterventionRecord,
    ExecutionResultRecord,
    ActionRecord,
):
    register_dataclass(_record)
