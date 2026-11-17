"""Reconcile improvement-study receipts with cumulative ledgers, retaining unknown charges."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from analyze_ckpt3 import run_usage
from negotrain.evaluation import write_json

START = {"dev": 9.163600, "final": 41.133781}
FIELDS = (
    "calls",
    "total_input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "estimated_usd",
    "estimated_uncached_usd",
)


def audit_usage(root):
    """Audit runners may have one model and a single usage.json receipt."""
    paths = sorted({*root.glob("usage_*.json"), *root.glob("usage.json")})
    totals = dict.fromkeys(FIELDS, 0)
    for path in paths:
        receipt = json.loads(path.read_text())
        for role in ("learner", "coach"):
            for key in FIELDS:
                totals[key] += receipt.get(role, {}).get(key, 0)
    return {"invocations": len(paths), **totals}


def ledger(path):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        cap = db.execute("SELECT cap FROM budget WHERE id=1").fetchone()[0]
        actual, accounted = db.execute(
            "SELECT COALESCE(SUM(actual),0), COALESCE(SUM(COALESCE(actual,reserved)),0) "
            "FROM requests"
        ).fetchone()
        states = dict(db.execute("SELECT state,COUNT(*) FROM requests GROUP BY state"))
    return {
        "limit_usd": cap / 1e6,
        "known_usage_cost_usd": actual / 1e6,
        "accounted_usd": accounted / 1e6,
        "unresolved_reserved_upper_bound_usd": (accounted - actual) / 1e6,
        "remaining_accounted_allowance_usd": (cap - accounted) / 1e6,
        "request_states": states,
    }


def main():
    roots = sorted(
        p for p in Path("results/ckpt3").glob("consolidation-*") if (p / "protocol.json").exists()
    )
    studies = {}
    for root in roots:
        phases = {
            str(p.relative_to(root)): run_usage(p)
            for p in sorted({p.parent for p in root.rglob("usage_*.json")})
        }
        studies[str(root)] = {
            "independently_verified": (root / "verified_analysis.json").exists(),
            "phases": phases,
            "usage": {k: sum(v.get(k, 0) for v in phases.values()) for k in FIELDS},
        }
    for name in (
        "audit-corrected-smoke-v1",
        "persona-calibration-v1",
        "persona-probes-v1",
        "persona-probes-v2",
        "persona-probes-v3",
        "corrected-transfer-v1",
    ):
        root = Path("results/ckpt3") / name
        if root.exists():
            usage = audit_usage(root)
            studies[str(root)] = {
                "independently_verified": (root / "verification.json").exists(),
                "phases": {".": usage},
                "usage": {k: usage[k] for k in FIELDS},
            }
    totals = {k: sum(v["usage"][k] for v in studies.values()) for k in FIELDS}
    totals["cache_read_fraction"] = (
        totals["cache_read_input_tokens"] / totals["total_input_tokens"]
        if totals["total_input_tokens"]
        else 0
    )
    totals["same_volume_estimated_savings_usd"] = (
        totals["estimated_uncached_usd"] - totals["estimated_usd"]
    )
    budgets = {p: ledger(Path(f".api-budget.sqlite3.ckpt3-{p}")) for p in START}
    for phase, value in budgets.items():
        value["goal_start_known_cost_usd"] = START[phase]
        value["new_goal_known_cost_usd"] = round(value["known_usage_cost_usd"] - START[phase], 6)
    known = round(sum(v["known_usage_cost_usd"] for v in budgets.values()), 6)
    goal_known = round(sum(v["new_goal_known_cost_usd"] for v in budgets.values()), 6)
    historical = ledger(Path(".api-budget.sqlite3"))
    result = {
        "scope": "Usage-based estimates, not a provider invoice. New-goal receipts never sum "
        "cumulative ledger snapshots. Cache savings compare the same token volume. Unknown "
        "historical charges remain reserved upper bounds, not confirmed spending.",
        "studies": studies,
        "new_goal_receipts": totals,
        "cumulative_checkpoint3_ledgers": budgets,
        "cumulative_checkpoint3_known_cost_usd": known,
        "new_goal_known_cost_usd": goal_known,
        "ledger_minus_receipts_usd": goal_known - totals["estimated_usd"],
        "separate_historical_ledger": historical,
        "all_three_ledgers_known_cost_usd": round(known + historical["known_usage_cost_usd"], 6),
    }
    write_json(Path("results/ckpt3/improvement-design/cost_summary.json"), result)
    print(json.dumps({k: v for k, v in result.items() if k != "studies"}, indent=2))


if __name__ == "__main__":
    main()
