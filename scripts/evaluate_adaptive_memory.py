"""Matched-history corrected-persona development and separate-case validation."""

from __future__ import annotations

import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from adaptive_memory import GENERIC, build_plan, choose, memory
from consolidation_ablate import source_hash
from consolidation_evaluate import frozen_json
from evaluate_fresh_confirmation import Learner, paired_stats, record, traits_for
from negotrain.budget import SpendLedger
from negotrain.cases import load_case
from negotrain.evaluation import Experiment, write_json
from negotrain.llm import ClaudeLLM
from negotrain.schemas import Session

ROOT = Path("results/ckpt3/corrected-adaptive-memory-v1")
HISTORY = Path("results/ckpt3/corrected-confirmation-v1") / "train"
SEED = 2822122806
USERS = tuple(range(8))
ARMS = ("reports", "generic", "personalized")
CASES = {
    "development": (("harbor_analytics", "buyer"), ("maple_festival", "organizer")),
    "validation": (("cloudline_hiring", "candidate"), ("beacon_museum", "host")),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def history(uid):
    root = HISTORY / f"user{uid}" / "raw"
    sessions = []
    for t in range(5):
        raw = json.loads((root / f"user{uid}_practice{t}.json").read_text())
        if not raw["complete"]:
            raise ValueError("incomplete source practice")
        sessions.append(Session.model_validate(raw["session"]))
    return sessions, json.loads((root / "reports.json").read_text())


def freeze_protocol():
    paths = [HISTORY / f"user{u}" / "raw" / "reports.json" for u in USERS]
    paths += [
        HISTORY / f"user{u}" / "raw" / f"user{u}_practice{t}.json" for u in USERS for t in range(5)
    ]
    sources = (
        "adaptive_memory.py",
        "evaluate_adaptive_memory.py",
        "evaluate_fresh_confirmation.py",
        "persona_decision.py",
        "persona_instructions.py",
        "probe_isolated_personas.py",
    )
    protocol = {
        "seed": SEED,
        "users": list(USERS),
        "arms": list(ARMS),
        "bootstrap_seed": 2822122805,
        "core_sha256": source_hash(),
        "sources": {n: digest(Path("scripts") / n) for n in sources},
        "history": {str(p): digest(p) for p in paths},
        "cases": {
            phase: [
                {"id": name, "role": role, "sha256": digest(Path("data/cases") / f"{name}.json")}
                for name, role in entries
            ]
            for phase, entries in CASES.items()
        },
        "training_case_sha256": digest(Path("data/cases/private/sim3_inferred.json")),
        "traits": {str(u): traits_for(u).model_dump() for u in USERS},
        "learner": "claude-sonnet-5-5",
        "coach": "claude-opus-5-5",
        "effort": "low",
        "counterpart": "rule-based economics and templated dialogue",
        "tier": 3,
        "expected_development_episodes": 48,
        "expected_validation_episodes": 48,
        "selection": "Highest mean on two development cases; margin >=.03 over reports; "
        "ties prefer reports, then generic, then personalized",
        "primary": "Validation per-user mean across two cases, selected minus reports "
        "AND selected minus generic; eight paired replicates",
        "advance_rule": "Both mean differences positive and both exact two-sided "
        "sign-flip p<=.05; all 96 outcomes complete and verified",
        "limits": "Development study, two prompt profiles, known public cases, "
        "full-session weakness calibration unresolved; no human claim",
        "exclusions": "No Sim4 or Cedar outcome, transcript or test case enters plans or selection",
        "cost_estimate_usd": 10,
    }
    frozen_json(ROOT / "protocol.json", protocol)
    return protocol


def main():
    protocol = freeze_protocol()
    ledger = SpendLedger(".api-budget.sqlite3.ckpt3-dev")
    before = ledger.snapshot()
    attempt = len(list(ROOT.glob("usage_*.json")))
    learner = ClaudeLLM(model=protocol["learner"], effort="low", ledger=ledger)
    coach = ClaudeLLM(model=protocol["coach"], effort="low", ledger=ledger)
    train_case = load_case("data/cases/private/sim3_inferred.json")
    try:

        def prepare(uid):
            sessions, reports = history(uid)
            root = ROOT / "raw" / f"user{uid}"
            plan = build_plan(train_case, sessions, coach, root)
            memories = {
                "reports": memory(reports),
                "generic": memory(reports, GENERIC),
                "personalized": memory(reports, plan.render()),
            }
            frozen_json(root / "memories.json", memories)
            print(json.dumps({"prepared": uid}), flush=True)

        # Serial coach calls fit conservative full-context reservations at the current cap.
        for uid in USERS:
            prepare(uid)
        memories = {u: ROOT / "raw" / f"user{u}" / "memories.json" for u in USERS}
        frozen_json(
            ROOT / "frozen.json",
            {
                "protocol_sha256": digest(ROOT / "protocol.json"),
                "memories": {str(p): digest(p) for p in memories.values()},
            },
        )
        for phase_index, phase in enumerate(CASES):

            def assess(job, phase=phase, phase_index=phase_index):
                uid, case_index = job
                name, role = CASES[phase][case_index]
                case = load_case(f"data/cases/{name}.json")
                root = ROOT / phase / name / f"user{uid}"
                wrapped = Learner(learner)
                exp = Experiment(
                    case,
                    role,
                    root,
                    {
                        "protocol_sha256": digest(ROOT / "protocol.json"),
                        "user": uid,
                        "phase": phase,
                        "case": name,
                    },
                    None,
                    wrapped,
                )
                mem = json.loads(memories[uid].read_text())
                seed = SEED + phase_index * 100000 + case_index * 10000 + uid * 100
                arms = list(ARMS)
                random.Random(seed).shuffle(arms)
                rows = []
                for arm in arms:
                    traits = traits_for(uid)
                    original = traits.model_dump()
                    s = exp.episode(f"user{uid}_{arm}", traits, 3, None, seed, mem[arm])
                    assert traits.model_dump() == original
                    rows.append(record(case, s, uid, case_id=name, phase=phase, arm=arm))
                    write_json(root / "rows.json", rows)
                    write_json(root / "raw" / "private_intents.json", wrapped.notes)
                    print(
                        json.dumps(
                            {
                                "phase": phase,
                                "case": name,
                                "user": uid,
                                "arm": arm,
                                "R": rows[-1]["R"],
                            }
                        ),
                        flush=True,
                    )
                return rows

            with ThreadPoolExecutor(max_workers=3) as pool:
                rows = [
                    r
                    for rr in pool.map(assess, [(u, c) for u in USERS for c in range(2)])
                    for r in rr
                ]
            assert len(rows) == 48
            frozen_json(ROOT / f"{phase}_rows.json", rows)
            if phase == "development":
                selection = {
                    str(u): choose(
                        {
                            a: [r["R"] for r in rows if r["user"] == u and r["arm"] == a]
                            for a in ARMS
                        }
                    )
                    for u in USERS
                }
                frozen_json(
                    ROOT / "selection.json",
                    {
                        "selected": selection,
                        "development_sha256": digest(ROOT / f"{phase}_rows.json"),
                        "frozen_sha256": digest(ROOT / "frozen.json"),
                    },
                )
            else:
                selection = json.loads((ROOT / "selection.json").read_text())["selected"]
                averages = {
                    str(u): {
                        a: sum(r["R"] for r in rows if r["user"] == u and r["arm"] == a) / 2
                        for a in ARMS
                    }
                    for u in USERS
                }
                effects = {
                    control: paired_stats(
                        [
                            averages[str(u)][selection[str(u)]] - averages[str(u)][control]
                            for u in USERS
                        ]
                    )
                    for control in ("reports", "generic")
                }
                frozen_json(
                    ROOT / "summary.json",
                    {
                        "validation_means": averages,
                        "selected": selection,
                        "selected_minus_control": effects,
                        "advance_pass": all(e["confirmation_pass"] for e in effects.values()),
                        "scope": protocol["limits"],
                    },
                )
    finally:
        write_json(
            ROOT / f"usage_{attempt}.json",
            {
                "before": before,
                "after": ledger.snapshot(),
                "learner": learner.usage.snapshot(),
                "coach": coach.usage.snapshot(),
            },
        )


if __name__ == "__main__":
    main()
