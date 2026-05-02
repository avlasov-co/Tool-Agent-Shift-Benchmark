from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value.strip('"\'')


def _tiny_yaml(text: str) -> Dict[str, Any]:
    """Tiny fallback parser for this repo's simple YAML configs.

    It supports the small subset used by this repository: scalar keys, inline
    lists such as ``[0.5, 1.0]``, and indented ``- item`` lists. The fallback
    keeps smoke runs usable even when PyYAML is unavailable.
    """
    out: Dict[str, Any] = {}
    current_key: str | None = None
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(' ') and ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            out[key] = [] if value == '' else _parse_scalar(value)
        elif line.lstrip().startswith('-') and current_key:
            item = line.lstrip()[1:].strip()
            out.setdefault(current_key, []).append(_parse_scalar(item))
    return out


def load_config(path: str | Path) -> Dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
    except Exception:
        try:
            data = json.loads(text)
        except Exception:
            data = _tiny_yaml(text)
    if not isinstance(data, dict):
        raise ValueError("config must parse to a dictionary")
    return data
