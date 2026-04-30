from __future__ import annotations
from collections import defaultdict
from math import sqrt
from statistics import mean, stdev
from typing import Iterable, Mapping


def confidence_intervals(rows: Iterable[Mapping[str, object]], group_keys=("env_name", "agent_name", "fault_name"), metrics=("unsafe_action_rate", "coverage", "safe_useful_action_rate")):
    groups = defaultdict(list)
    for row in rows:
        key = tuple(str(row.get(k, "")) for k in group_keys)
        groups[key].append(row)
    out = []
    for key, items in sorted(groups.items()):
        base = dict(zip(group_keys, key))
        for metric in metrics:
            vals = [float(i.get(metric, 0) or 0) for i in items]
            m = mean(vals) if vals else 0.0
            sd = stdev(vals) if len(vals) > 1 else 0.0
            half = 1.96 * sd / sqrt(len(vals)) if len(vals) > 1 else 0.0
            out.append({**base, "metric": metric, "n": len(vals), "mean": m, "std": sd, "ci95_low": max(0.0, m-half), "ci95_high": min(1.0, m+half)})
    return out
