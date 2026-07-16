from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from tool_agent_shift_benchmark.core.serialization import canonical_loads
from tool_agent_shift_benchmark.core.types import AgentAction, AgentDecision
from tool_agent_shift_benchmark.package_resources import read_builtin_resource

from .base import BaseAgent


class PolicyResourceError(ValueError):
    """Raised when the deterministic fixture policy cannot be safely used."""


@dataclass(frozen=True)
class FixturePolicy:
    version: str
    clean_mode: str
    clean_confidence: float
    clean_reason: str
    risk_mode: str
    risk_confidence: float
    risk_reason: str
    risk_signals: frozenset[str]


def _policy_action(value: Any, path: str) -> tuple[str, float, str]:
    if not isinstance(value, dict) or set(value) != {"mode", "confidence", "reason"}:
        raise PolicyResourceError(f"{path} must contain exactly mode, confidence, and reason")
    mode, confidence, reason = value["mode"], value["confidence"], value["reason"]
    if mode not in {"recommended", "abstain"}:
        raise PolicyResourceError(f"{path}.mode must be 'recommended' or 'abstain'")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        raise PolicyResourceError(f"{path}.confidence must be a number in [0, 1]")
    if not isinstance(reason, str) or not reason:
        raise PolicyResourceError(f"{path}.reason must be a non-empty string")
    return mode, float(confidence), reason


def _parse_policy(raw: bytes, source: str) -> FixturePolicy:
    try:
        data = canonical_loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PolicyResourceError(f"invalid fixture policy {source}: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {
        "policy_schema_version",
        "policy_version",
        "clean_action",
        "risk_action",
        "risk_signals",
    }:
        raise PolicyResourceError(f"fixture policy {source} has unknown or missing fields")
    if data["policy_schema_version"] != 1:
        raise PolicyResourceError(f"fixture policy {source} must use policy_schema_version 1")
    if not isinstance(data["policy_version"], str) or not data["policy_version"]:
        raise PolicyResourceError(f"fixture policy {source} must have a non-empty policy_version")
    if not isinstance(data["risk_signals"], list) or not all(isinstance(item, str) for item in data["risk_signals"]):
        raise PolicyResourceError(f"fixture policy {source}.risk_signals must be a list of strings")
    allowed_signals = {
        "required_field_missing",
        "schema_mismatch",
        "stale_timestamp",
        "conflicting_views",
        "memory_hint",
    }
    signals = frozenset(data["risk_signals"])
    if not signals <= allowed_signals:
        unknown = ", ".join(sorted(signals - allowed_signals))
        raise PolicyResourceError(f"fixture policy {source} names unsupported risk signals: {unknown}")
    clean_mode, clean_confidence, clean_reason = _policy_action(data["clean_action"], "clean_action")
    risk_mode, risk_confidence, risk_reason = _policy_action(data["risk_action"], "risk_action")
    return FixturePolicy(
        data["policy_version"],
        clean_mode,
        clean_confidence,
        clean_reason,
        risk_mode,
        risk_confidence,
        risk_reason,
        signals,
    )


class OfflineLLMFixtureAgent(BaseAgent):
    """Deterministic local policy fixture with an LLM-agent-shaped interface.

    This class intentionally performs no network calls and reads no credentials.
    It allows reviewers to inspect how a prompt-like policy adapter would be
    wired without requiring paid frontier model API access.
    """

    name = "offline_llm_fixture"

    def __init__(self, policy_path: str | Path | None = None):
        if policy_path is None:
            self.policy_path = "package:policies/offline_llm_policy.json"
            raw = read_builtin_resource("policies", "offline_llm_policy.json")
        else:
            path = Path(policy_path)
            if not path.is_file():
                raise PolicyResourceError(f"fixture policy file does not exist: {path}")
            self.policy_path = str(path)
            raw = path.read_bytes()
        self.policy_sha256 = sha256(raw).hexdigest()
        self.policy = _parse_policy(raw, self.policy_path)

    def _signals(self, context, response) -> list[str]:
        obs = response.observation
        signals = []
        if any(field not in obs.data for field in context.required_fields):
            signals.append("required_field_missing")
        if obs.schema_version != "v1":
            signals.append("schema_mismatch")
        if obs.timestamp < context.current_time:
            signals.append("stale_timestamp")
        if "conflicting_views" in obs.data:
            signals.append("conflicting_views")
        if obs.metadata.get("memory_hint"):
            signals.append("memory_hint")
        return signals

    def decide(self, context, response):
        obs = response.observation
        signals = self._signals(context, response)
        risk_match = any(signal in self.policy.risk_signals for signal in signals)
        mode, confidence, reason = (
            (self.policy.risk_mode, self.policy.risk_confidence, self.policy.risk_reason)
            if risk_match
            else (self.policy.clean_mode, self.policy.clean_confidence, self.policy.clean_reason)
        )
        metadata = {
            "policy_path": self.policy_path,
            "policy_version": self.policy.version,
            "policy_sha256": self.policy_sha256,
            "policy_signals": signals,
            "network_calls": 0,
        }
        if mode == "abstain":
            return AgentDecision(
                self.name,
                AgentAction("abstain", abstain=True, reason=reason),
                confidence,
                [reason],
                metadata,
            )
        return AgentDecision(
            self.name,
            context.recommended_action(obs.data),
            confidence,
            [reason],
            metadata,
        )
