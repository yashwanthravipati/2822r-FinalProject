"""Independently recompute checkpoint-3 gains from saved agreements; no API calls."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

from negotrain.cases import load_case
from negotrain.evaluation import write_json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def economics(case, role_id):
    """Enumerate all packages independently of the production Pareto-frontier scorer."""
    own, other = case.role(role_id), case.other_role(role_id)
    issues = [issue.id for issue in case.issues]

    def legal(terms):
        return not any(
            terms.get(issue) in banned
            for role in (own, other)
            for constraint in role.constraints
            if constraint.hard
            for issue, banned in constraint.disallowed.items()
        )

    def value(role, terms):
        return sum(role.points[issue][option] for issue, option in terms.items())

    feasible = []
    for options in itertools.product(*(issue.option_ids() for issue in case.issues)):
        terms = dict(zip(issues, options, strict=True))
        if legal(terms) and value(other, terms) >= other.reservation_value:
            feasible.append(value(own, terms))
    best = max(feasible)
    check(best > own.reservation_value, "undefined surplus denominator")

    def score(session):
        if session["status"] != "agreed":
            check(session["status"] == "impasse", "nonterminal session")
            return 0.0
        offer = session["agreement"]
        check(not offer["custom_terms"], "unscored custom agreement")
        terms = offer["terms"]
        check(set(terms) == set(issues) and legal(terms), "invalid terminal agreement")
        check(
            value(other, terms) >= other.reservation_value, "counterpart accepted below walk-away"
        )
        return (value(own, terms) - own.reservation_value) / (best - own.reservation_value)

    return score, best


def audit_phase(root, case, role, protocol, phase):
    methods = list(protocol["methods"])
    if phase == "assess":
        methods.append("generic_zero_shot")
    expected = {}
    for uid in range(protocol["users"]):
        for tier in protocol["probe_tiers"]:
            expected[f"learner{uid}_baseline_t{tier}"] = tier
            for method in methods:
                expected[f"learner{uid}_{method}_after_t{tier}"] = tier
        if phase == "train":
            for method in methods:
                for t, tier in enumerate(protocol["training_tiers"]):
                    expected[f"learner{uid}_{method}_train{t}"] = tier
    score, best = economics(case, role)
    scores = {}
    for path in sorted((root / "raw").glob("*.json")):
        value = json.loads(path.read_text())
        if not isinstance(value, dict) or "session" not in value:
            continue
        session = value["session"]
        key = session["id"]
        check(value["complete"], f"incomplete episode: {key}")
        check(key not in scores and key in expected, f"duplicate/unplanned episode: {key}")
        check(session["case_id"] == case.id, f"wrong case: {key}")
        check(session["user_role_id"] == role, f"wrong role: {key}")
        check(
            session["counterpart_role_id"] == case.other_role(role).id, f"wrong counterpart: {key}"
        )
        check(session["counterpart_profile"]["tier"] == expected[key], f"wrong tier: {key}")
        check(value["schedule_violations"] == 0, f"counterpart schedule violation: {key}")
        scores[key] = score(session)
    check(scores.keys() == expected.keys(), "missing planned episodes")

    def probe(prefix):
        return sum(scores[f"{prefix}_t{tier}"] for tier in protocol["probe_tiers"]) / len(
            protocol["probe_tiers"]
        )

    rows = json.loads((root / f"{phase}_rows.json").read_text())
    pairs = {(uid, method) for uid in range(protocol["users"]) for method in methods}
    seen = set()
    for row in rows:
        pair = (row["user"], row["method"])
        check(pair in pairs and pair not in seen, "duplicate/unplanned result row")
        seen.add(pair)
        uid, method = pair
        before = probe(f"learner{uid}_baseline")
        after = probe(f"learner{uid}_{method}_after")
        for key, value in (("baseline_G", before), ("final_G", after), ("gain", after - before)):
            check(math.isclose(row[key], value, abs_tol=1e-12), f"wrong {key}: {pair}")
        if phase == "train":
            curve = [
                scores[f"learner{uid}_{method}_train{t}"]
                for t in range(len(protocol["training_tiers"]))
            ]
            check(len(curve) == len(row["training_R"]), "incomplete training curve")
            check(
                all(
                    math.isclose(a, b, abs_tol=1e-12)
                    for a, b in zip(curve, row["training_R"], strict=True)
                ),
                f"wrong training curve: {pair}",
            )
    check(seen == pairs, "missing result rows")
    return {"episodes": len(scores), "paired_rows": len(rows), "feasible_best": best}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--phase", choices=("train", "all"), default="all")
    parser.add_argument(
        "--training-case", type=Path, default=Path("data/cases/private/sim3_inferred.json")
    )
    parser.add_argument(
        "--heldout-case", type=Path, default=Path("data/cases/private/sim4_inferred.json")
    )
    args = parser.parse_args()
    protocol = json.loads((args.root / "protocol.json").read_text())
    freeze = json.loads((args.root / "frozen.json").read_text())
    sources = sorted(Path("src/negotrain").rglob("*.py")) + [Path("scripts/ckpt3_evaluate.py")]
    source = hashlib.sha256(b"".join(path.read_bytes() for path in sources)).hexdigest()
    check(source == protocol["source_sha256"], "experiment source changed")
    check(digest(args.training_case) == protocol["training_case_sha256"], "training case changed")
    check(digest(args.heldout_case) == protocol["heldout_case_sha256"], "held-out case changed")
    check(digest(args.root / "protocol.json") == freeze["protocol_sha256"], "protocol changed")
    expected_memories = {
        f"learner{uid}_{method}.json"
        for uid in range(protocol["users"])
        for method in protocol["methods"]
    }
    check(set(freeze["memories"]) == expected_memories, "missing frozen memories")
    for name, saved_hash in freeze["memories"].items():
        path = args.root / "raw" / name
        check(digest(path) == saved_hash, "training memory changed")
        check(
            json.loads(path.read_text())["rounds_complete"] == protocol["rounds"], "short training"
        )
    result = {
        "source_sha256": source,
        "protocol_sha256": freeze["protocol_sha256"],
        "frozen_memories": len(expected_memories),
        "train": audit_phase(
            args.root, load_case(args.training_case), protocol["training_role"], protocol, "train"
        ),
    }
    if args.phase == "all":
        result["heldout"] = audit_phase(
            args.root / "heldout",
            load_case(args.heldout_case),
            protocol["heldout_role"],
            protocol,
            "assess",
        )
    write_json(args.root / f"verification_{args.phase}.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
