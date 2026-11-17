import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from summarize_improvement_costs import audit_usage, ledger


def test_audit_receipts_allow_one_model_and_exclude_cumulative_balances(tmp_path):
    (tmp_path / "usage.json").write_text(
        json.dumps(
            {
                "learner": {"calls": 3, "estimated_usd": 0.2},
                "coach": {"calls": 2, "estimated_usd": 0.3},
                "before": {"estimated_usd": 100},
                "after": {"estimated_usd": 100.5},
            }
        )
    )
    (tmp_path / "usage_1.json").write_text(
        json.dumps(
            {
                "learner": {"calls": 1, "estimated_usd": 0.1},
            }
        )
    )
    result = audit_usage(tmp_path)
    assert result["invocations"] == 2
    assert result["calls"] == 6
    assert abs(result["estimated_usd"] - 0.6) < 1e-12


def test_cost_summary_keeps_unknown_reservations_separate_and_reads_only(tmp_path):
    path = tmp_path / "budget.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE budget (id INTEGER PRIMARY KEY, cap INTEGER)")
        db.execute("INSERT INTO budget VALUES (1,100000000)")
        db.execute("CREATE TABLE requests (actual INTEGER, reserved INTEGER, state TEXT)")
        db.executemany(
            "INSERT INTO requests VALUES (?,?,?)",
            [
                (100000, 8000000, "completed"),
                (200000, 4000000, "completed"),
                (None, 8000000, "uncertain"),
            ],
        )
    before = path.read_bytes()
    summary = ledger(path)
    assert summary["known_usage_cost_usd"] == 0.3
    assert summary["accounted_usd"] == 8.3
    assert summary["unresolved_reserved_upper_bound_usd"] == 8
    assert summary["remaining_accounted_allowance_usd"] == 91.7
    assert summary["request_states"] == {"completed": 2, "uncertain": 1}
    assert path.read_bytes() == before
