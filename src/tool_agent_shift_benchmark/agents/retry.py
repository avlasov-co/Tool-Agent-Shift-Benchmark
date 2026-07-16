from __future__ import annotations

from typing import Any

from tool_agent_shift_benchmark.core.memory import POLICY_MEMORY_CONTRACT, MemoryOperation, MemoryWrite
from tool_agent_shift_benchmark.core.requery import REQUERY_ACTION_TYPE, TOOL_REQUERY_CONTRACT
from tool_agent_shift_benchmark.core.schema_registry import (
    SCHEMA_REGISTRY_CONTRACT,
    adapt_to_source_schema,
    schema_delta_from_metadata,
)
from tool_agent_shift_benchmark.core.serialization import stable_hash
from tool_agent_shift_benchmark.core.types import AgentAction, AgentDecision

from .base import BaseAgent


class RetryAgent(BaseAgent):
    name = "retry"
    version = "4.0.0"
    capabilities = (TOOL_REQUERY_CONTRACT, POLICY_MEMORY_CONTRACT, SCHEMA_REGISTRY_CONTRACT)
    stateful_memory = True

    def __init__(self) -> None:
        self._seen_response_hashes: set[str] = set()

    @staticmethod
    def _attempt_state(response: Any) -> dict[str, Any]:
        state = response.metadata.get("requery", {})
        return state if isinstance(state, dict) else {}

    def decide(self, context, response):
        observation = response.observation
        data = observation.data
        schema_adaptation = None
        if observation.schema_version != "v1":
            delta = schema_delta_from_metadata(response.metadata)
            if delta is not None:
                schema_adaptation = adapt_to_source_schema(data, delta)
                if schema_adaptation.succeeded:
                    data = schema_adaptation.data
        missing = [field for field in context.required_fields if field not in data]
        issues: list[str] = []
        if not response.ok or response.errors:
            issues.append("incomplete_observation")
        if missing and "incomplete_observation" not in issues:
            issues.append("incomplete_observation")
        if observation.schema_version != "v1" and (schema_adaptation is None or not schema_adaptation.succeeded):
            issues.append("invalid_schema")
        if "conflicting_views" in data:
            issues.append("conflicting_output")

        attempt_state = self._attempt_state(response)
        fingerprint = str(
            attempt_state.get("visible_response_hash")
            or stable_hash(
                {
                    "tool_name": response.tool_name,
                    "ok": response.ok,
                    "observation": observation.to_dict(),
                    "latency_ms": response.latency_ms,
                    "errors": response.errors,
                },
                prefix="visible",
            )
        )
        repeated = fingerprint in self._seen_response_hashes
        self._seen_response_hashes.add(fingerprint)
        if issues and repeated:
            issues.extend(["repeated_response", "persistent_fault_suspected"])

        memory_issues: list[str] = []
        memory_operations: list[MemoryOperation] = []
        memory = context.memory
        if memory is not None:
            memory_operations.append(MemoryOperation("validate", "last_observation", "validate_before_use"))
            previous = memory.get("last_observation")
            if memory.revision > 0 and previous is None:
                memory_issues.append("memory_entry_missing")
            elif previous is not None:
                if previous.source != response.tool_name:
                    memory_issues.append("memory_source_untrusted")
                if previous.confidence < 0.5:
                    memory_issues.append("memory_confidence_invalid")
                if previous.observed_at > context.current_time or context.current_time - previous.observed_at > 5000:
                    memory_issues.append("memory_timestamp_invalid")
                if not isinstance(previous.value, dict) or "visible_response_hash" not in previous.value:
                    memory_issues.append("memory_value_invalid")
        # A trustworthy current tool response can supersede suspicious memory.
        # If the current response is also questionable, reobserve or abstain.
        if issues:
            issues.extend(memory_issues)

        memory_write = MemoryWrite(
            "last_observation",
            {
                "visible_response_hash": fingerprint,
                "schema_version": observation.schema_version,
                "observation_timestamp": observation.timestamp,
                "lifecycle_phase": (data.get("lifecycle") or {}).get("phase"),
            },
            response.tool_name,
            context.response_received_at,
            1.0,
        )

        remaining = int(attempt_state.get("remaining_requeries", 0))
        attempt_number = int(attempt_state.get("attempt_number", 1))
        if issues and remaining > 0:
            memory_operations.append(MemoryOperation("reobserve", None, issues[0]))
            return AgentDecision(
                self.name,
                AgentAction(
                    REQUERY_ACTION_TYPE,
                    params={"reason": issues[0]},
                    reason=issues[0],
                ),
                0.85,
                issues,
                {
                    "contract": TOOL_REQUERY_CONTRACT,
                    "retry": True,
                    "attempt_number": attempt_number,
                    "remaining_requeries": remaining,
                    "missing": missing,
                    "clean_tool_bypass_prevented": True,
                    "schema_adaptation": schema_adaptation.to_dict() if schema_adaptation is not None else None,
                },
                (memory_write,),
                tuple(memory_operations),
            )
        if issues:
            memory_operations.append(MemoryOperation("abstain", None, "unresolved_memory_or_observation_risk"))
            return AgentDecision(
                self.name,
                AgentAction("abstain", abstain=True, reason="requery_exhausted"),
                0.98,
                issues + ["requery_budget_exhausted"],
                {
                    "contract": TOOL_REQUERY_CONTRACT,
                    "retry": False,
                    "attempt_number": attempt_number,
                    "remaining_requeries": 0,
                    "missing": missing,
                    "persistent_fault_suspected": repeated,
                    "clean_tool_bypass_prevented": True,
                    "safe_abstention": True,
                    "schema_adaptation": schema_adaptation.to_dict() if schema_adaptation is not None else None,
                },
                (memory_write,),
                tuple(memory_operations),
            )
        if memory_issues:
            memory_operations.extend(
                (
                    MemoryOperation("ignore", "last_observation", "current_observation_valid"),
                    MemoryOperation("overwrite", "last_observation", "replace_suspicious_memory"),
                )
            )
        elif memory is not None:
            memory_operations.append(MemoryOperation("overwrite", "last_observation", "refresh_clean_memory"))
        action = context.recommended_action(data)
        return AgentDecision(
            self.name,
            action,
            0.75,
            ["no_retry_needed"],
            {
                "contract": TOOL_REQUERY_CONTRACT,
                "retry": False,
                "attempt_number": attempt_number,
                "remaining_requeries": remaining,
                "schema_adaptation": schema_adaptation.to_dict() if schema_adaptation is not None else None,
            },
            (memory_write,),
            tuple(memory_operations),
        )
