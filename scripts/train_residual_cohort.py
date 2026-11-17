"""Add eight fresh practice histories to the eight existing corrected histories."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from consolidation_ablate import source_hash
from consolidation_evaluate import frozen_json
from evaluate_fresh_confirmation import TIERS, Learner, record
from evaluate_fresh_confirmation import traits_for as original_traits
from negotrain.budget import SpendLedger
from negotrain.cases import load_case
from negotrain.evaluation import Experiment, write_json
from negotrain.llm import ClaudeLLM
from negotrain.schemas import Session

ROOT = Path("results/ckpt3/corrected-residual-v1")
SEED = 2822122807
USERS = tuple(range(16))
NEW_USERS = tuple(range(8, 16))
OLD = Path("results/ckpt3/corrected-confirmation-v1/train")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def traits_for(uid):
    if uid not in USERS:
        raise ValueError("unplanned replicate")
    return original_traits(uid % 8)


def history_root(uid):
    return (OLD if uid < 8 else ROOT / "train") / f"user{uid}" / "raw"


def load_history(uid):
    root = history_root(uid)
    sessions = []
    for t, tier in enumerate(TIERS):
        raw = json.loads((root / f"user{uid}_practice{t}.json").read_text())
        session = Session.model_validate(raw["session"])
        if not raw["complete"] or session.status == "active":
            raise ValueError("incomplete history")
        if session.user_role_id != "officer" or session.counterpart_profile.tier != tier:
            raise ValueError("wrong source training role or tier")
        sessions.append(session)
    reports = json.loads((root / "reports.json").read_text())
    if len(reports) != 5 or any(json.loads(r)["source"] != "llm" for r in reports):
        raise ValueError("five genuine coaching reports required")
    return sessions, reports


def main():
    case_path = Path("data/cases/private/sim3_inferred.json")
    case = load_case(case_path)
    old = [OLD / f"user{u}" / "raw" / "reports.json" for u in range(8)]
    old += [
        OLD / f"user{u}" / "raw" / f"user{u}_practice{t}.json" for u in range(8) for t in range(5)
    ]
    sources = (
        "train_residual_cohort.py",
        "evaluate_fresh_confirmation.py",
        "persona_decision.py",
        "persona_instructions.py",
        "probe_isolated_personas.py",
    )
    protocol = {
        "seed": SEED,
        "new_users": list(NEW_USERS),
        "all_users": list(USERS),
        "core_sha256": source_hash(),
        "case_sha256": digest(case_path),
        "sources": {n: digest(Path("scripts") / n) for n in sources},
        "old_histories": {str(p): digest(p) for p in old},
        "tiers": list(TIERS),
        "role": "officer",
        "expected_new_practices": 40,
        "traits": {str(u): traits_for(u).model_dump() for u in USERS},
        "learner": "claude-sonnet-5-5",
        "coach": "claude-opus-5-5",
        "effort": "low",
        "limits": "16 stochastic histories of two concession profiles, not 16 human types",
        "learn_updates": False,
    }
    frozen_json(ROOT / "training_protocol.json", protocol)
    ledger = SpendLedger(".api-budget.sqlite3.ckpt3-dev")
    before = ledger.snapshot()
    learner = ClaudeLLM(model=protocol["learner"], effort="low", ledger=ledger)
    coach = ClaudeLLM(model=protocol["coach"], effort="low", ledger=ledger)
    attempt = len(list(ROOT.glob("usage_train_*.json")))

    def train(uid):
        root = ROOT / "train" / f"user{uid}"
        wrapped = Learner(learner)
        config = {"training_protocol_sha256": digest(ROOT / "training_protocol.json"), "user": uid}
        practice = Experiment(case, "officer", root, config, None, wrapped)
        debrief = Experiment(case, "officer", root, config, coach, wrapped)
        traits = traits_for(uid)
        original = traits.model_dump()
        reports, rows = [], []
        for t, tier in enumerate(TIERS):
            s = practice.episode(
                f"user{uid}_practice{t}", traits, tier, None, SEED + uid * 1009 + t, reports
            )
            report = debrief.feedback(s).report
            if report.source != "llm":
                raise ValueError("template fallback in training")
            reports.append(report.model_dump_json())
            rows.append(record(case, s, uid, stage=t, feedback_source=report.source))
            write_json(root / "rows.json", rows)
            write_json(root / "raw" / "reports.json", reports)
            write_json(root / "raw" / "private_intents.json", wrapped.notes)
            print(json.dumps({"phase": "practice", "user": uid, "complete": t + 1}), flush=True)
        assert traits.model_dump() == original
        return rows

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = [r for group in pool.map(train, NEW_USERS) for r in group]
        assert len(rows) == 40
        write_json(ROOT / "training_rows.json", rows)
        files = [history_root(u) / "reports.json" for u in USERS]
        files += [history_root(u) / f"user{u}_practice{t}.json" for u in USERS for t in range(5)]
        for u in USERS:
            load_history(u)
        frozen_json(
            ROOT / "histories_frozen.json",
            {
                "training_protocol_sha256": digest(ROOT / "training_protocol.json"),
                "history": {str(p): digest(p) for p in files},
            },
        )
    finally:
        write_json(
            ROOT / f"usage_train_{attempt}.json",
            {
                "before": before,
                "after": ledger.snapshot(),
                "learner": learner.usage.snapshot(),
                "coach": coach.usage.snapshot(),
            },
        )


if __name__ == "__main__":
    main()
