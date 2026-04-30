from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json


def _tiny_yaml(text: str) -> Dict[str, Any]:
    """Tiny fallback parser for this repo's simple YAML configs."""
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
            if value == '':
                out[key] = []
            else:
                if value.isdigit():
                    out[key] = int(value)
                else:
                    try:
                        out[key] = float(value)
                    except ValueError:
                        out[key] = value.strip('"\'')
        elif line.lstrip().startswith('-') and current_key:
            item = line.lstrip()[1:].strip().strip('"\'')
            out.setdefault(current_key, []).append(item)
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
