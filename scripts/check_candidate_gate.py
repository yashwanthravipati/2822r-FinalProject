"""Apply the prespecified positive-pooled-and-validation mean rule to complete cohorts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyze_consolidation import aggregate
from consolidation_ablate import check_frozen, read
from consolidation_evaluate import digest
from negotrain.evaluation import interval, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roots", type=Path, nargs=2, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    protocols, analyses = [], []
    for root in args.roots:
        protocol, frozen = check_frozen(root)
        analysis = read(root / "verified_analysis.json")
        if protocol["budget"] != "dev" or analysis["protocol_sha256"] != frozen["protocol_sha256"]:
            raise ValueError("verified development roots required")
        protocols.append(protocol)
        analyses.append(analysis)
    first, second = protocols
    if set(first["users"]) & set(second["users"]):
        raise ValueError("development cohorts must not overlap")
    for field in ("cases", "methods", "primary_method", "primary_comparison", "seed"):
        if first[field] != second[field]:
            raise ValueError("cohort protocol mismatch")
    method, comparator = first["primary_method"], first["primary_comparison"]
    users = first["users"] + second["users"]
    case_rows = [
        [row for a in analyses for row in a["cases"][c["key"]]["rows"]]
        for c in first["cases"]
        if c["primary"]
    ]
    pooled = aggregate(case_rows, users, first["methods"])
    values = {(r["user"], r["method"]): r["gain"] for r in pooled["rows"]}
    contrast = interval([values[u, method] - values[u, comparator] for u in users])
    validation = analyses[1]["primary_test"]["estimate"]
    result = {
        "rule": "Proceed only if paired candidate-minus-reports mean is positive both pooled "
        "and in the separate validation cohort; this is not a significance claim.",
        "candidate": method,
        "comparator": comparator,
        "sources": {
            str(r): {
                "protocol_sha256": digest(r / "protocol.json"),
                "verified_analysis_sha256": digest(r / "verified_analysis.json"),
            }
            for r in args.roots
        },
        "pooled": pooled,
        "pooled_contrast": contrast,
        "validation_contrast": validation,
        "proceed": contrast["mean"] > 0 and validation["mean"] > 0,
        "new_assessment_episodes": sum(a["new_assessment_episode_count"] for a in analyses),
        "reused_episodes": sum(a["reused_episode_count"] for a in analyses),
        "calls": sum(a["run_usage_total"]["calls"] for a in analyses),
        "estimated_usd": sum(a["run_usage_total"]["estimated_usd"] for a in analyses),
    }
    write_json(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("pooled", "sources")}, indent=2))


if __name__ == "__main__":
    main()
