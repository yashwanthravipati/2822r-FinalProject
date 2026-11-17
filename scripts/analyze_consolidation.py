"""Audit matched-history agreements independently and aggregate cases within persona."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
from pathlib import Path

from analyze_ckpt3 import episode_diagnostics, ledger_report, run_usage
from negotrain.cases import load_case
from negotrain.evaluation import interval, write_json
from select_consolidation import select
from verify_ckpt3 import check, digest, economics


def read(path):
    return json.loads(path.read_text())


def aggregate(case_rows, users, methods):
    """Cases are repeated observations, not independent sampled personas."""
    check(bool(case_rows), "no cases")
    expected = set(itertools.product(users, methods))
    indexed = []
    for rows in case_rows:
        index = {(r["user"], r["method"]): r for r in rows}
        check(len(index) == len(rows) and index.keys() == expected, "incomplete paired cohort")
        indexed.append(index)
    rows = []
    for user, method in sorted(expected):
        row = {"user": user, "method": method}
        for metric in ("baseline_G", "final_G", "gain"):
            row[metric] = sum(i[user, method][metric] for i in indexed) / len(indexed)
        rows.append(row)
    summary = {
        m: {
            k: interval([r[k] for r in rows if r["method"] == m])
            for k in ("baseline_G", "final_G", "gain")
        }
        for m in methods
    }
    for a, b in itertools.combinations(methods, 2):
        by_method = {m: {r["user"]: r["gain"] for r in rows if r["method"] == m} for m in (a, b)}
        summary[a + "_minus_" + b] = interval([by_method[a][u] - by_method[b][u] for u in users])
    return {"cases": len(case_rows), "rows": rows, "summary": summary}


def audit_case(root, entry, protocol, *, training=False):
    case = load_case(entry["path"])
    score, best = economics(case, entry["role"])
    expected = {}
    offset = 0 if training else 900000 + 100000 * protocol["cases"].index(entry)
    for uid in protocol["users"]:
        base = protocol["seed"] + 1009 * uid + offset
        for tier in protocol["probe_tiers"]:
            expected[f"learner{uid}_baseline_t{tier}"] = tier, base + tier
            for method in protocol["methods"]:
                expected[f"learner{uid}_{method}_after_t{tier}"] = tier, base + tier
        if training:
            for t, tier in enumerate(protocol["training_tiers"]):
                expected[f"learner{uid}_reports_train{t}"] = tier, base + 100 + t
    scores, statuses, below = {}, {}, 0
    for path in sorted((root / "raw").glob("*.json")):
        data = read(path)
        if not isinstance(data, dict) or "session" not in data:
            continue
        s = data["session"]
        key = s["id"]
        check(key in expected and key not in scores, "unplanned or duplicate episode")
        check(data["complete"], "incomplete episode")
        check(s["case_id"] == case.id and s["user_role_id"] == entry["role"], "wrong case/role")
        check(s["counterpart_role_id"] == case.other_role(entry["role"]).id, "wrong counterpart")
        check(s["counterpart_profile"]["tier"] == expected[key][0], "wrong tier")
        check(s["seed"] == expected[key][1], "wrong counterpart seed")
        check(s["counterpart_profile"].get("focus") is None, "unexpected focus")
        check(data["schedule_violations"] == 0, "counterpart schedule violation")
        scores[key] = score(s)
        statuses[s["status"]] = statuses.get(s["status"], 0) + 1
        below += scores[key] < 0
    check(scores.keys() == expected.keys(), "missing planned episodes")
    rows = (
        [read(root / "raw" / f"learner{u}.training.json") for u in protocol["users"]]
        if training
        else read(root / "assess_rows.json")
    )
    pairs = set(itertools.product(protocol["users"], protocol["methods"]))
    seen = set()
    for row in rows:
        pair = row["user"], row["method"]
        check(pair in pairs and pair not in seen, "unplanned/duplicate row")
        seen.add(pair)
        uid, method = pair
        before = sum(scores[f"learner{uid}_baseline_t{t}"] for t in protocol["probe_tiers"]) / 3
        after = (
            sum(scores[f"learner{uid}_{method}_after_t{t}"] for t in protocol["probe_tiers"]) / 3
        )
        for k, value in (("baseline_G", before), ("final_G", after), ("gain", after - before)):
            check(math.isclose(row[k], value, abs_tol=1e-12), f"wrong {k}")
        if training:
            curve = [scores[f"learner{uid}_reports_train{t}"] for t in range(5)]
            check(
                len(row["training_R"]) == 5
                and all(
                    math.isclose(a, b, abs_tol=1e-12)
                    for a, b in zip(curve, row["training_R"], strict=True)
                ),
                "wrong training curve",
            )
    check(seen == pairs, "missing rows")
    return rows, {
        "episodes": len(scores),
        "status_counts": statuses,
        "below_walkaway": below,
        "feasible_best": best,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument(
        "--training-case", type=Path, default=Path("data/cases/private/sim3_inferred.json")
    )
    args = p.parse_args()
    root = args.root
    protocol, frozen = read(root / "protocol.json"), read(root / "frozen.json")
    paths = sorted(Path("src/negotrain").rglob("*.py")) + [
        Path("scripts/consolidation_evaluate.py")
    ]
    source = hashlib.sha256(b"".join(p.read_bytes() for p in paths)).hexdigest()
    check(source == protocol["source_sha256"], "source changed")
    if "worksheet_source_sha256" in protocol:
        check(
            digest(Path("scripts/worksheet_evaluate.py")) == protocol["worksheet_source_sha256"],
            "worksheet runner changed",
        )
        check(
            digest(Path("scripts/value_worksheet.py")) == protocol["worksheet_memory_sha256"],
            "worksheet source changed",
        )
        for uid in protocol["users"]:
            data = read(root / "raw" / f"learner{uid}.memories.json")
            check(
                set(data["by_case"]) == {c["key"] for c in protocol["cases"]},
                "worksheet case set changed",
            )
            for entry in protocol["cases"]:
                projected = (
                    root
                    / "raw"
                    / "projected"
                    / entry["key"]
                    / "raw"
                    / f"learner{uid}.memories.json"
                )
                check(read(projected) == data["by_case"][entry["key"]], "projection changed")
    if "credit_source_sha256" in protocol:
        check(
            digest(Path("scripts/credit_evaluate.py")) == protocol["credit_source_sha256"],
            "credit runner changed",
        )
        check(
            digest(Path("scripts/credit_memory.py")) == protocol["credit_memory_sha256"],
            "credit memory source changed",
        )
    if "final_source_sha256" in protocol:
        check(
            digest(Path("scripts/consolidation_final.py")) == protocol["final_source_sha256"],
            "final source changed",
        )
    if "ablation_source_sha256" in protocol:
        check(
            digest(Path("scripts/consolidation_ablate.py")) == protocol["ablation_source_sha256"],
            "ablation source changed",
        )
    check(digest(root / "protocol.json") == frozen["protocol_sha256"], "protocol changed")
    for path, sha in {
        **frozen["memories"],
        **frozen["history"],
        **frozen.get("reused_episodes", {}),
    }.items():
        check(digest(Path(path)) == sha, "frozen memory/history changed")
    expected = {str(root / "raw" / f"learner{u}.memories.json") for u in protocol["users"]}
    check(frozen["memories"].keys() == expected, "missing frozen persona")
    check(digest(args.training_case) == protocol["training_case_sha256"], "training case changed")
    training_case = load_case(args.training_case)
    training_score, _ = economics(training_case, protocol["training_role"])
    expected_training = {
        f"learner{u}_reports_train{t}" for u in protocol["users"] for t in range(5)
    }
    seen_training = set()
    for path in frozen["history"]:
        key = Path(path).stem
        match = re.fullmatch(r"learner\d+_reports_train(\d+)", key)
        if not match:
            continue
        data = read(Path(path))
        session = data["session"]
        check(key in expected_training and key not in seen_training, "unexpected training history")
        seen_training.add(key)
        check(data["complete"] and session["id"] == key, "incomplete training episode")
        check(
            session["case_id"] == training_case.id
            and session["user_role_id"] == protocol["training_role"],
            "wrong training role/case",
        )
        check(
            session["counterpart_profile"]["tier"] == protocol["training_tiers"][int(match[1])],
            "wrong training tier",
        )
        check(data["schedule_violations"] == 0, "training schedule violation")
        training_score(session)
    check(seen_training == expected_training, "missing common practice history")
    result = {"source_sha256": source, "protocol_sha256": frozen["protocol_sha256"], "cases": {}}
    primary = []
    for entry in protocol["cases"]:
        check(digest(Path(entry["path"])) == entry["sha256"], "case changed")
        rows, diagnostics = audit_case(root / "assessment" / entry["key"], entry, protocol)
        result["cases"][entry["key"]] = {
            **diagnostics,
            "status": entry["status"],
            **aggregate([rows], protocol["users"], protocol["methods"]),
            "diagnostics": episode_diagnostics(
                root / "assessment" / entry["key"], Path(entry["path"])
            ),
        }
        if entry["primary"]:
            primary.append(rows)
    result["primary"] = aggregate(primary, protocol["users"], protocol["methods"])
    if "primary_method" in protocol:
        method, comparator = protocol["primary_method"], protocol["primary_comparison"]
        values = {(r["user"], r["method"]): r["gain"] for r in result["primary"]["rows"]}
        result["primary_test"] = {
            "method": method,
            "comparator": comparator,
            "contrast": "candidate minus comparator, averaging primary cases within each persona",
            "estimate": interval(
                [values[u, method] - values[u, comparator] for u in protocol["users"]]
            ),
            "cases": len(primary),
        }
    result["reused_episode_count"] = len(frozen.get("reused_episodes", {}))
    result["new_assessment_episode_count"] = (
        sum(c["episodes"] for c in result["cases"].values()) - result["reused_episode_count"]
    )
    selection_path = root / "selection.json"
    if selection_path.exists():
        selection = read(selection_path)
        selection_root = root / "assessment" / selection["selection_case"]
        check(
            digest(selection_root / "assess_rows.json") == selection["selection_rows_sha256"],
            "selection rows changed",
        )
        check(
            digest(root / "frozen.json") == selection["frozen_memories_sha256"],
            "selection memories changed",
        )
        chosen = select(read(selection_root / "assess_rows.json"), protocol["users"])
        check(chosen == selection["selected"], "selection rule mismatch")
        transfer = []
        selected_cases = {}
        for entry in protocol["cases"]:
            if entry["key"] == selection["selection_case"]:
                continue
            rows = result["cases"][entry["key"]]["rows"]
            selected = [
                {**r, "method": "personalized_selection"}
                for r in rows
                if r["method"] == chosen[str(r["user"])]
            ]
            combined = rows + selected
            selected_cases[entry["key"]] = aggregate(
                [combined], protocol["users"], protocol["methods"] + ["personalized_selection"]
            )
            if entry["primary"]:
                transfer.append(combined)
        result["selected_transfer"] = {
            "selection": selection,
            "cases": selected_cases,
            "primary": aggregate(
                transfer, protocol["users"], protocol["methods"] + ["personalized_selection"]
            ),
            "scope": "excludes selection case; selection requires twelve validation "
            "negotiations per persona",
        }
    result["common_practice_episodes_verified"] = len(seen_training)
    result["execution_errors"] = [
        {"artifact": str(p.relative_to(root)), "failures": read(p)}
        for p in sorted(root.rglob("errors_*.json"))
    ]
    if (root / "training").exists():
        training_rows, training_audit = audit_case(
            root / "training",
            {"path": str(args.training_case), "role": protocol["training_role"]},
            {**protocol, "methods": ["reports"]},
            training=True,
        )
        result["training"] = {**training_audit, "rows": training_rows}
    result["run_usage_by_phase"] = {
        str(p.relative_to(root)): run_usage(p)
        for p in sorted({p.parent for p in root.rglob("usage_*.json")})
    }
    fields = (
        "calls",
        "total_input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "estimated_usd",
        "estimated_uncached_usd",
    )
    total = {k: sum(v[k] for v in result["run_usage_by_phase"].values()) for k in fields}
    total["cache_read_fraction"] = (
        total["cache_read_input_tokens"] / total["total_input_tokens"]
        if total["total_input_tokens"]
        else 0
    )
    total["estimated_savings_usd"] = total["estimated_uncached_usd"] - total["estimated_usd"]
    result["run_usage_total"] = total
    result["cumulative_budget"] = ledger_report(
        Path(f".api-budget.sqlite3.ckpt3-{protocol['budget']}")
    )
    write_json(root / "verified_analysis.json", result)
    print(
        json.dumps(
            {
                "primary": result["primary"]["summary"],
                "episodes": sum(r["episodes"] for r in result["cases"].values()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
