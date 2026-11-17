"""Train on Sim3, freeze memories, then assess transfer without feeding test data back."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import random
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from negotrain.budget import SpendLedger
from negotrain.cases import load_case
from negotrain.evaluation import Experiment, interval, write_json
from negotrain.learning import GENERIC_CARD, refine_memory
from negotrain.llm import ClaudeLLM
from negotrain.virtual_users import VirtualTraits

METHODS = ("reports", "reflection", "rehearsal")
TIERS = (2, 2, 4, 4, 4)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hash():
    paths = sorted(Path("src/negotrain").rglob("*.py")) + [Path(__file__)]
    return hashlib.sha256(b"".join(p.read_bytes() for p in paths)).hexdigest()


def frozen_json(path, value):
    if path.exists() and json.loads(path.read_text()) != value:
        raise ValueError(f"configuration changed: {path}; use a new output directory")
    write_json(path, value)


def memory(root, uid, method):
    data = json.loads((root / "raw" / f"learner{uid}_{method}.json").read_text())
    return data["memory"]


def train_one(exp, root, uid, traits, settings, coach, learner):
    base_seed = settings["seed"] + 1009 * uid
    before = exp.probe(f"learner{uid}_baseline", traits, base_seed)
    order = list(METHODS)
    random.Random(base_seed).shuffle(order)
    records = []
    for method in order:
        feedback = []
        card = None
        curve = []
        for t, tier in enumerate(TIERS[: settings["rounds"]]):
            key = f"learner{uid}_{method}_train{t}"
            session = exp.episode(key, traits, tier, None, base_seed + 100 + t, feedback)
            if method == "reports":
                report = exp.feedback(session)
                feedback.append(report.report.model_dump_json())
            else:
                card = refine_memory(
                    exp.case,
                    session,
                    card,
                    traits,
                    coach,
                    learner,
                    root / "raw" / key,
                    rehearse=method == "rehearsal",
                )
                feedback = [card.for_learner()]
            from negotrain.simulation import episode_score

            curve.append(episode_score(exp.case, session))
            write_json(
                root / "raw" / f"learner{uid}_{method}.json",
                {
                    "memory": feedback,
                    "card": card.model_dump() if card else None,
                    "rounds_complete": t + 1,
                },
            )
        after = exp.probe(f"learner{uid}_{method}_after", traits, base_seed, feedback)
        records.append(
            {
                "user": uid,
                "method": method,
                "baseline_G": before,
                "final_G": after,
                "gain": after - before,
                "training_R": curve,
            }
        )
        print(
            json.dumps(
                {
                    "event": "trained",
                    "user": uid,
                    "method": method,
                    "baseline": before,
                    "after": after,
                }
            ),
            flush=True,
        )
    write_json(root / "raw" / f"learner{uid}.training.json", records)
    return records


def transfer_one(exp, root, uid, traits, settings):
    base_seed = settings["seed"] + 900000 + 1009 * uid
    # Each probe constructs a fresh actor. Baseline has no memory, and assessment
    # transcripts/rewards never feed either training or another assessment episode.
    before = exp.probe(f"learner{uid}_baseline", traits, base_seed)
    order = [*METHODS, "generic_zero_shot"]
    random.Random(base_seed).shuffle(order)
    rows = []
    for method in order:
        feedback = [GENERIC_CARD] if method == "generic_zero_shot" else memory(root, uid, method)
        after = exp.probe(f"learner{uid}_{method}_after", traits, base_seed, feedback)
        rows.append(
            {
                "user": uid,
                "method": method,
                "baseline_G": before,
                "final_G": after,
                "gain": after - before,
            }
        )
        print(json.dumps({"event": "assessed", "user": uid, "method": method}), flush=True)
    write_json(exp.raw / f"learner{uid}.assessment.json", rows)
    return rows


def summarize(rows):
    by_method = {
        m: sorted([r for r in rows if r["method"] == m], key=lambda r: r["user"])
        for m in sorted({r["method"] for r in rows})
    }
    summary = {
        m: {k: interval([r[k] for r in data]) for k in ("baseline_G", "final_G", "gain")}
        for m, data in by_method.items()
    }
    for target, baseline in (
        ("reflection", "reports"),
        ("rehearsal", "reports"),
        ("rehearsal", "reflection"),
        ("rehearsal", "generic_zero_shot"),
    ):
        if target not in by_method or baseline not in by_method:
            continue
        a = {r["user"]: r["gain"] for r in by_method[target]}
        b = {r["user"]: r["gain"] for r in by_method[baseline]}
        if a.keys() != b.keys():
            raise ValueError("incomplete paired cohort")
        summary[target + "_minus_" + baseline] = interval([a[u] - b[u] for u in sorted(a)])
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["train", "assess"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--budget", choices=["dev", "final"], required=True)
    parser.add_argument("--users", type=int, default=8)
    parser.add_argument("--rounds", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=28221117)
    parser.add_argument("--training-role", default="officer")
    parser.add_argument("--heldout-role", default="global_relief")
    parser.add_argument(
        "--training-case", type=Path, default=Path("data/cases/private/sim3_inferred.json")
    )
    parser.add_argument(
        "--heldout-case", type=Path, default=Path("data/cases/private/sim4_inferred.json")
    )
    args = parser.parse_args()
    if args.users < 1 or not 1 <= args.workers <= 8:
        parser.error("positive user count and 1-8 workers required")
    if args.phase == "assess" and args.budget != "final":
        parser.error("Sim4 is unavailable to development runs")
    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    run_lock = (root / ".lock").open("w")
    fcntl.flock(run_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    settings = {
        "users": args.users,
        "rounds": args.rounds,
        "seed": args.seed,
        "budget": args.budget,
        "methods": list(METHODS),
        "source_sha256": source_hash(),
        "training_case_sha256": digest(args.training_case),
        "training_role": args.training_role,
        "heldout_role": args.heldout_role,
        "cache_ttl": "5m",
        "learner_model": "claude-sonnet-5-5",
        "coach_model": "claude-opus-5-5",
        "controller": "hybrid",
        "training_tiers": list(TIERS[: args.rounds]),
        "probe_tiers": [1, 3, 5],
        "targeting": "none",
        "memory_limit_rules": 5,
    }
    if args.budget == "final":
        settings["heldout_case_sha256"] = digest(args.heldout_case)
    frozen_json(root / "protocol.json", settings)
    ledger = SpendLedger(f".api-budget.sqlite3.ckpt3-{args.budget}", 100)
    coach = ClaudeLLM(model=settings["coach_model"], effort="low", ledger=ledger, cache_ttl="5m")
    learner = ClaudeLLM(
        model=settings["learner_model"], effort="low", ledger=ledger, cache_ttl="5m"
    )
    rng = random.Random(args.seed)
    traits = [VirtualTraits.sample(rng) for _ in range(args.users)]
    if args.phase == "train":
        if (root / "frozen.json").exists():
            raise ValueError(
                "training already frozen; run assessment or use a new development root"
            )
        exp = Experiment(
            load_case(args.training_case),
            args.training_role,
            root,
            {**settings, "phase": "train"},
            coach,
            learner,
        )

        def run(uid):
            return train_one(exp, root, uid, traits[uid], settings, coach, learner)
    else:
        freeze = json.loads((root / "frozen.json").read_text())
        current = {
            p.name: digest(p)
            for p in sorted((root / "raw").glob("learner*_*.json"))
            if p.name.endswith(tuple(m + ".json" for m in METHODS))
        }
        if freeze["protocol_sha256"] != digest(root / "protocol.json"):
            raise ValueError("frozen training protocol changed")
        if freeze["memories"] != current or len(current) != args.users * len(METHODS):
            raise ValueError("training memories changed or incomplete")
        if digest(args.heldout_case) == digest(args.training_case):
            raise ValueError("held-out case must differ from training")
        exp = Experiment(
            load_case(args.heldout_case),
            args.heldout_role,
            root / "heldout",
            {
                **settings,
                "phase": "assessment",
                "heldout_case_sha256": digest(args.heldout_case),
                "frozen_sha256": digest(root / "frozen.json"),
            },
            coach,
            learner,
        )

        def run(uid):
            return transfer_one(exp, root, uid, traits[uid], settings)

    rows = []
    errors = []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = {pool.submit(run, u): u for u in range(args.users)}
            for future in as_completed(pending):
                uid = pending[future]
                try:
                    rows.extend(future.result())
                    write_json(
                        exp.root / f"{args.phase}_rows.json",
                        sorted(rows, key=lambda r: (r["user"], r["method"])),
                    )
                except Exception as error:
                    errors.append({"user": uid, "type": type(error).__name__})
                    write_json(
                        exp.raw / f"learner{uid}.error.json", {"traceback": traceback.format_exc()}
                    )
                    print(
                        json.dumps({"event": "failed", "user": uid, "type": type(error).__name__}),
                        flush=True,
                    )
        if errors:
            write_json(exp.root / "errors.json", errors)
            raise RuntimeError("incomplete cohort; preserve original users and resume")
        write_json(exp.root / f"{args.phase}_summary.json", summarize(rows))
        if args.phase == "train":
            memories = {
                p.name: digest(p)
                for p in sorted((root / "raw").glob("learner*_*.json"))
                if p.name.endswith(tuple(m + ".json" for m in METHODS))
            }
            write_json(
                root / "frozen.json",
                {"memories": memories, "protocol_sha256": digest(root / "protocol.json")},
            )
    finally:
        usage = {
            "coach": coach.usage.snapshot(),
            "learner": learner.usage.snapshot(),
            "ledger": ledger.snapshot(),
        }
        # Each invocation is separately recorded; a resume must not overwrite paid usage.
        import time

        write_json(exp.root / f"usage_{args.phase}_{time.time_ns()}.json", usage)
        print(json.dumps(usage), flush=True)


if __name__ == "__main__":
    main()
