"""Show every matched-history candidate without counting reused controls twice."""

from __future__ import annotations

import itertools
from pathlib import Path

from analyze_consolidation import aggregate
from consolidation_ablate import check_frozen, read
from consolidation_evaluate import digest
from negotrain.evaluation import interval, write_json
from plot_ckpt3 import plt

LABELS = {
    "reports": "Full reports",
    "reflection": "Reflective card",
    "workbook": "Workbook with examples",
    "procedure_only": "Fixed procedure",
    "workbook_no_examples": "Workbook without examples",
    "reports_with_procedure": "Reports + procedure",
    "credit_memory": "Terminal-credit memory",
    "worksheet_reports": "Reports + own-value worksheet",
}


def main():
    pooled, provenance, case_hashes = {}, {}, {}
    for cohort, variant in itertools.product(
        ("dev", "validation"), ("v1", "v2", "credit", "worksheet")
    ):
        name = (
            f"consolidation-{cohort}-{variant}"
            if variant in ("v1", "v2")
            else f"consolidation-{variant}-{cohort}-v1"
        )
        root = Path("results/ckpt3") / name
        protocol, frozen = check_frozen(root)
        analysis = read(root / "verified_analysis.json")
        if analysis["protocol_sha256"] != frozen["protocol_sha256"]:
            raise ValueError("unverified source")
        provenance[str(root)] = digest(root / "verified_analysis.json")
        for entry in protocol["cases"]:
            key = entry["key"]
            if case_hashes.setdefault(key, entry["sha256"]) != entry["sha256"]:
                raise ValueError("assessment cases differ")
            index = pooled.setdefault(key, {})
            for row in analysis["cases"][key]["rows"]:
                pair = row["user"], row["method"]
                if pair in index and index[pair] != row:
                    raise ValueError("reused control results changed")
                index[pair] = row
    result = aggregate(
        [list(rows.values()) for rows in pooled.values()], list(range(8)), list(LABELS)
    )
    values = {(r["user"], r["method"]): r["gain"] for r in result["rows"]}
    contrasts = {
        method: interval([values[u, method] - values[u, "reports"] for u in range(8)])
        for method in LABELS
        if method != "reports"
    }
    output = Path("results/ckpt3/improvement-design")
    write_json(
        output / "all_memory_candidates.json",
        {
            "scope": "Exploratory repeated development comparisons on hiring and revisited Sim4; "
            "all five practice histories matched. Cases averaged within persona. "
            "Pointwise intervals, not corrected for multiple selection attempts.",
            "source_analysis_sha256": provenance,
            "case_sha256": case_hashes,
            "pooled": result,
            "candidate_minus_reports": contrasts,
        },
    )
    fig, ax = plt.subplots(figsize=(9.5, 5.0))
    for i, estimate in enumerate(contrasts.values()):
        mean, (lo, hi) = estimate["mean"], estimate["ci95"]
        ax.plot([lo, hi], [i, i], color="#366ea5", linewidth=2)
        ax.scatter([mean], [i], color="#366ea5", s=45, zorder=3)
    ax.set_yticks(range(len(contrasts)), [LABELS[m] for m in contrasts])
    ax.invert_yaxis()
    ax.axvline(0, color="#7b8490", linestyle="--", linewidth=1)
    ax.set_xlabel("Candidate minus full reports: mean normalized surplus G")
    ax.set_title("Matched-history development: 8 personas, 2 known cases")
    ax.grid(axis="x", alpha=0.15)
    fig.text(
        0.02,
        0.02,
        "All candidates retained; paired pointwise 95% intervals. Reused controls counted once.",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(output / "all_memory_candidates.png", dpi=180)
    for method, estimate in contrasts.items():
        print(method, estimate)


if __name__ == "__main__":
    main()
