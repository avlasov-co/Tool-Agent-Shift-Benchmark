from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.analysis.run_pairwise_compounds import parse_pair
from src.core.catalog import PluginCatalog
from src.core.config import load_config
from src.environments.calendar_ops import CalendarOpsEnvironment
from src.environments.file_ops import FileOpsEnvironment
from src.environments.risk_ops import RiskOpsEnvironment

ENVS = {
    "file_ops": FileOpsEnvironment,
    "calendar_ops": CalendarOpsEnvironment,
    "risk_ops": RiskOpsEnvironment,
}


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
    if "schema_version" not in data:
        warnings.append("legacy config without schema_version; normalized as schema version 1")
    elif str(data["schema_version"]) not in {"1", "1.0"}:
        raise ConfigValidationError(f"unsupported config schema_version: {data['schema_version']!r}")
    envs = _as_list(data.get("environments", []), "environments")
    agents = _as_list(data.get("agents", []), "agents")
    faults = _as_list(data.get("faults", []), "faults")
    severities = _as_list(data.get("fault_severities", [1.0]), "fault_severities")
    catalog = PluginCatalog()
    _require_known(envs, set(catalog.names("environment")), "environment")
    _require_known(agents, set(catalog.names("agent")), "agent")
    if faults:
        _require_known(faults, set(catalog.names("shift")), "fault")
    if "shift_chains" in data:
        chains = _as_list(data.get("shift_chains"), "shift_chains")
        for chain in chains:
            if not isinstance(chain, list) or not chain:
                raise ConfigValidationError("each shift chain must be a non-empty list")
            _require_known(chain, set(catalog.names("shift")), "shift")
    monitor = str(data.get("monitor", "composite"))
    _require_known([monitor], set(catalog.names("monitor")), "monitor")
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
    if str(data.get("failure_policy", "continue")) not in {"continue", "fail_fast"}:
        raise ConfigValidationError("failure_policy must be 'continue' or 'fail_fast'")
    if str(data.get("monitor_policy", "record")) not in {"record", "gate"}:
        raise ConfigValidationError("monitor_policy must be 'record' or 'gate'")
    if str(data.get("artifact_policy", "bundle")) not in {"bundle", "legacy", "both"}:
        raise ConfigValidationError("artifact_policy must be 'bundle', 'legacy', or 'both'")
    try:
        retries = int(data.get("retry_attempts", 0))
    except (TypeError, ValueError):
        raise ConfigValidationError("retry_attempts must be a non-negative integer")
    if retries < 0:
        raise ConfigValidationError("retry_attempts must be a non-negative integer")
    if "seeds" in data:
        for seed in _as_list(data.get("seeds"), "seeds"):
            try:
                int(seed)
            except (TypeError, ValueError):
                raise ConfigValidationError(f"seed must be an integer: {seed!r}")
    if "scenario_indices" in data:
        for index in _as_list(data.get("scenario_indices"), "scenario_indices"):
            try:
                if int(index) < 0:
                    raise ValueError
            except (TypeError, ValueError):
                raise ConfigValidationError(f"scenario index must be a non-negative integer: {index!r}")
    if "episode_ids" in data:
        for episode_id in _as_list(data.get("episode_ids"), "episode_ids"):
            if not isinstance(episode_id, str) or not episode_id:
                raise ConfigValidationError("episode_ids must contain non-empty strings")
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
