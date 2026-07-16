"""Typed deterministic fault schedules evaluated on every tool call."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from tool_agent_shift_benchmark.core.serialization import register_dataclass, stable_hash

FAULT_SCHEDULE_CONTRACT = "fault-schedule-v2"


@dataclass(frozen=True)
class FaultSchedule:
    components: tuple[str, ...]
    configured_severity: float
    onset_step: int
    duration: int | None
    persistence: str
    recurrence: int | None
    per_step_severity: tuple[float, ...]
    contract: str = FAULT_SCHEDULE_CONTRACT

    def __post_init__(self) -> None:
        if not self.components or any(not component for component in self.components):
            raise ValueError("fault schedule components must be non-empty")
        if not 0.0 <= self.configured_severity <= 1.0:
            raise ValueError("configured fault severity must be in [0, 1]")
        if self.onset_step < 0:
            raise ValueError("fault schedule onset_step must be non-negative")
        if self.persistence not in {"persistent", "transient"}:
            raise ValueError("fault schedule persistence must be 'persistent' or 'transient'")
        if self.persistence == "persistent":
            if self.duration is not None or self.recurrence is not None:
                raise ValueError("persistent schedules cannot declare duration or recurrence")
        else:
            if self.duration is None or self.duration <= 0:
                raise ValueError("transient schedules require a positive duration")
            if self.recurrence is not None and self.recurrence <= self.duration:
                raise ValueError("intermittent recurrence must be greater than duration")
        if not self.per_step_severity:
            raise ValueError("fault schedule per_step_severity must not be empty")
        if any(not 0.0 <= severity <= 1.0 for severity in self.per_step_severity):
            raise ValueError("per-step fault severities must be in [0, 1]")
        if self.contract != FAULT_SCHEDULE_CONTRACT:
            raise ValueError(f"unsupported fault schedule contract: {self.contract!r}")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FaultSchedule":
        return cls(
            components=tuple(str(component) for component in value["shift_chain"]),
            configured_severity=float(value["configured_severity"]),
            onset_step=int(value["onset_step"]),
            duration=None if value.get("duration") is None else int(value["duration"]),
            persistence=str(value["persistence"]),
            recurrence=None if value.get("recurrence") is None else int(value["recurrence"]),
            per_step_severity=tuple(float(severity) for severity in value["per_step_severity"]),
        )

    @property
    def schedule_id(self) -> str:
        return stable_hash(self.to_dict(), prefix="schedule")

    def severity_at(self, step: int) -> float | None:
        if step < self.onset_step:
            return None
        offset = step - self.onset_step
        if self.persistence == "persistent":
            active_offset = offset
        elif self.recurrence is None:
            if self.duration is None or offset >= self.duration:
                return None
            active_offset = offset
        else:
            active_offset = offset % self.recurrence
            if self.duration is None or active_offset >= self.duration:
                return None
        return self.per_step_severity[min(active_offset, len(self.per_step_severity) - 1)]

    def provenance(self, step: int) -> dict[str, Any]:
        realized = self.severity_at(step)
        return {
            "contract": self.contract,
            "schedule_id": self.schedule_id,
            "components": list(self.components),
            "step": step,
            "onset_step": self.onset_step,
            "duration": self.duration,
            "persistence": self.persistence,
            "recurrence": self.recurrence,
            "configured_severity": self.configured_severity,
            "scheduled_severity": realized,
            "active": realized is not None,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


register_dataclass(FaultSchedule)
