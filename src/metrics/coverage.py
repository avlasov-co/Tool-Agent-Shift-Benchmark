from __future__ import annotations
from typing import Iterable
from src.core.episode import Episode


def coverage(episodes: Iterable[Episode]) -> float:
    eps = list(episodes)
    return sum(not e.decision.action.abstain for e in eps) / len(eps) if eps else 0.0


def abstention_rate(episodes: Iterable[Episode]) -> float:
    eps = list(episodes)
    return sum(e.decision.action.abstain for e in eps) / len(eps) if eps else 0.0
