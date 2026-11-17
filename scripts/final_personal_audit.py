"""Unconditional final audit of the frozen personal-plan method on two unused cases."""

from __future__ import annotations

import argparse
import itertools
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from adaptive_memory import GENERIC, Plan, build_plan, memory
from consolidation_ablate import source_hash
from consolidation_evaluate import frozen_json
from evaluate_fresh_confirmation import Learner, record
from negotrain.budget import SpendLedger
from negotrain.cases import load_case
from negotrain.evaluation import Experiment, write_json
from negotrain.llm import ClaudeLLM
from train_residual_cohort import ROOT as COHORT
from train_residual_cohort import USERS, digest, load_history, traits_for

ROOT = Path("results/ckpt3/final-personal-audit-v1")
OLD_PLANS = Path("results/ckpt3/corrected-adaptive-memory-v1/raw")
SEED = 2822122808
ARMS = ("reports", "generic", "personalized")
CASES = (("pine_learning", "district"), ("willow_kitchen", "nonprofit"))


def paired_stats(values):
    if len(values) != 16 or not np.isfinite(values).all():
        raise ValueError("sixteen complete finite history-level differences required")
    data = np.asarray(values, dtype=float)
    signs = np.array(list(itertools.product((-1, 1), repeat=16)), dtype=np.int8)
    mean = float(data.mean())
    distribution = (signs @ data) / 16
    p = float(np.mean(np.abs(distribution) >= abs(mean) - 1e-12))
    bootstrap = np.random.default_rng(SEED).choice(data, size=(10000, 16)).mean(axis=1)
    return {
        "n": 16,
        "mean": mean,
        "ci95": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        "exact_sign_flip_p_two_sided": p,
        "positive_and_p_05": mean > 0 and p <= 0.05,
    }


def protocol():
    sources = (
        "final_personal_audit.py",
        "adaptive_memory.py",
        "train_residual_cohort.py",
        "evaluate_fresh_confirmation.py",
        "persona_decision.py",
        "persona_instructions.py",
        "probe_isolated_personas.py",
    )
    value = {
        "seed": SEED,
        "users": list(USERS),
        "arms": list(ARMS),
        "tier": 3,
        "core_sha256": source_hash(),
        "sources": {n: digest(Path("scripts") / n) for n in sources},
        "cohort_protocol_sha256": digest(COHORT / "training_protocol.json"),
        "old_plans": {
            str(OLD_PLANS / f"user{u}" / "plan.json"): digest(OLD_PLANS / f"user{u}" / "plan.json")
            for u in range(8)
        },
        "cases": [
            {
                "id": name,
                "role": role,
                "path": f"data/cases/{name}.json",
                "sha256": digest(Path(f"data/cases/{name}.json")),
            }
            for name, role in CASES
        ],
        "case_allocation_sha256": digest(ROOT / "case_allocation_amendment.json"),
        "traits": {str(u): traits_for(u).model_dump() for u in USERS},
        "learner": "claude-sonnet-5-5",
        "coach": "claude-opus-5-5",
        "effort": "low",
        "counterpart": "rule-based economic controller and templated dialogue",
        "expected_assessments": 96,
        "expected_new_plan_calls": 8,
        "primary": "Personalized minus reports AND personalized minus generic; average the "
        "two cases within each of sixteen independent practice histories first",
        "confirmation_rule": "Both means positive and both exact two-sided sign-flip p<=.05, "
        "all 96 outcomes complete and independently verified",
        "method": "Unchanged one-shot personal-plan generator from dd19a8d; all five reports "
        "retained, no per-user arm selector, no residual-advice amendment",
        "prior_evidence": "The prior selector failed its joint development gate. The personal "
        "plan had the highest secondary mean, without established superiority "
        "over generic advice. This unconditional final audit does not change "
        "that failed gate or qualify the candidate retroactively.",
        "limits": "Two synthetic cases, sixteen stochastic histories of two prompt profiles; "
        "eight histories reused, eight new; incomplete full-session calibration; "
        "no human or six-weakness claim",
        "exclusions": "No Sim4/Cedar or final-case dialogue, scores or utilities enter plan "
        "generation. No feedback, tuning or retries based on final outcomes.",
        "estimated_additional_api_usd": 10,
    }
    frozen_json(ROOT / "protocol.json", value)
    return value


def prepare(p):
    histories = json.loads((COHORT / "histories_frozen.json").read_text())
    for path, sha in histories["history"].items():
        assert digest(Path(path)) == sha
    ledger = SpendLedger(".api-budget.sqlite3.ckpt3-dev")
    before = ledger.snapshot()
    coach = ClaudeLLM(model=p["coach"], effort="low", ledger=ledger)
    case = load_case("data/cases/private/sim3_inferred.json")
    attempt = len(list(ROOT.glob("usage_prepare_*.json")))
    try:
        quality = []
        for uid in USERS:
            sessions, reports = load_history(uid)
            root = ROOT / "raw" / f"user{uid}"
            if uid < 8:
                old_path = OLD_PLANS / f"user{uid}" / "plan.json"
                plan = Plan.model_validate(json.loads(old_path.read_text())["output"])
                frozen_json(root / "plan.json", json.loads(old_path.read_text()))
            else:
                plan = build_plan(case, sessions, coach, root)
            allowed = {(s.id, t.index) for s in sessions for t in s.turns if t.speaker == "user"}
            assert all(
                (c.session_id, c.turn) in allowed for rule in plan.rules for c in rule.evidence
            )
            memories = {
                "reports": memory(reports),
                "generic": memory(reports, GENERIC),
                "personalized": memory(reports, plan.render()),
            }
            frozen_json(root / "memories.json", memories)
            quality.append(
                {"user": uid, "words": len(plan.render().split()), "reused_exact_plan": uid < 8}
            )
            print(json.dumps({"phase": "prepare", "user": uid}), flush=True)
        files = [
            ROOT / "raw" / f"user{u}" / name
            for u in USERS
            for name in ("plan.json", "memories.json")
        ]
        frozen_json(
            ROOT / "frozen.json",
            {
                "protocol_sha256": digest(ROOT / "protocol.json"),
                "cohort_freeze_sha256": digest(COHORT / "histories_frozen.json"),
                "history": histories["history"],
                "memories": {str(f): digest(f) for f in files},
            },
        )
        write_json(
            ROOT / "plan_quality.json",
            {
                "rows": quality,
                "scope": "Original generator and its known soft length/portability limits "
                "are retained. No plan selection or rewriting from final scores.",
            },
        )
    finally:
        write_json(
            ROOT / f"usage_prepare_{attempt}.json",
            {
                "before": before,
                "after": ledger.snapshot(),
                "coach": coach.usage.snapshot(),
            },
        )


def assess(p):
    frozen = json.loads((ROOT / "frozen.json").read_text())
    assert frozen["protocol_sha256"] == digest(ROOT / "protocol.json")
    for mapping in (frozen["history"], frozen["memories"]):
        for path, sha in mapping.items():
            assert digest(Path(path)) == sha
    ledger = SpendLedger(".api-budget.sqlite3.ckpt3-final")
    before = ledger.snapshot()
    learner = ClaudeLLM(model=p["learner"], effort="low", ledger=ledger)
    attempt = len(list(ROOT.glob("usage_assess_*.json")))

    def run(job):
        uid, ci = job
        name, role = CASES[ci]
        case = load_case(f"data/cases/{name}.json")
        root = ROOT / "assessment" / name / f"user{uid}"
        wrapped = Learner(learner)
        exp = Experiment(
            case,
            role,
            root,
            {
                "protocol_sha256": digest(ROOT / "protocol.json"),
                "user": uid,
                "case": name,
            },
            None,
            wrapped,
        )
        memories = json.loads((ROOT / "raw" / f"user{uid}" / "memories.json").read_text())
        seed = SEED + ci * 10000 + uid * 100
        arms = list(ARMS)
        random.Random(seed).shuffle(arms)
        rows = []
        for arm in arms:
            traits = traits_for(uid)
            initial = traits.model_dump()
            s = exp.episode(f"user{uid}_{arm}", traits, 3, None, seed, memories[arm])
            assert traits.model_dump() == initial
            rows.append(record(case, s, uid, case_id=name, arm=arm))
            write_json(root / "rows.json", rows)
            write_json(root / "raw" / "private_intents.json", wrapped.notes)
            print(
                json.dumps(
                    {"phase": "final", "case": name, "user": uid, "arm": arm, "R": rows[-1]["R"]}
                ),
                flush=True,
            )
        return rows

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = [
                r for rr in pool.map(run, [(u, c) for u in USERS for c in range(2)]) for r in rr
            ]
        assert len(rows) == 96
        write_json(ROOT / "assessment_rows.json", rows)
        means = {
            str(u): {
                a: sum(r["R"] for r in rows if r["user"] == u and r["arm"] == a) / 2 for a in ARMS
            }
            for u in USERS
        }
        effects = {
            control: paired_stats(
                [means[str(u)]["personalized"] - means[str(u)][control] for u in USERS]
            )
            for control in ("reports", "generic")
        }
        write_json(
            ROOT / "summary.json",
            {
                "history_level_means": means,
                "personalized_minus_control": effects,
                "confirmation_pass": all(e["positive_and_p_05"] for e in effects.values()),
                "scope": p["limits"],
            },
        )
    finally:
        write_json(
            ROOT / f"usage_assess_{attempt}.json",
            {
                "before": before,
                "after": ledger.snapshot(),
                "learner": learner.usage.snapshot(),
            },
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("freeze", "prepare", "assess"))
    args = parser.parse_args()
    p = protocol()
    if args.phase == "prepare":
        prepare(p)
    elif args.phase == "assess":
        assess(p)


if __name__ == "__main__":
    main()
