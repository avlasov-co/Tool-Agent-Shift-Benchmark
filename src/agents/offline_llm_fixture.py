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

    def decide(self, context, response):
        obs = response.observation
        risky = False
        for field in context.required_fields:
            if field not in obs.data:
                risky = True
        if obs.schema_version != "v1":
            risky = True
        if obs.timestamp < context.current_time:
            risky = True
        if "conflicting_views" in obs.data:
            risky = True
        if obs.metadata.get("memory_hint"):
            risky = True
        if risky:
            return AgentDecision(self.name, AgentAction("abstain", abstain=True, reason="offline_fixture_uncertainty"), 0.72, ["offline_fixture_abstained_under_shift"], {"policy_path": self.policy_path, "network_calls": 0})
        return AgentDecision(self.name, context.recommended_action(obs.data), 0.70, ["offline_fixture_clean_policy"], {"policy_path": self.policy_path, "network_calls": 0})
