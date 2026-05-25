from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.agents import AGENTS
from src.core.config import load_config
from src.environments.file_ops import FileOpsEnvironment
from src.environments.calendar_ops import CalendarOpsEnvironment
from src.environments.risk_ops import RiskOpsEnvironment
from src.faults import FAULTS
from src.analysis.run_pairwise_compounds import parse_pair

ENVS = {"file_ops": FileOpsEnvironment, "calendar_ops": CalendarOpsEnvironment, "risk_ops": RiskOpsEnvironment}


class ConfigValidationError(ValueError):
    pass


def _as_list(value: Any, name: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigValidationError(f"{name} must be a list")
    return value


def _require_known(values: list[Any], known: set[str], name: str) -> None:
    for value in values:
        if str(value) not in known:
            raise ConfigValidationError(f"unknown {name}: {value!r}")


def validate_config_data(data: dict[str, Any], *, pairwise: bool = False) -> list[str]:
    warnings: list[str] = []
    envs = _as_list(data.get("environments", []), "environments")
    agents = _as_list(data.get("agents", []), "agents")
    faults = _as_list(data.get("faults", []), "faults")
    severities = _as_list(data.get("fault_severities", [1.0]), "fault_severities")
    _require_known(envs, set(ENVS), "environment")
    _require_known(agents, set(AGENTS), "agent")
    if faults:
        _require_known(faults, set(FAULTS), "fault")
    for raw in severities:
        try:
            severity = float(raw)
        except (TypeError, ValueError):
            raise ConfigValidationError(f"fault severity must be numeric: {raw!r}")
        if not 0.0 <= severity <= 1.0:
            raise ConfigValidationError(f"fault severity must be between 0.0 and 1.0: {raw!r}")
    episodes = int(data.get("episodes_per_combo", 1))
    if episodes <= 0:
        raise ConfigValidationError("episodes_per_combo must be positive")
    steps = int(data.get("episode_steps", 1))
    if steps <= 0:
        raise ConfigValidationError("episode_steps must be positive")
    if "seeds" in data:
        for seed in _as_list(data.get("seeds"), "seeds"):
            try:
                int(seed)
            except (TypeError, ValueError):
                raise ConfigValidationError(f"seed must be an integer: {seed!r}")
    if pairwise or "fault_pairs" in data:
        seen: set[tuple[str, str]] = set()
        for pair in _as_list(data.get("fault_pairs", []), "fault_pairs"):
            parsed = parse_pair(str(pair))
            key = tuple(sorted(parsed))
            if key in seen:
                raise ConfigValidationError(f"duplicate fault pair: {pair!r}")
            seen.add(key)
    if not envs:
        warnings.append("config has no explicit environments; runner defaults may apply")
    if not agents:
        warnings.append("config has no explicit agents; runner defaults may apply")
    return warnings


def validate_config(path: str | Path, *, pairwise: bool = False) -> list[str]:
    data = load_config(path)
    return validate_config_data(data, pairwise=pairwise)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Validate Tool-Agent Shift Benchmark config")
    parser.add_argument("path")
    parser.add_argument("--pairwise", action="store_true")
    args = parser.parse_args(argv)
    warnings = validate_config(args.path, pairwise=args.pairwise)
    for warning in warnings:
        print(f"warning: {warning}")
    print(f"config valid: {args.path}")


if __name__ == "__main__":
    main()
