#!/usr/bin/env python3
"""Render the two performance figures for the thesis from measured JSON.

Reads the artifacts written by the measurement scripts:
  docs/experiments/docker_stats.json     -> thesis-assets/09_performance/container-resources.png
  docs/experiments/storage_growth.json   -> thesis-assets/09_performance/storage-growth.png

This script only plots values that exist in those files. It invents nothing; if a
file is missing it skips that figure and reports it, so it can be run before all
measurements are complete.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "docs" / "experiments"
OUTPUT_DIR = ROOT / "thesis-assets" / "09_performance"


# --- unit parsing -----------------------------------------------------------

def parse_percent(text: str) -> float:
    """'1.23%' -> 1.23"""
    return float(text.strip().rstrip("%"))


def to_mib(text: str) -> float:
    """Parse a docker size token such as '45.2MiB', '1.9GiB', '512KiB', '900B'."""
    token = text.strip()
    units = {
        "GiB": 1024.0,
        "MiB": 1.0,
        "KiB": 1.0 / 1024.0,
        "kiB": 1.0 / 1024.0,
        "GB": 1000.0 / 1024.0,
        "MB": 1000.0 / 1024.0 / 1.0,  # approx; docker mem normally uses *iB
        "kB": 1.0 / 1024.0,
        "B": 1.0 / (1024.0 * 1024.0),
    }
    for suffix, factor in units.items():
        if token.endswith(suffix):
            return float(token[: -len(suffix)]) * factor
    # bare number: assume bytes
    return float(token) / (1024.0 * 1024.0)


def mem_used_mib(mem_usage: str) -> float:
    """'45.2MiB / 1.9GiB' -> used part in MiB."""
    used = mem_usage.split("/")[0].strip()
    return to_mib(used)


# --- figures ----------------------------------------------------------------

def plot_container_resources(plt, dpi: int) -> Path | None:
    path = INPUT_DIR / "docker_stats.json"
    if not path.exists():
        print(f"skip container-resources: {path} not found")
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    containers = data.get("containers", [])
    rows = []
    for c in containers:
        name = c.get("Name") or c.get("Container") or "?"
        rows.append((name, parse_percent(c.get("CPUPerc", "0%")),
                     mem_used_mib(c.get("MemUsage", "0B"))))
    if not rows:
        print("skip container-resources: no container snapshots in docker_stats.json")
        return None
    rows.sort(key=lambda r: r[0])
    names = [r[0] for r in rows]
    cpu = [r[1] for r in rows]
    mem = [r[2] for r in rows]

    fig, (ax_cpu, ax_mem) = plt.subplots(1, 2, figsize=(10, 4.2))
    bars_cpu = ax_cpu.barh(names, cpu, color="#3b6fb0")
    ax_cpu.set_xlabel("CPU usage (%)")
    ax_cpu.set_title("CPU per container")
    ax_cpu.invert_yaxis()
    for b, v in zip(bars_cpu, cpu):
        ax_cpu.text(b.get_width(), b.get_y() + b.get_height() / 2,
                    f" {v:.2f}%", va="center", fontsize=8)

    bars_mem = ax_mem.barh(names, mem, color="#9aa0a6")
    ax_mem.set_xlabel("Memory used (MiB)")
    ax_mem.set_title("Memory per container")
    ax_mem.invert_yaxis()
    for b, v in zip(bars_mem, mem):
        ax_mem.text(b.get_width(), b.get_y() + b.get_height() / 2,
                    f" {v:.0f}", va="center", fontsize=8)

    fig.suptitle("Compose container resource use", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = OUTPUT_DIR / "container-resources.png"
    fig.savefig(out, dpi=dpi)
    plt.close(fig)
    print(f"wrote {out}")
    return out


def plot_storage_growth(plt, dpi: int) -> Path | None:
    path = INPUT_DIR / "storage_growth.json"
    if not path.exists():
        print(f"skip storage-growth: {path} not found")
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    growth = data.get("growth_kib", {})
    n = int(data.get("event_count", 0)) or 1
    jsonl_kib = float(growth.get("jsonl_kib", 0))
    loki_kib = float(growth.get("loki_kib", 0))

    labels = ["JSONL (app)", "Loki store"]
    values_kib = [jsonl_kib, loki_kib]
    per_event_bytes = [v * 1024.0 / n for v in values_kib]

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    bars = ax.bar(labels, values_kib, color=["#3b6fb0", "#9aa0a6"], width=0.55)
    ax.set_ylabel("Storage growth (KiB)")
    ax.set_title(f"Storage growth for N = {n} events")
    for b, kib, bpe in zip(bars, values_kib, per_event_bytes):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                f"{kib:.0f} KiB\n({bpe:.0f} B/event)",
                ha="center", va="bottom", fontsize=8)
    ax.margins(y=0.18)
    fig.tight_layout()
    out = OUTPUT_DIR / "storage-growth.png"
    fig.savefig(out, dpi=dpi)
    plt.close(fig)
    print(f"wrote {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dpi", type=int, default=150)
    parser.parse_args()

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit(
            "matplotlib is required: install it in the venv "
            "(pip install matplotlib) and re-run."
        ) from exc

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    produced = [p for p in (
        plot_container_resources(plt, 150),
        plot_storage_growth(plt, 150),
    ) if p is not None]
    if not produced:
        raise SystemExit(
            "no figures produced: run scripts/measure_docker_stats.py and "
            "scripts/measure_storage_growth.py first."
        )
    print(f"done: {len(produced)} figure(s) in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
