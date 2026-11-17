"""Prospective fresh-persona evaluation of a development-selected coaching memory."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import random
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from consolidation_ablate import METHODS, check_frozen, read, source_hash
from consolidation_evaluate import (
    assess_one,
    digest,
    frozen_json,
    history_files,
    load_history,
    summarize,
    train_reports,
)
from negotrain.budget import SpendLedger
from negotrain.cases import load_case
from negotrain.consolidation import CONSOLIDATE_SYSTEM, PROCEDURE, consolidate
from negotrain.evaluation import Experiment, write_json
from negotrain.llm import ClaudeLLM
from negotrain.virtual_users import VirtualTraits


def make_memories(root, uid, case, role, coach):
    sessions, reports = load_history(root / "training", uid, case, role)
    workbook, examples = consolidate(case, sessions, reports, coach, root / "raw" / f"learner{uid}")
    memories = {
        "reports": reports,
        "procedure_only": [PROCEDURE],
        "workbook": [workbook.for_learner(examples)],
        "workbook_no_examples": [workbook.for_learner(examples, include_examples=False)],
        "reports_with_procedure": [
            PROCEDURE + "\n\nYour five completed practice debriefs:\n" + "\n\n".join(reports)
        ],
    }
    write_json(
        root / "raw" / f"learner{uid}.memories.json",
        {"memories": memories, "workbook": workbook.model_dump(), "examples": examples},
    )
    return {"user": uid, "memory_characters": {m: sum(map(len, v)) for m, v in memories.items()}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("prepare", "assess"))
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--methods", required=True)
    p.add_argument("--primary-method", required=True)
    p.add_argument("--users", type=int, default=7)
    p.add_argument("--seed", type=int, default=28221129)
    p.add_argument("--workers", type=int, default=7)
    p.add_argument("--case")
    p.add_argument(
        "--training-case", type=Path, default=Path("data/cases/private/sim3_inferred.json")
    )
    p.add_argument("--training-role", default="officer")
    args = p.parse_args()
    methods = args.methods.split(",")
    if (
        set(methods) - set(METHODS)
        or len(methods) != len(set(methods))
        or "reports" not in methods
        or args.primary_method not in methods
        or not 1 <= args.workers <= 8
        or args.users < 1
    ):
        p.error(
            "unique valid methods including reports/primary, positive users, 1–8 workers required"
        )
    cases = read(args.manifest)["cases"]
    if len({c["key"] for c in cases}) != len(cases) or any(
        Path(c["key"]).name != c["key"] or c["key"] in (".", "..") for c in cases
    ):
        p.error("unique plain case keys required")
    if args.phase == "assess" and args.case not in {c["key"] for c in cases}:
        p.error("select a manifest case")
    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / ".lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    protocol = {
        "users": list(range(args.users)),
        "seed": args.seed,
        "methods": methods,
        "primary_method": args.primary_method,
        "primary_comparison": "reports",
        "budget": "final",
        "training_tiers": [2, 2, 4, 4, 4],
        "probe_tiers": [1, 3, 5],
        "training_case_sha256": digest(args.training_case),
        "training_role": args.training_role,
        "source_sha256": source_hash(),
        "ablation_source_sha256": digest(Path("scripts/consolidation_ablate.py")),
        "final_source_sha256": digest(Path(__file__)),
        "instruction_sha256": hashlib.sha256(CONSOLIDATE_SYSTEM.encode()).hexdigest(),
        "cases": [{**c, "sha256": digest(Path(c["path"]))} for c in cases],
        "coach_model": "claude-opus-5-5",
        "learner_model": "claude-sonnet-5-5",
        "cache_ttl": "5m",
    }
    frozen_json(root / "protocol.json", protocol)
    ledger = SpendLedger(".api-budget.sqlite3.ckpt3-final", 100)
    coach = ClaudeLLM(model=protocol["coach_model"], effort="low", ledger=ledger, cache_ttl="5m")
    learner = ClaudeLLM(
        model=protocol["learner_model"], effort="low", ledger=ledger, cache_ttl="5m"
    )
    rng = random.Random(args.seed)
    traits = [VirtualTraits.sample(rng) for _ in protocol["users"]]
    if args.phase == "prepare":
        if (root / "frozen.json").exists():
            raise ValueError("memories already frozen")
        case = load_case(args.training_case)
        exp = Experiment(case, args.training_role, root / "training", protocol, coach, learner)
        output = root

        def run(uid):
            train_reports(exp, uid, traits[uid], args.seed)
            row = make_memories(root, uid, case, args.training_role, coach)
            print(json.dumps({"event": "prepared", "user": uid}), flush=True)
            return [row]
    else:
        check_frozen(root)
        index = next(i for i, c in enumerate(cases) if c["key"] == args.case)
        entry = cases[index]
        output = root / "assessment" / entry["key"]
        exp = Experiment(
            load_case(entry["path"]),
            entry["role"],
            output,
            {**protocol, "assessment_case": args.case},
            coach,
            learner,
        )

        def run(uid):
            return assess_one(exp, root, uid, traits[uid], args.seed, methods, index)

    rows, errors = [], []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run, u): u for u in protocol["users"]}
            for future in as_completed(futures):
                uid = futures[future]
                try:
                    rows.extend(future.result())
                    write_json(
                        output / f"{args.phase}_rows.json",
                        sorted(rows, key=lambda r: (r["user"], r.get("method", ""))),
                    )
                except Exception as error:
                    errors.append({"user": uid, "type": type(error).__name__})
                    write_json(
                        output / "raw" / f"learner{uid}.error.json",
                        {"traceback": traceback.format_exc()},
                    )
                    print(
                        json.dumps({"event": "failed", "user": uid, "type": type(error).__name__}),
                        flush=True,
                    )
        if errors:
            write_json(output / f"errors_{time.time_ns()}.json", errors)
            raise RuntimeError("incomplete cohort; preserve checkpoints")
        if args.phase == "prepare":
            write_json(
                root / "frozen.json",
                {
                    "protocol_sha256": digest(root / "protocol.json"),
                    "memories": {
                        str(root / "raw" / f"learner{u}.memories.json"): digest(
                            root / "raw" / f"learner{u}.memories.json"
                        )
                        for u in protocol["users"]
                    },
                    "history": history_files(root / "training", protocol["users"]),
                },
            )
        else:
            write_json(output / "assess_summary.json", summarize(rows))
    finally:
        usage = {
            "coach": coach.usage.snapshot(),
            "learner": learner.usage.snapshot(),
            "ledger": ledger.snapshot(),
        }
        write_json(output / f"usage_{args.phase}_{time.time_ns()}.json", usage)
        print(json.dumps(usage), flush=True)


if __name__ == "__main__":
    main()
