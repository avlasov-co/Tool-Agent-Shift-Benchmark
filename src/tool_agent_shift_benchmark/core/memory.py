"""Versioned policy-visible memory channel with evaluator-isolated references."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from random import Random
from typing import Any, Iterable

from tool_agent_shift_benchmark.core.serialization import canonicalize, register_dataclass, stable_hash

POLICY_MEMORY_CONTRACT = "policy-memory-v1"
MEMORY_CORRUPTION_TYPES = (
    "substitution",
    "staleness",
    "source_confusion",
    "confidence_corruption",
    "deletion",
)


@dataclass(frozen=True)
class MemoryWrite:
    key: str
    value: Any
    source: str
    observed_at: int
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.key or not self.source:
            raise ValueError("memory write key and source must be non-empty")
        if not isinstance(self.observed_at, int) or isinstance(self.observed_at, bool):
            raise ValueError("memory write observed_at must be an integer")
        if (
            not isinstance(self.confidence, (int, float))
            or isinstance(self.confidence, bool)
            or not math.isfinite(float(self.confidence))
            or not 0.0 <= float(self.confidence) <= 1.0
        ):
            raise ValueError("memory write confidence must be finite and in [0, 1]")
        canonicalize(self.value, path="$.memory_write.value")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryOperation:
    operation: str
    target: str | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.operation not in {"validate", "overwrite", "reobserve", "ignore", "abstain"}:
            raise ValueError(f"unknown memory operation: {self.operation!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryEntry:
    key: str
    value: Any
    source: str
    observed_at: int
    written_step: int
    confidence: float
    content_hash: str

    @classmethod
    def from_write(cls, write: MemoryWrite, *, step: int) -> "MemoryEntry":
        payload = {
            "key": write.key,
            "value": canonicalize(write.value),
            "source": write.source,
            "observed_at": write.observed_at,
            "written_step": step,
            "confidence": float(write.confidence),
        }
        return cls(**payload, content_hash=stable_hash(payload, prefix="mem"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PolicyMemoryView:
    contract: str
    revision: int
    entries: tuple[MemoryEntry, ...]
    view_hash: str

    @classmethod
    def create(cls, revision: int, entries: Iterable[MemoryEntry]) -> "PolicyMemoryView":
        ordered = tuple(sorted(entries, key=lambda entry: entry.key))
        payload = {
            "contract": POLICY_MEMORY_CONTRACT,
            "revision": revision,
            "entries": [entry.to_dict() for entry in ordered],
        }
        return cls(POLICY_MEMORY_CONTRACT, revision, ordered, stable_hash(payload, prefix="memory_view"))

    def get(self, key: str) -> MemoryEntry | None:
        return next((entry for entry in self.entries if entry.key == key), None)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryCorruptionRecord:
    corruption_type: str
    target: str
    before_hash: str
    after_hash: str | None
    policy_visible_before: dict[str, Any]
    policy_visible_after: dict[str, Any] | None

    def __post_init__(self) -> None:
        if self.corruption_type not in MEMORY_CORRUPTION_TYPES:
            raise ValueError(f"unknown memory corruption type: {self.corruption_type!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryReadResult:
    policy_view: PolicyMemoryView | None
    pristine_reference_hash: str
    corruptions: tuple[MemoryCorruptionRecord, ...]
    stateful_agent: bool

    def policy_dict(self) -> dict[str, Any]:
        return {
            "contract": POLICY_MEMORY_CONTRACT,
            "stateful_agent": self.stateful_agent,
            "view": self.policy_view.to_dict() if self.policy_view is not None else None,
        }

    def evaluator_dict(self) -> dict[str, Any]:
        return {
            **self.policy_dict(),
            "pristine_reference_hash": self.pristine_reference_hash,
            "corruptions": [record.to_dict() for record in self.corruptions],
        }


@dataclass(frozen=True)
class MemoryCorruptionRequest:
    schedule_id: str
    severity: float
    rng_seed: int


def _rehash(entry: MemoryEntry) -> MemoryEntry:
    payload = {
        "key": entry.key,
        "value": canonicalize(entry.value),
        "source": entry.source,
        "observed_at": entry.observed_at,
        "written_step": entry.written_step,
        "confidence": float(entry.confidence),
    }
    return replace(entry, content_hash=stable_hash(payload, prefix="mem"))


def corrupt_memory_view(
    view: PolicyMemoryView,
    *,
    severity: float,
    rng: Random,
    current_step: int,
    corruption_types: tuple[str, ...] | None = None,
) -> tuple[PolicyMemoryView, tuple[MemoryCorruptionRecord, ...]]:
    """Corrupt a copied view while leaving the channel's pristine store intact."""

    if (
        not isinstance(severity, (int, float))
        or isinstance(severity, bool)
        or not math.isfinite(float(severity))
        or not 0.0 <= float(severity) <= 1.0
    ):
        raise ValueError("memory corruption severity must be finite and in [0, 1]")
    if not view.entries or severity == 0.0:
        return view, ()
    if corruption_types is None:
        count = min(len(MEMORY_CORRUPTION_TYPES), max(1, math.ceil(float(severity) * 5)))
        offset = rng.randrange(len(MEMORY_CORRUPTION_TYPES))
        selected = tuple(
            MEMORY_CORRUPTION_TYPES[(offset + index) % len(MEMORY_CORRUPTION_TYPES)] for index in range(count)
        )
        # Deletion runs last so the other mechanisms remain independently
        # observable when maximum severity selects every corruption family.
        selected = tuple(item for item in selected if item != "deletion") + tuple(
            item for item in selected if item == "deletion"
        )
    else:
        unknown = set(corruption_types) - set(MEMORY_CORRUPTION_TYPES)
        if unknown:
            raise ValueError(f"unknown memory corruption type: {sorted(unknown)[0]!r}")
        selected = corruption_types

    entries = {entry.key: entry for entry in view.entries}
    target = sorted(entries)[rng.randrange(len(entries))]
    records: list[MemoryCorruptionRecord] = []
    for corruption_type in selected:
        entry = entries.get(target)
        if entry is None:
            break
        before = entry.to_dict()
        before_hash = entry.content_hash
        if corruption_type == "deletion":
            del entries[target]
            after = None
        elif corruption_type == "substitution":
            replacement = {
                "substituted_value": stable_hash(
                    {"target": target, "before": before_hash, "step": current_step}, prefix="memory_substitute"
                )
            }
            entries[target] = _rehash(replace(entry, value=replacement))
            after = entries[target]
        elif corruption_type == "staleness":
            delta = max(1, math.ceil(10 * float(severity)))
            entries[target] = _rehash(
                replace(
                    entry,
                    observed_at=entry.observed_at - delta,
                    written_step=max(-1, entry.written_step - delta),
                )
            )
            after = entries[target]
        elif corruption_type == "source_confusion":
            entries[target] = _rehash(replace(entry, source=f"confused_source_{rng.randrange(4)}"))
            after = entries[target]
        else:
            corrupted_confidence = round(max(0.0, 1.0 - float(severity)), 6)
            if corrupted_confidence == entry.confidence:
                corrupted_confidence = 0.0 if entry.confidence > 0.0 else 1.0
            entries[target] = _rehash(replace(entry, confidence=corrupted_confidence))
            after = entries[target]
        records.append(
            MemoryCorruptionRecord(
                corruption_type,
                target,
                before_hash,
                after.content_hash if after is not None else None,
                before,
                after.to_dict() if after is not None else None,
            )
        )
    return PolicyMemoryView.create(view.revision, entries.values()), tuple(records)


class PolicyMemoryChannel:
    """Episode-local memory store; pristine entries never enter policy context."""

    def __init__(self) -> None:
        self._pristine: dict[str, MemoryEntry] = {}
        self._revision = 0

    @property
    def revision(self) -> int:
        return self._revision

    def pristine_reference_hash(self) -> str:
        return stable_hash(
            {
                "contract": POLICY_MEMORY_CONTRACT,
                "revision": self._revision,
                "entries": [self._pristine[key].to_dict() for key in sorted(self._pristine)],
            },
            prefix="memory_reference",
        )

    def write(self, writes: Iterable[MemoryWrite], *, step: int) -> tuple[MemoryEntry, ...]:
        receipts: list[MemoryEntry] = []
        for write in writes:
            entry = MemoryEntry.from_write(write, step=step)
            self._pristine[entry.key] = entry
            receipts.append(entry)
        if receipts:
            self._revision += 1
        return tuple(receipts)

    def read(
        self,
        *,
        step: int,
        stateful_agent: bool,
        requests: Iterable[MemoryCorruptionRequest] = (),
    ) -> MemoryReadResult:
        reference_hash = self.pristine_reference_hash()
        if not stateful_agent:
            return MemoryReadResult(None, reference_hash, (), False)
        view = PolicyMemoryView.create(self._revision, self._pristine.values())
        records: list[MemoryCorruptionRecord] = []
        for request in requests:
            view, applied = corrupt_memory_view(
                view,
                severity=request.severity,
                rng=Random(request.rng_seed),
                current_step=step,
            )
            records.extend(applied)
        return MemoryReadResult(view, reference_hash, tuple(records), True)


for _memory_dataclass in (
    MemoryWrite,
    MemoryOperation,
    MemoryEntry,
    PolicyMemoryView,
    MemoryCorruptionRecord,
    MemoryReadResult,
    MemoryCorruptionRequest,
):
    register_dataclass(_memory_dataclass)
