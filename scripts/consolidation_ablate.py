"""Evaluate two memory ablations while preserving verified v1 control episodes exactly."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import random
import shutil
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from analyze_consolidation import audit_case
from consolidation_evaluate import assess_one, digest, frozen_json, summarize
from negotrain.budget import SpendLedger
from negotrain.cases import load_case
from negotrain.consolidation import PROCEDURE
from negotrain.evaluation import Experiment, write_json
from negotrain.llm import ClaudeLLM
from negotrain.virtual_users import VirtualTraits

METHODS = (
    "reports",
    "workbook",
    "procedure_only",
    "workbook_no_examples",
    "reports_with_procedure",
)
REUSED = ("baseline", "reports", "workbook", "procedure_only")


def read(path):
    return json.loads(path.read_text())


def source_hash():
    paths = sorted(Path("src/negotrain").rglob("*.py")) + [
        Path("scripts/consolidation_evaluate.py")
    ]
    return hashlib.sha256(b"".join(p.read_bytes() for p in paths)).hexdigest()


def check_frozen(root):
    protocol, frozen = read(root / "protocol.json"), read(root / "frozen.json")
    if digest(root / "protocol.json") != frozen["protocol_sha256"]:
        raise ValueError("protocol changed")
    if source_hash() != protocol["source_sha256"]:
        raise ValueError("actor/experiment source changed")
    for path, sha in {
        **frozen["memories"],
        **frozen["history"],
        **frozen.get("reused_episodes", {}),
    }.items():
        if digest(Path(path)) != sha:
            raise ValueError("frozen artifact changed")
    return protocol, frozen


def prepare(root, source):
    if (root / "frozen.json").exists():
        raise ValueError("ablation already frozen")
    original, freeze = check_frozen(source)
    audit = read(source / "verified_analysis.json")
    if audit["protocol_sha256"] != freeze["protocol_sha256"] or original["budget"] != "dev":
        raise ValueError("verified development source required")
    if any(c["status"] == "fresh_test" for c in original["cases"]):
        raise ValueError("fresh test reuse prohibited")
    for entry in original["cases"]:
        if digest(Path(entry["path"])) != entry["sha256"]:
            raise ValueError("source case changed")
        audit_case(source / "assessment" / entry["key"], entry, original)
    protocol = {
        **original,
        "methods": list(METHODS),
        "reused_root": str(source),
        "reused_protocol_sha256": digest(source / "protocol.json"),
        "ablation_source_sha256": digest(Path(__file__)),
    }
    frozen_json(root / "protocol.json", protocol)
    memory_paths, reused_paths, provenance, sizes = {}, {}, [], []
    for uid in protocol["users"]:
        original_path = source / "raw" / f"learner{uid}.memories.json"
        data = read(original_path)
        reports = data["memories"]["reports"]
        data["memories"]["reports_with_procedure"] = [
            PROCEDURE + "\n\nYour five completed practice debriefs:\n" + "\n\n".join(reports)
        ]
        path = root / "raw" / f"learner{uid}.memories.json"
        write_json(path, data)
        memory_paths[str(path)] = digest(path)
        sizes.append(
            {
                "user": uid,
                "memory_characters": {m: sum(map(len, data["memories"][m])) for m in METHODS},
            }
        )
        for case in protocol["cases"]:
            for method in REUSED:
                prefix = (
                    f"learner{uid}_baseline"
                    if method == "baseline"
                    else f"learner{uid}_{method}_after"
                )
                for tier in protocol["probe_tiers"]:
                    relative = Path("assessment") / case["key"] / "raw" / f"{prefix}_t{tier}.json"
                    src, dst = source / relative, root / relative
                    if not read(src)["complete"]:
                        raise ValueError("incomplete control")
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
                    sha = digest(dst)
                    reused_paths[str(dst)] = sha
                    provenance.append({"source": str(src), "destination": str(dst), "sha256": sha})
    write_json(root / "reuse_manifest.json", provenance)
    write_json(root / "prepare_rows.json", sizes)
    write_json(
        root / "frozen.json",
        {
            "protocol_sha256": digest(root / "protocol.json"),
            "memories": memory_paths,
            "history": freeze["history"],
            "reused_episodes": reused_paths,
        },
    )
    print(
        json.dumps(
            {
                "prepared_users": protocol["users"],
                "reused_episodes": len(reused_paths),
                "api_calls": 0,
            }
        )
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("prepare", "assess"))
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--source", type=Path)
    p.add_argument("--case")
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    if not 1 <= args.workers <= 8:
        p.error("1–8 workers required")
    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / ".lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.phase == "prepare":
        if not args.source:
            p.error("preparation requires verified source root")
        prepare(root, args.source)
        return
    protocol, _ = check_frozen(root)
    if digest(Path(__file__)) != protocol["ablation_source_sha256"]:
        raise ValueError("ablation source changed")
    if protocol["budget"] != "dev":
        raise ValueError("development-only ablation")
    index = next(i for i, c in enumerate(protocol["cases"]) if c["key"] == args.case)
    entry = protocol["cases"][index]
    if digest(Path(entry["path"])) != entry["sha256"]:
        raise ValueError("case changed")
    ledger = SpendLedger(".api-budget.sqlite3.ckpt3-dev", 100)
    coach = ClaudeLLM(model=protocol["coach_model"], effort="low", ledger=ledger, cache_ttl="5m")
    learner = ClaudeLLM(
        model=protocol["learner_model"], effort="low", ledger=ledger, cache_ttl="5m"
    )
    output = root / "assessment" / entry["key"]
    exp = Experiment(
        load_case(entry["path"]),
        entry["role"],
        output,
        {**protocol, "assessment_case": args.case},
        coach,
        learner,
    )
    rng = random.Random(protocol["seed"])
    traits = [VirtualTraits.sample(rng) for _ in range(max(protocol["users"]) + 1)]
    rows, errors = [], []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    assess_one,
                    exp,
                    root,
                    u,
                    traits[u],
                    protocol["seed"],
                    protocol["methods"],
                    index,
                ): u
                for u in protocol["users"]
            }
            for future in as_completed(futures):
                uid = futures[future]
                try:
                    rows.extend(future.result())
                    write_json(
                        output / "assess_rows.json",
                        sorted(rows, key=lambda r: (r["user"], r["method"])),
                    )
                except Exception as error:
                    errors.append({"user": uid, "type": type(error).__name__})
                    write_json(
                        output / "raw" / f"learner{uid}.error.json",
                        {"traceback": traceback.format_exc()},
                    )
        if errors:
            write_json(output / f"errors_{time.time_ns()}.json", errors)
            raise RuntimeError("incomplete cohort; preserve checkpoints")
        write_json(output / "assess_summary.json", summarize(rows))
    finally:
        usage = {
            "coach": coach.usage.snapshot(),
            "learner": learner.usage.snapshot(),
            "ledger": ledger.snapshot(),
        }
        write_json(output / f"usage_assess_{time.time_ns()}.json", usage)
        print(json.dumps(usage), flush=True)


if __name__ == "__main__":
    main()
