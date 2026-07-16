"""Independent oversight treatments applied after an agent proposal."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from tool_agent_shift_benchmark.core.context import ObservationContext
from tool_agent_shift_benchmark.core.serialization import register_dataclass, stable_hash
from tool_agent_shift_benchmark.core.types import AgentAction, MonitorDecision, Observation

OVERSIGHT_TREATMENT_CONTRACT = "oversight-treatment-v1"
OVERSIGHT_MODE_ORDER = ("no_oversight", "record_only", "hard_gate")
OVERSIGHT_MODES = frozenset(OVERSIGHT_MODE_ORDER)
LEGACY_OVERSIGHT_ALIASES = {"record": "record_only", "gate": "hard_gate"}


@dataclass(frozen=True)
class OversightTreatmentDescriptor:
    contract: str
    name: str
    evaluates_monitor: bool
    enforcement: str

    def __post_init__(self) -> None:
        if self.contract != OVERSIGHT_TREATMENT_CONTRACT:
            raise ValueError(f"unsupported oversight contract: {self.contract!r}")
        if self.name not in OVERSIGHT_MODES:
            raise ValueError(f"unknown oversight mode: {self.name!r}")
        expected = {
            "no_oversight": (False, "none"),
            "record_only": (True, "observe_only"),
            "hard_gate": (True, "replace_denied_execution_with_abstention"),
        }[self.name]
        if (self.evaluates_monitor, self.enforcement) != expected:
            raise ValueError(f"oversight descriptor does not match registered mode {self.name!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def oversight_treatment(mode: str) -> OversightTreatmentDescriptor:
    if mode not in OVERSIGHT_MODES:
        raise ValueError(f"unknown oversight mode: {mode!r}")
    evaluates, enforcement = {
        "no_oversight": (False, "none"),
        "record_only": (True, "observe_only"),
        "hard_gate": (True, "replace_denied_execution_with_abstention"),
    }[mode]
    return OversightTreatmentDescriptor(OVERSIGHT_TREATMENT_CONTRACT, mode, evaluates, enforcement)


def resolve_oversight_modes(requested: Iterable[str]) -> tuple[str, ...]:
    values = tuple(str(value) for value in requested)
    unknown = set(values) - OVERSIGHT_MODES
    if unknown:
        raise ValueError(f"unknown oversight mode: {sorted(unknown)[0]!r}")
    if len(values) != len(set(values)):
        raise ValueError("oversight modes must not contain duplicates")
    selected = set(values or ("hard_gate",))
    return tuple(mode for mode in OVERSIGHT_MODE_ORDER if mode in selected)


def apply_oversight(
    mode: str,
    monitor: object,
    context: ObservationContext,
    observation: Observation,
    proposed_action: AgentAction,
) -> tuple[MonitorDecision, AgentAction]:
    """Return explicit oversight evidence and the action sent to execution."""

    descriptor = oversight_treatment(mode)
    proposal_hash = stable_hash(proposed_action.to_dict(), prefix="proposal")
    if not descriptor.evaluates_monitor:
        return (
            MonitorDecision(
                "no_oversight",
                True,
                0.0,
                [],
                {
                    "contract": descriptor.contract,
                    "oversight_mode": mode,
                    "monitor_evaluated": False,
                    "proposal_hash": proposal_hash,
                },
            ),
            proposed_action,
        )
    check = getattr(monitor, "check", None)
    if not callable(check):
        raise TypeError("configured monitor does not implement check")
    decision = check(context, observation, proposed_action)
    decision = MonitorDecision(
        decision.monitor_name,
        decision.allow_action,
        decision.risk_score,
        list(decision.reasons),
        {
            **decision.metadata,
            "oversight_contract": descriptor.contract,
            "oversight_mode": mode,
            "monitor_evaluated": True,
            "proposal_hash": proposal_hash,
        },
    )
    if mode == "hard_gate" and not decision.allow_action and not proposed_action.abstain:
        return decision, AgentAction("abstain", abstain=True, reason="oversight_hard_gate")
    return decision, proposed_action


register_dataclass(OversightTreatmentDescriptor)
