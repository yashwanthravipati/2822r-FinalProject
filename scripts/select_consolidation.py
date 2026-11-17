"""Select each persona's memory on a separate validation case; never read target scores."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from negotrain.evaluation import write_json

# Prespecified tie order favors the existing baseline over a new intervention.
ORDER = ("reports", "reflection", "workbook", "procedure_only")


def select(rows, users):
    indexed = {(r["user"], r["method"]): r for r in rows}
    expected = {(u, m) for u in users for m in ORDER}
    if len(indexed) != len(rows) or indexed.keys() != expected:
        raise ValueError("complete four-method selection cohort required")
    return {str(u): max(ORDER, key=lambda m: indexed[u, m]["final_G"]) for u in users}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--selection-case", default="hiring")
    args = p.parse_args()
    root = args.root
    protocol = json.loads((root / "protocol.json").read_text())
    entry = next(c for c in protocol["cases"] if c["key"] == args.selection_case)
    if entry["status"] == "fresh_test":
        raise ValueError("fresh test outcomes cannot select prompts")
    rows_path = root / "assessment" / args.selection_case / "assess_rows.json"
    result = {
        "selection_case": args.selection_case,
        "rule": "highest mean final_G across three validation tiers; ties use fixed ORDER",
        "tie_order": ORDER,
        "selection_rows_sha256": hashlib.sha256(rows_path.read_bytes()).hexdigest(),
        "frozen_memories_sha256": hashlib.sha256((root / "frozen.json").read_bytes()).hexdigest(),
        "selected": select(json.loads(rows_path.read_text()), protocol["users"]),
    }
    result = json.loads(json.dumps(result))
    path = root / "selection.json"
    if path.exists() and json.loads(path.read_text()) != result:
        raise ValueError("selection changed; preserve existing study")
    write_json(path, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
