"""Render saved checkpoint-3 gains without API calls or private source text."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from negotrain.evaluation import interval

LABELS = {
    "reports": "Accumulated\nreports",
    "reflection": "Reflective\ncard",
    "rehearsal": "Card + learner\napplication",
    "generic_zero_shot": "Generic advice\n(no training)",
}
COLORS = {
    "reports": "#7b8490",
    "reflection": "#366ea5",
    "rehearsal": "#168577",
    "generic_zero_shot": "#ad8541",
}


def panel(ax, rows, title):
    methods = [m for m in LABELS if any(r["method"] == m for r in rows)]
    users = sorted({r["user"] for r in rows})
    for uid in users:
        values = {r["method"]: r["gain"] for r in rows if r["user"] == uid}
        ax.plot(
            range(len(methods)),
            [values.get(m, np.nan) for m in methods],
            color="#c5cbd1",
            linewidth=0.8,
            alpha=0.7,
            zorder=1,
        )
    for i, method in enumerate(methods):
        values = [r["gain"] for r in rows if r["method"] == method]
        ax.scatter([i] * len(values), values, color=COLORS[method], alpha=0.7, s=28, zorder=2)
        mean = float(np.mean(values))
        ax.scatter(
            [i], [mean], color=COLORS[method], marker="D", s=70, edgecolors="white", zorder=4
        )
        # A one/two-person smoke does not support a meaningful confidence interval.
        if len(values) >= 5:
            lo, hi = interval(values)["ci95"]
            ax.errorbar(
                [i],
                [mean],
                yerr=[[mean - lo], [hi - mean]],
                color=COLORS[method],
                capsize=5,
                linewidth=2,
                zorder=3,
            )
    ax.axhline(0, color="#59636e", linewidth=0.9, linestyle="--")
    ax.set_xticks(range(len(methods)), [LABELS[m] for m in methods])
    ax.set_ylabel("Post minus baseline G")
    noun = "persona" if len(users) == 1 else "personas"
    ax.set_title(f"{title} · {len(users)} {noun}", loc="left", fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    train = json.loads((args.root / "train_rows.json").read_text())
    heldout_path = args.root / "heldout" / "assess_rows.json"
    datasets = [(train, "Training-case assessment")]
    if heldout_path.exists():
        datasets.append((json.loads(heldout_path.read_text()), "Held-out case assessment"))
    fig, axes = plt.subplots(1, len(datasets), figsize=(6 * len(datasets), 4.6), squeeze=False)
    for ax, (rows, title) in zip(axes[0], datasets, strict=True):
        panel(ax, rows, title)
    users = len({r["user"] for r in train})
    note = (
        "Dots: personas; diamonds: means. Development sample; no population inference."
        if users < 5
        else "Dots: personas; diamonds: means; bars: user-bootstrap 95% intervals."
    )
    fig.text(0.05, 0.025, note, fontsize=9, color="#525c66")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    for extension in ("png", "svg"):
        fig.savefig(args.root / f"learning_gains.{extension}", dpi=180)
    print(args.root / "learning_gains.png")


if __name__ == "__main__":
    main()
