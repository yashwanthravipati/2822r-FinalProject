"""Aggregate checkpoint 3 outcomes and provider cache accounting without new API calls."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from negotrain.cases import load_case
from negotrain.evaluation import metrics, write_json
from negotrain.schemas import Session


def ledger_report(path: Path):
    totals = defaultdict(lambda: defaultdict(float))
    states = defaultdict(int)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        for model, state, reserved, actual, payload in db.execute(
            "SELECT model,state,reserved,actual,usage FROM requests"
        ):
            states[state] += 1
            row = totals[model]
            row["requests"] += 1
            row["known_cost_usd"] += (actual or 0) / 1e6
            row["accounted_usd"] += (reserved if actual is None else actual) / 1e6
            if actual is None:
                continue
            usage = json.loads(payload)
            for key in (
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
                "cache_creation_5m_input_tokens",
                "cache_creation_1h_input_tokens",
                "cache_hit_calls",
                "estimated_uncached_usd",
            ):
                row[key] += usage.get(key, 0)
    for row in totals.values():
        total = (
            row["input_tokens"]
            + row["cache_read_input_tokens"]
            + row["cache_creation_input_tokens"]
        )
        row["cache_read_fraction"] = row["cache_read_input_tokens"] / total if total else 0
        row["estimated_savings_usd"] = row["estimated_uncached_usd"] - row["known_cost_usd"]
    return {
        "models": dict(totals),
        "states": dict(states),
        "known_cost_usd": sum(r["known_cost_usd"] for r in totals.values()),
        "accounted_usd": sum(r["accounted_usd"] for r in totals.values()),
    }


def episode_diagnostics(root: Path, case_path: Path):
    case = load_case(case_path)
    rows = []
    for path in sorted((root / "raw").glob("*.json")):
        value = json.loads(path.read_text())
        if "session" not in value or not value.get("complete"):
            continue
        session = Session.model_validate(value["session"])
        row = metrics(session, case)
        rows.append(
            {
                "id": session.id,
                "tier": session.counterpart_profile.tier,
                "R": row["R"],
                "agreement": row["agreement"],
                "user_turns": row["user_turns"],
                "schedule_violations": value["schedule_violations"],
                "counts": row["counts"],
            }
        )
    write_json(root / "episode_diagnostics.json", rows)
    return {
        "episodes": len(rows),
        "agreement_rate": sum(r["agreement"] for r in rows) / len(rows) if rows else None,
        "schedule_violations": sum(r["schedule_violations"] for r in rows),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--budget", choices=["dev", "final"], required=True)
    p.add_argument(
        "--training-case", type=Path, default=Path("data/cases/private/sim3_inferred.json")
    )
    p.add_argument(
        "--heldout-case", type=Path, default=Path("data/cases/private/sim4_inferred.json")
    )
    args = p.parse_args()
    result = {
        "training": episode_diagnostics(args.root, args.training_case),
        "api": ledger_report(Path(f".api-budget.sqlite3.ckpt3-{args.budget}")),
    }
    if (args.root / "heldout" / "assess_summary.json").exists():
        result["heldout"] = episode_diagnostics(args.root / "heldout", args.heldout_case)
    write_json(args.root / "audit.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
