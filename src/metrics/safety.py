from __future__ import annotations
from typing import Iterable
from src.core.episode import Episode


def unsafe_action_rate(episodes: Iterable[Episode]) -> float:
    eps = list(episodes)
    return sum(e.execution.unsafe for e in eps) / len(eps) if eps else 0.0


def constraint_violation_rate(episodes: Iterable[Episode]) -> float:
    eps = list(episodes)
    return sum(e.execution.constraint_violation for e in eps) / len(eps) if eps else 0.0


def stale_data_action_rate(episodes: Iterable[Episode]) -> float:
    eps = list(episodes)
    return sum(e.execution.stale_data_action for e in eps) / len(eps) if eps else 0.0
