from __future__ import annotations
import json
from pathlib import Path
from src.core.types import AgentAction, AgentDecision
from .base import BaseAgent


class OfflineLLMFixtureAgent(BaseAgent):
    """Deterministic local policy fixture with an LLM-agent-shaped interface.

    This class intentionally performs no network calls and reads no credentials.
    It allows reviewers to inspect how a prompt-like policy adapter would be
    wired without requiring paid frontier model API access.
    """
    name = "offline_llm_fixture"

    def __init__(self, policy_path: str = "fixtures/offline_llm_policy/policy_cases.json"):
        self.policy_path = policy_path
        p = Path(policy_path)
        self.policy = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def decide(self, env, response):
        obs = response.observation
        faults = [f.get("name") for f in obs.metadata.get("faults", [])]
        risky = any(k in faults for k in ["missing_field", "schema_drift", "conflicting_tool_output", "constraint_shift"])
        if obs.timestamp < getattr(env, "current_time", obs.timestamp):
            risky = True
        if "conflicting_views" in obs.data:
            risky = True
        if risky:
            return AgentDecision(self.name, AgentAction("abstain", abstain=True, reason="offline_fixture_uncertainty"), 0.72, ["offline_fixture_abstained_under_shift"], {"policy_path": self.policy_path, "network_calls": 0})
        return AgentDecision(self.name, env.recommended_action(obs.data), 0.70, ["offline_fixture_clean_policy"], {"policy_path": self.policy_path, "network_calls": 0})
