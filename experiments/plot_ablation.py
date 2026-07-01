#!/usr/bin/env python3
"""Plot the label-design ablation: cardinality and board-query latency vs board count.

Reads docs/experiments/label_ablation.json (raised-limit sweep) and writes a two-panel
figure to thesis-assets/12_label_ablation/label_ablation.png.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "experiments" / "label_ablation.json"
OUT = ROOT / "thesis-assets" / "12_label_ablation" / "label_ablation.png"
DEFAULT_STREAM_LIMIT = 5000  # Loki's default max_global_streams_per_user

LABEL_C, PARSED_C = "#c1121f", "#0353a4"


def main() -> None:
    d = json.loads(DATA.read_text())
    pts = d["points"]
    n = [p["n_boards"] for p in pts]
    lab_series = [p["label_arm"]["cardinality"]["active_series"] for p in pts]
    par_series = [p["parsed_arm"]["cardinality"]["active_series"] for p in pts]
    lab_bq = [p["label_arm"]["board_query"]["ms"]["median"] for p in pts]
    par_bq = [p["parsed_arm"]["board_query"]["ms"]["median"] for p in pts]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    ax1.plot(n, lab_series, "o-", color=LABEL_C, label="pcb_id as label")
    ax1.plot(n, par_series, "s-", color=PARSED_C, label="pcb_id parsed-only")
    ax1.axhline(DEFAULT_STREAM_LIMIT, ls="--", color="grey", lw=1)
    ax1.text(n[0], DEFAULT_STREAM_LIMIT * 1.15, "Loki default stream limit (5000)",
             fontsize=8, color="grey")
    ax1.set_yscale("log")
    ax1.set_xlabel("Boards ingested (N)")
    ax1.set_ylabel("Active Loki series")
    ax1.set_title("(a) Cardinality cost")
    ax1.legend(fontsize=8)
    ax1.grid(True, which="both", ls=":", alpha=0.4)

    ax2.plot(n, lab_bq, "o-", color=LABEL_C, label="label selector")
    ax2.plot(n, par_bq, "s-", color=PARSED_C, label="json parse + filter")
    ax2.set_xlabel("Boards ingested (N)")
    ax2.set_ylabel("Board-isolation query latency (ms, median)")
    ax2.set_title("(b) Query cost (same 50-entry result set)")
    ax2.legend(fontsize=8)
    ax2.grid(True, ls=":", alpha=0.4)

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    print(f"saved figure -> {OUT}")

    # markdown table for the write-up
    print("\n| N boards | label series | parsed series | label bq ms | parsed bq ms |")
    print("|---|---|---|---|---|")
    for p in pts:
        print(f"| {p['n_boards']} | {p['label_arm']['cardinality']['active_series']} "
              f"| {p['parsed_arm']['cardinality']['active_series']} "
              f"| {p['label_arm']['board_query']['ms']['median']:.1f} "
              f"| {p['parsed_arm']['board_query']['ms']['median']:.1f} |")


if __name__ == "__main__":
    main()
