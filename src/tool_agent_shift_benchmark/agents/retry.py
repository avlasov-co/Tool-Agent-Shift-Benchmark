from __future__ import annotations

from typing import Any

from tool_agent_shift_benchmark.core.requery import REQUERY_ACTION_TYPE, TOOL_REQUERY_CONTRACT
from tool_agent_shift_benchmark.core.serialization import stable_hash
from tool_agent_shift_benchmark.core.types import AgentAction, AgentDecision

from .base import BaseAgent


class RetryAgent(BaseAgent):
    name = "retry"
    version = "2.0.0"
    capabilities = (TOOL_REQUERY_CONTRACT,)

    def __init__(self) -> None:
        self._seen_response_hashes: set[str] = set()

    @staticmethod
    def _attempt_state(response: Any) -> dict[str, Any]:
        state = response.metadata.get("requery", {})
        return state if isinstance(state, dict) else {}

    def decide(self, context, response):
        observation = response.observation
        data = observation.data
        missing = [field for field in context.required_fields if field not in data]
        issues: list[str] = []
        if not response.ok or response.errors:
            issues.append("incomplete_observation")
        if missing and "incomplete_observation" not in issues:
            issues.append("incomplete_observation")
        if observation.schema_version != "v1":
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

        remaining = int(attempt_state.get("remaining_requeries", 0))
        attempt_number = int(attempt_state.get("attempt_number", 1))
        if issues and remaining > 0:
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
                },
            )
        if issues:
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
                },
            )
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
            },
        )
