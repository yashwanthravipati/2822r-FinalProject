"""Evaluate post-practice memories from identical five-rehearsal histories."""

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

from negotrain.budget import SpendLedger
from negotrain.cases import load_case
from negotrain.consolidation import CONSOLIDATE_SYSTEM, PROCEDURE, consolidate
from negotrain.evaluation import Experiment, interval, write_json
from negotrain.learning import refine_memory
from negotrain.llm import ClaudeLLM
from negotrain.schemas import Session
from negotrain.simulation import episode_score
from negotrain.virtual_users import VirtualTraits

METHODS = ("reports", "reflection", "workbook", "procedure_only")
TIERS = (2, 2, 4, 4, 4)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_json(path, value):
    if path.exists() and json.loads(path.read_text()) != value:
        raise ValueError(f"configuration changed: {path}; use a new root")
    write_json(path, value)


def history_files(root, users):
    files = []
    for uid in users:
        files.append(root / "raw" / f"learner{uid}_reports.json")
        for t in range(5):
            files.extend(
                root / "raw" / f"learner{uid}_reports_train{t}{suffix}"
                for suffix in (".json", ".feedback.json")
            )
    return {str(path): digest(path) for path in files}


def load_history(root, uid, case, role):
    saved = json.loads((root / "raw" / f"learner{uid}_reports.json").read_text())
    if saved["rounds_complete"] != 5 or len(saved["memory"]) != 5:
        raise ValueError("five complete report-based rehearsals required")
    sessions = []
    for t in range(5):
        data = json.loads((root / "raw" / f"learner{uid}_reports_train{t}.json").read_text())
        session = Session.model_validate(data["session"])
        if not data["complete"] or session.case_id != case.id or session.user_role_id != role:
            raise ValueError("incomplete or mismatched training history")
        if session.status == "active" or session.counterpart_profile.tier != TIERS[t]:
            raise ValueError("wrong training schedule")
        sessions.append(session)
    return sessions, saved["memory"]


def train_reports(exp, uid, traits, seed):
    base = seed + 1009 * uid
    before = exp.probe(f"learner{uid}_baseline", traits, base)
    reports, curve = [], []
    for t, tier in enumerate(TIERS):
        session = exp.episode(
            f"learner{uid}_reports_train{t}", traits, tier, None, base + 100 + t, reports
        )
        reports.append(exp.feedback(session).report.model_dump_json())
        curve.append(episode_score(exp.case, session))
        write_json(
            exp.raw / f"learner{uid}_reports.json",
            {"memory": reports, "rounds_complete": t + 1},
        )
    after = exp.probe(f"learner{uid}_reports_after", traits, base, reports)
    row = {
        "user": uid,
        "method": "reports",
        "baseline_G": before,
        "final_G": after,
        "gain": after - before,
        "training_R": curve,
    }
    write_json(exp.raw / f"learner{uid}.training.json", row)
    return row


def make_memories(root, history_root, uid, case, role, traits, coach, learner, instruction):
    sessions, reports = load_history(history_root, uid, case, role)
    card = None
    for t, session in enumerate(sessions):
        card = refine_memory(
            case,
            session,
            card,
            traits,
            coach,
            learner,
            root / "raw" / f"learner{uid}" / f"reflection{t}",
            rehearse=False,
        )
    workbook, examples = consolidate(
        case, sessions, reports, coach, root / "raw" / f"learner{uid}", instruction=instruction
    )
    memories = {
        "reports": reports,
        "reflection": [card.for_learner()],
        "workbook": [workbook.for_learner(examples)],
        "workbook_no_examples": [workbook.for_learner(examples, include_examples=False)],
        "procedure_only": [PROCEDURE],
    }
    write_json(
        root / "raw" / f"learner{uid}.memories.json",
        {"memories": memories, "examples": examples, "workbook": workbook.model_dump()},
    )
    print(json.dumps({"event": "prepared", "user": uid}), flush=True)
    return {"user": uid, "memory_characters": {m: sum(map(len, v)) for m, v in memories.items()}}


def assess_one(exp, root, uid, traits, seed, methods, case_index):
    base = seed + 900000 + 100000 * case_index + 1009 * uid
    before = exp.probe(f"learner{uid}_baseline", traits, base)
    memories = json.loads((root / "raw" / f"learner{uid}.memories.json").read_text())["memories"]
    order = list(methods)
    random.Random(base).shuffle(order)
    rows = []
    for method in order:
        after = exp.probe(f"learner{uid}_{method}_after", traits, base, memories[method])
        rows.append(
            {
                "user": uid,
                "method": method,
                "baseline_G": before,
                "final_G": after,
                "gain": after - before,
            }
        )
        print(
            json.dumps({"event": "assessed", "case": case_index, "user": uid, "method": method}),
            flush=True,
        )
    write_json(exp.raw / f"learner{uid}.assessment.json", rows)
    return rows


def summarize(rows):
    methods = sorted({r["method"] for r in rows})
    result = {}
    grouped = {
        m: sorted((r for r in rows if r["method"] == m), key=lambda r: r["user"]) for m in methods
    }
    for method, data in grouped.items():
        if len({r["user"] for r in data}) != len(data):
            raise ValueError("duplicate persona result")
        result[method] = {
            k: interval([r[k] for r in data]) for k in ("baseline_G", "final_G", "gain")
        }
    if "workbook" in grouped:
        a = {r["user"]: r["gain"] for r in grouped["workbook"]}
        for method in methods:
            if method == "workbook":
                continue
            b = {r["user"]: r["gain"] for r in grouped[method]}
            if a.keys() != b.keys():
                raise ValueError("incomplete paired cohort")
            result["workbook_minus_" + method] = interval([a[u] - b[u] for u in sorted(a)])
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("prepare", "assess"))
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--budget", choices=("dev", "final"), required=True)
    p.add_argument("--users", default="0,1,2,3")
    p.add_argument("--seed", type=int)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--case", help="case key from manifest, required for assessment")
    p.add_argument("--history-root", type=Path)
    p.add_argument("--instruction-file", type=Path)
    p.add_argument("--methods", default=",".join(METHODS))
    p.add_argument(
        "--training-case", type=Path, default=Path("data/cases/private/sim3_inferred.json")
    )
    p.add_argument("--training-role", default="officer")
    args = p.parse_args()
    users = sorted(int(u) for u in args.users.split(","))
    methods = args.methods.split(",")
    if not users or min(users) < 0 or len(users) != len(set(users)) or not 1 <= args.workers <= 8:
        p.error("unique nonnegative users and 1-8 workers required")
    if len(methods) != len(set(methods)) or set(methods) - {*METHODS, "workbook_no_examples"}:
        p.error("invalid methods")
    manifest = json.loads(args.manifest.read_text())
    cases = manifest["cases"]
    if len({c["key"] for c in cases}) != len(cases):
        p.error("case keys must be unique")
    for case in cases:
        if Path(case["key"]).name != case["key"] or case["key"] in (".", ".."):
            p.error("case key must be a plain filename")
        if args.budget == "dev" and case["status"] == "fresh_test":
            p.error("fresh test cases cannot be used for development")
    if args.phase == "assess" and args.case not in {c["key"] for c in cases}:
        p.error("select a manifest case for assessment")
    case = load_case(args.training_case)
    source = None
    if args.history_root:
        source = json.loads((args.history_root / "protocol.json").read_text())
        if (
            source["training_case_sha256"] != digest(args.training_case)
            or source["training_role"] != args.training_role
        ):
            p.error("historical training case/role mismatch")
        if max(users) >= source["users"]:
            p.error("persona absent from historical cohort")
        if args.seed is not None and args.seed != source["seed"]:
            p.error("historical persona seed must be retained")
    seed = source["seed"] if source else (args.seed if args.seed is not None else 28221129)
    instruction = args.instruction_file.read_text() if args.instruction_file else CONSOLIDATE_SYSTEM
    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / ".lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    paths = sorted(Path("src/negotrain").rglob("*.py")) + [Path(__file__)]
    settings = {
        "users": users,
        "seed": seed,
        "methods": methods,
        "budget": args.budget,
        "training_tiers": list(TIERS),
        "probe_tiers": [1, 3, 5],
        "training_case_sha256": digest(args.training_case),
        "training_role": args.training_role,
        "source_sha256": hashlib.sha256(b"".join(x.read_bytes() for x in paths)).hexdigest(),
        "instruction_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
        "cases": [{**c, "sha256": digest(Path(c["path"]))} for c in cases],
        "history_root": str(args.history_root) if args.history_root else None,
        "source_history": history_files(args.history_root, users) if args.history_root else None,
        "coach_model": "claude-opus-5-5",
        "learner_model": "claude-sonnet-5-5",
        "cache_ttl": "5m",
    }
    frozen_json(root / "protocol.json", settings)
    ledger = SpendLedger(f".api-budget.sqlite3.ckpt3-{args.budget}", 100)
    coach = ClaudeLLM(model=settings["coach_model"], effort="low", ledger=ledger, cache_ttl="5m")
    learner = ClaudeLLM(
        model=settings["learner_model"], effort="low", ledger=ledger, cache_ttl="5m"
    )
    rng = random.Random(seed)
    traits = [VirtualTraits.sample(rng) for _ in range(max(users) + 1)]
    output = root
    if args.phase == "prepare":
        if (root / "frozen.json").exists():
            raise ValueError("memories already frozen; assess or use a new root")
        history_root = args.history_root or root / "training"
        exp = (
            None
            if args.history_root
            else Experiment(case, args.training_role, history_root, settings, coach, learner)
        )

        def run(uid):
            if exp:
                train_reports(exp, uid, traits[uid], seed)
            return make_memories(
                root,
                history_root,
                uid,
                case,
                args.training_role,
                traits[uid],
                coach,
                learner,
                instruction,
            )
    else:
        frozen = json.loads((root / "frozen.json").read_text())
        if frozen["protocol_sha256"] != digest(root / "protocol.json"):
            raise ValueError("frozen protocol changed")
        for path, sha in {**frozen["memories"], **frozen["history"]}.items():
            if digest(Path(path)) != sha:
                raise ValueError("frozen memory/history changed")
        expected = {str(root / "raw" / f"learner{u}.memories.json") for u in users}
        if set(frozen["memories"]) != expected:
            raise ValueError("incomplete frozen cohort")
        index = next(i for i, c in enumerate(cases) if c["key"] == args.case)
        entry = cases[index]
        output = root / "assessment" / args.case
        exp = Experiment(
            load_case(entry["path"]),
            entry["role"],
            output,
            {**settings, "assessment_case": args.case},
            coach,
            learner,
        )

        def run(uid):
            return assess_one(exp, root, uid, traits[uid], seed, methods, index)

    rows, errors = [], []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run, uid): uid for uid in users}
            for future in as_completed(futures):
                uid = futures[future]
                try:
                    value = future.result()
                    rows.extend(value if isinstance(value, list) else [value])
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
            raise RuntimeError("incomplete cohort; preserve users and resume")
        if args.phase == "prepare":
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
                    "history": history_files(history_root, users),
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
