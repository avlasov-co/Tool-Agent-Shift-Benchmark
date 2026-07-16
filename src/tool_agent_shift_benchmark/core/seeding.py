"""Domain-separated deterministic seed streams for scientific execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from tool_agent_shift_benchmark.core.serialization import register_dataclass, stable_hash

SEED_STREAM_ALGORITHM = "sha256-domain-separated-63-v1"
SEED_STREAM_NAMES = (
    "scenario_generation",
    "agent_behavior",
    "fault_behavior",
    "oversight",
    "execution",
    "analysis",
)


def derive_seed(root_seed: int, stream: str, identity: dict[str, Any]) -> int:
    """Derive a local seed without reading or mutating module-global RNG state."""

    if stream not in SEED_STREAM_NAMES:
        raise ValueError(f"unknown deterministic seed stream: {stream}")
    digest = stable_hash(
        {
            "algorithm": SEED_STREAM_ALGORITHM,
            "root_seed": int(root_seed),
            "stream": stream,
            "identity": identity,
        },
        prefix="seed",
    )
    return int(digest.split("_", 1)[1], 16) % (2**63)


@dataclass(frozen=True)
class EpisodeSeedStreams:
    """All localized streams associated with one planned episode.

    Scenario generation intentionally excludes agent and treatment fields.
    Agent, oversight, and execution streams intentionally exclude treatment so
    clean and shifted members can initialize identically. Only fault behavior
    includes the declared treatment.
    """

    algorithm: str
    root_seed: int
    scenario_generation: int
    agent_behavior: int
    fault_behavior: int
    oversight: int
    execution: int
    analysis: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def episode_seed_streams(
    *,
    root_seed: int,
    environment: str,
    scenario_index: int,
    generator_name: str,
    generator_version: str,
    scenario_schema_version: str,
    agent: str,
    shift: str,
    severity: float,
    monitor: str,
    oversight_treatment: str,
) -> EpisodeSeedStreams:
    scenario_identity = {
        "environment": environment,
        "scenario_index": int(scenario_index),
        "generator_name": generator_name,
        "generator_version": generator_version,
        "scenario_schema_version": scenario_schema_version,
    }
    scenario_seed = derive_seed(root_seed, "scenario_generation", scenario_identity)
    matched_identity = {
        "scenario_generation": scenario_seed,
        "environment": environment,
        "scenario_index": int(scenario_index),
        "agent": agent,
    }
    return EpisodeSeedStreams(
        algorithm=SEED_STREAM_ALGORITHM,
        root_seed=int(root_seed),
        scenario_generation=scenario_seed,
        agent_behavior=derive_seed(root_seed, "agent_behavior", matched_identity),
        fault_behavior=derive_seed(
            root_seed,
            "fault_behavior",
            {**matched_identity, "shift": shift, "severity": float(severity)},
        ),
        oversight=derive_seed(
            root_seed,
            "oversight",
            {**matched_identity, "monitor": monitor, "treatment": oversight_treatment},
        ),
        execution=derive_seed(root_seed, "execution", matched_identity),
        analysis=derive_seed(
            root_seed,
            "analysis",
            {
                "scenario_generation": scenario_seed,
                "environment": environment,
                "scenario_index": int(scenario_index),
            },
        ),
    )


register_dataclass(EpisodeSeedStreams)
