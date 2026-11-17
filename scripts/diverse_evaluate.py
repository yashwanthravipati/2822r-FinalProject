"""Evaluate varied practice against five same-case rehearsals with a shared two-session prefix."""

from __future__ import annotations

import argparse
import fcntl
import json
import random
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from consolidation_ablate import check_frozen, read, source_hash
from consolidation_evaluate import assess_one, digest, frozen_json, load_history, summarize
from diverse_practice import SCHEDULE, rehearse
from negotrain.budget import SpendLedger
from negotrain.cases import load_case
from negotrain.evaluation import Experiment, write_json
from negotrain.llm import ClaudeLLM
from negotrain.virtual_users import VirtualTraits

METHODS = ("reports", "diverse_reports")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("prepare", "assess"))
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--budget", choices=("dev", "final"), required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--case")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument(
        "--training-case", type=Path, default=Path("data/cases/private/sim3_inferred.json")
    )
    args = p.parse_args()
    if not 1 <= args.workers <= 8:
        p.error("1–8 workers required")
    source, source_freeze = check_frozen(args.source)
    audit = read(args.source / "verified_analysis.json")
    if audit["protocol_sha256"] != source_freeze["protocol_sha256"]:
        raise ValueError("verified source required")
    manifest = read(args.manifest) if args.manifest else {"cases": source["cases"]}
    cases = manifest["cases"]
    if len({c["key"] for c in cases}) != len(cases) or any(
        Path(c["key"]).name != c["key"] or c["key"] in (".", "..") for c in cases
    ):
        p.error("unique plain case keys required")
    if args.budget == "dev" and any(c["status"] == "fresh_test" for c in cases):
        p.error("fresh test cases cannot be used for development")
    for c in cases:
        if c.get("sha256", digest(Path(c["path"]))) != digest(Path(c["path"])):
            raise ValueError("case changed")
    if "case_sha256" in manifest and (
        len(cases) != 1 or digest(Path(cases[0]["path"])) != manifest["case_sha256"]
    ):
        raise ValueError("prespecified fresh case changed")
    if digest(args.training_case) != source["training_case_sha256"]:
        raise ValueError("practice case changed")
    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / ".lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    protocol = {
        **source,
        "budget": args.budget,
        "methods": list(METHODS),
        "primary_method": "diverse_reports",
        "primary_comparison": "reports",
        "source_sha256": source_hash(),
        "diverse_source_sha256": digest(Path(__file__)),
        "diverse_memory_sha256": digest(Path("scripts/diverse_practice.py")),
        "practice_cases": [
            {**c, "sha256": digest(Path(c["path"]))}
            for c in read(Path("results/ckpt3/improvement-design/diverse_practice_manifest.json"))[
                "cases"
            ]
        ],
        "diverse_schedule": list(SCHEDULE),
        "source_root": str(args.source),
        "source_protocol_sha256": digest(args.source / "protocol.json"),
        "cases": [{**c, "sha256": digest(Path(c["path"]))} for c in cases],
    }
    practice_hashes = {c["sha256"] for c in protocol["practice_cases"]} | {
        protocol["training_case_sha256"]
    }
    if any(c["sha256"] in practice_hashes for c in protocol["cases"]):
        p.error("transfer assessments must differ from every practice case")
    frozen_json(root / "protocol.json", protocol)
    ledger = SpendLedger(f".api-budget.sqlite3.ckpt3-{args.budget}", 100)
    coach = ClaudeLLM(model=protocol["coach_model"], effort="low", ledger=ledger, cache_ttl="5m")
    learner = ClaudeLLM(
        model=protocol["learner_model"], effort="low", ledger=ledger, cache_ttl="5m"
    )
    users = protocol["users"]
    rng = random.Random(protocol["seed"])
    traits = [VirtualTraits.sample(rng) for _ in range(max(users) + 1)]
    reused = {}
    if args.phase == "prepare":
        if (root / "frozen.json").exists():
            raise ValueError("memories already frozen")
        history_root = (
            Path(source["history_root"]) if source.get("history_root") else args.source / "training"
        )
        case = load_case(args.training_case)
        experiments = {
            c["key"]: Experiment(
                load_case(c["path"]),
                c["role"],
                root / "practice" / c["key"],
                protocol,
                coach,
                learner,
            )
            for c in protocol["practice_cases"]
        }
        output = root

        def run(uid):
            sessions, reports = load_history(history_root, uid, case, protocol["training_role"])
            original = read(args.source / "raw" / f"learner{uid}.memories.json")["memories"]
            if original["reports"] != reports:
                raise ValueError("source reports changed")
            varied, scores = rehearse(experiments, uid, traits[uid], protocol["seed"], reports[:2])
            memories = {"reports": reports, "diverse_reports": varied}
            frozen_json(root / "raw" / f"learner{uid}.memories.json", {"memories": memories})
            print(json.dumps({"event": "prepared", "user": uid}), flush=True)
            return [
                {
                    "user": uid,
                    "memory_characters": {m: sum(map(len, v)) for m, v in memories.items()},
                    "new_practice_R": scores,
                }
            ]

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
            return assess_one(
                exp, root, uid, traits[uid], protocol["seed"], protocol["methods"], index
            )

    rows, errors = [], []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run, u): u for u in users}
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
            write_json(root / "reuse_manifest.json", reused)
            write_json(
                root / "frozen.json",
                {
                    "protocol_sha256": digest(root / "protocol.json"),
                    "memories": {
                        str(root / "raw" / f"learner{u}.memories.json"): digest(
                            root / "raw" / f"learner{u}.memories.json"
                        )
                        for u in users
                    },
                    "history": {
                        **source_freeze["history"],
                        **{
                            str(p): digest(p)
                            for p in sorted((root / "practice").glob("*/raw/*.json"))
                        },
                    },
                    "reused_episodes": {k: v["sha256"] for k, v in reused.items()},
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
