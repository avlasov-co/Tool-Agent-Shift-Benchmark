from __future__ import annotations
import csv
import struct
import zlib
from pathlib import Path
from collections import defaultdict


def _read_csv(path: str | Path):
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_png(path: str | Path, pixels, width: int, height: int) -> None:
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixels[y][x])
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(png)


def _canvas(width=640, height=360):
    return [[(255, 255, 255) for _ in range(width)] for _ in range(height)]


def _draw_bar_metric(rows, metric: str, out_path: str | Path, key="agent_name") -> None:
    grouped = defaultdict(list)
    for r in rows:
        grouped[r.get(key, r.get("agent_name", "all"))].append(float(r.get(metric, 0) or 0))
    vals = [sum(v) / len(v) for v in grouped.values()] or [0.0]
    img = _canvas(); width, height = 640, 360; margin = 40
    bar_w = max(12, (width - margin * 2) // max(1, len(vals) * 2))
    for i, val in enumerate(vals):
        h = int((height - margin * 2) * max(0.0, min(1.0, val)))
        x0 = margin + i * bar_w * 2
        for y in range(height - margin - h, height - margin):
            for x in range(x0, min(width - margin, x0 + bar_w)):
                img[y][x] = (40, 90, 160)
    for x in range(margin, width - margin): img[height - margin][x] = (0, 0, 0)
    for y in range(margin, height - margin + 1): img[y][margin] = (0, 0, 0)
    _write_png(out_path, img, width, height)


def _draw_scatter(rows, out_path: str | Path) -> None:
    img = _canvas(); width, height = 640, 360; margin = 40
    for r in rows:
        xval = float(r.get("coverage", 0) or 0); yval = 1.0 - float(r.get("unsafe_action_rate", 0) or 0)
        x = margin + int(xval * (width - 2 * margin)); y = height - margin - int(yval * (height - 2 * margin))
        for yy in range(max(0, y - 3), min(height, y + 4)):
            for xx in range(max(0, x - 3), min(width, x + 4)): img[yy][xx] = (160, 60, 60)
    for x in range(margin, width - margin): img[height - margin][x] = (0, 0, 0)
    for y in range(margin, height - margin + 1): img[y][margin] = (0, 0, 0)
    _write_png(out_path, img, width, height)


def generate_plots(summary_path="results/summary.csv", figures_dir="figures"):
    rows = _read_csv(summary_path)
    figures = Path(figures_dir); figures.mkdir(parents=True, exist_ok=True)
    _draw_bar_metric(rows, "unsafe_action_rate", figures / "unsafe_action_rate.png")
    _draw_scatter(rows, figures / "coverage_vs_safety.png")
    _draw_bar_metric([r for r in rows if r.get("agent_name") == "monitor_gated"] or rows, "monitor_recall", figures / "monitor_recall_precision.png")
    _draw_bar_metric(rows, "recovery_rate", figures / "recovery_rate.png")
    _draw_bar_metric(rows, "constraint_violation_rate", figures / "failure_breakdown.png")
    _draw_bar_metric(rows, "unsafe_step_rate", figures / "unsafe_step_rate.png")
    svd = _read_csv("results/static_vs_dynamic.csv")
    if svd:
        _draw_bar_metric(svd, "gap", figures / "static_vs_dynamic_gap.png")
    ci = _read_csv("results/confidence_intervals.csv")
    if ci:
        _draw_bar_metric([r for r in ci if r.get("metric") == "safe_useful_action_rate"] or ci, "mean", figures / "confidence_intervals.png", key="metric")
    return [str(p) for p in sorted(figures.glob("*.png"))]
