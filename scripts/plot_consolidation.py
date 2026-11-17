"""Plot verified matched-history gains, retaining paired persona observations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import plot_ckpt3 as plot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads((args.root / "verified_analysis.json").read_text())
    plot.LABELS = {
        "reports": "Accumulated\nreports",
        "reflection": "Reflective\ncard",
        "workbook": "Personalized\nworkbook",
        "procedure_only": "Fixed\nprocedure",
        "personalized_selection": "Selected per\npersona",
        "workbook_no_examples": "Workbook without\nexamples",
        "reports_with_procedure": "Reports +\nprocedure",
        "credit_memory": "Terminal-credit\nworkbook",
    }
    plot.COLORS = {
        "reports": "#7b8490",
        "reflection": "#366ea5",
        "workbook": "#168577",
        "procedure_only": "#ad8541",
        "personalized_selection": "#945aa5",
        "workbook_no_examples": "#df7d38",
        "reports_with_procedure": "#6f58ad",
        "credit_memory": "#168577",
    }
    if "selected_transfer" in data:
        data = data["selected_transfer"]
    datasets = [(data["primary"]["rows"], "Primary: cases averaged within persona")]
    if data["primary"]["cases"] == 1:
        datasets = []
    datasets += [
        (value["rows"], key.replace("_", " ").title()) for key, value in data["cases"].items()
    ]
    fig, axes = plot.plt.subplots(
        1, len(datasets), figsize=(5.8 * len(datasets), 4.7), squeeze=False
    )
    for ax, (rows, title) in zip(axes[0], datasets, strict=True):
        plot.panel(ax, rows, title)
    n = len({r["user"] for r in data["primary"]["rows"]})
    note = (
        "Dots: personas; diamonds: means; bars: pointwise persona-bootstrap 95% intervals."
        if n >= 5
        else "Development cohort: dots are personas, diamonds are means; exploratory only."
    )
    fig.text(0.025, 0.025, note, fontsize=10)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    for extension in ("png", "svg"):
        path = args.root / f"paired_gains.{extension}"
        fig.savefig(path, dpi=180)
        if extension == "svg":
            path.write_text(
                "\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n"
            )
    print(args.root / "paired_gains.png")


if __name__ == "__main__":
    main()
