#!/usr/bin/env python3
"""Validate local Markdown links without rewriting historical documentation."""

from __future__ import annotations

import re
import sys
from pathlib import Path


LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
GENERATED_RENDER_LINKS = {"docs/architecture.svg", "docs/architecture.png"}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    markdown_files = sorted(root.glob("*.md")) + sorted((root / "docs").rglob("*.md"))
    missing: list[str] = []
    for document in markdown_files:
        for raw_link in LINK_PATTERN.findall(document.read_text(encoding="utf-8")):
            link = raw_link.strip().split(maxsplit=1)[0]
            if not link or link.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target = link.split("#", maxsplit=1)[0]
            target_path = (document.parent / target).resolve()
            try:
                target_name = target_path.relative_to(root).as_posix()
            except ValueError:
                target_name = ""
            if target_name in GENERATED_RENDER_LINKS:
                continue
            if target and not target_path.is_file():
                missing.append(f"{document.relative_to(root)} -> {raw_link}")
    if missing:
        print("broken local Markdown links:", *missing, sep="\n", file=sys.stderr)
        return 1
    print(f"checked {len(markdown_files)} Markdown files; local links resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
