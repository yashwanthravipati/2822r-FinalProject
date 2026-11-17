"""Frozen five-session Sim3 practice and paired coached/uncoached Sim4 evaluation."""

from __future__ import annotations

import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from consolidation_ablate import source_hash
from consolidation_evaluate import frozen_json
from negotrain.budget import SpendLedger
from negotrain.cases import load_case
from negotrain.evaluation import Experiment, interval, write_json
from negotrain.llm import ClaudeLLM
from negotrain.profiling.observations import ERRORS, observe
from negotrain.simulation import episode_score
from negotrain.virtual_users import VirtualTraits
from persona_decision import IntentLLM
from persona_instructions import ENACTMENT
from probe_isolated_personas import SCOPE

ROOT = Path("results/ckpt3/corrected-transfer-v1")
SEED = 2822111804
USERS = (0, 1, 2, 3)
TIERS = (2, 2, 4, 4, 4)


class Learner(IntentLLM):
    def parse(self, system, messages, output_type, **kwargs):
        if output_type.__name__ == "CounterpartMove":
            system = system.append_uncached(ENACTMENT + SCOPE)
        return super().parse(system, messages, output_type, **kwargs)


def traits_for(uid):
    target = "error:1" if uid < 2 else "error:2"
    return VirtualTraits(errors={target: 0.9}, awareness=0.5, rapport=0.5, response={})


def record(case, session, uid, **fields):
    obs = observe(session, case)
    return {
        "user": uid,
        **fields,
        "R": episode_score(case, session),
        "status": session.status,
        "user_turns": session.user_turns,
        "counts": {k: obs.counts[k].model_dump(exclude={"turns"}) for k in ERRORS},
    }


def main():
    train_case = load_case("data/cases/private/sim3_inferred.json")
    test_case = load_case("data/cases/private/sim4_inferred.json")
    sources = (
        "evaluate_corrected_transfer.py",
        "persona_decision.py",
        "persona_instructions.py",
        "probe_isolated_personas.py",
    )
    protocol = {
        "core_sha256": source_hash(),
        "sources": {
            n: hashlib.sha256((Path("scripts") / n).read_bytes()).hexdigest() for n in sources
        },
        "training_case_sha256": hashlib.sha256(train_case.model_dump_json().encode()).hexdigest(),
        "test_case_sha256": hashlib.sha256(test_case.model_dump_json().encode()).hexdigest(),
        "training_role": "officer",
        "test_role": "global_relief",
        "seed": SEED,
        "users": list(USERS),
        "training_tiers": list(TIERS),
        "test_tier": 3,
        "traits": {str(u): traits_for(u).model_dump() for u in USERS},
        "learner": "claude-sonnet-5-5",
        "coach": "claude-opus-5-5",
        "effort": "low",
        "counterpart": "rule-based economic controller and templated dialogue",
        "persona": "Concrete enactment with private intent; only one concession weakness specified",
        "arms": ["no_feedback", "five_reports"],
        "learn_updates": False,
        "expected_practice_episodes": 20,
        "expected_test_episodes": 8,
        "primary": "Mean paired Sim4 R(five_reports) - R(no_feedback), four learners",
        "limits": "Small exploratory evaluation; only two controls passed one-step diagnostic; "
        "full-session calibration unproven; inferred utilities; no human claim",
        "heldout_policy": "No Sim4 practice, feedback, or tuning in this run; "
        "Sim4 was examined in historical studies and is a revisited benchmark",
    }
    frozen_json(ROOT / "protocol.json", protocol)
    dev = SpendLedger(".api-budget.sqlite3.ckpt3-dev")
    dev_before = dev.snapshot()
    user_llm = ClaudeLLM(model=protocol["learner"], effort="low", ledger=dev)
    coach = ClaudeLLM(model=protocol["coach"], effort="low", ledger=dev)
    dev_attempt = len(list(ROOT.glob("usage_dev_*.json")))

    def train(uid):
        root = ROOT / "train" / f"user{uid}"
        wrapped = Learner(user_llm)
        config = {**protocol, "user": uid, "phase": "practice"}
        practice = Experiment(train_case, "officer", root, config, None, wrapped)
        # This second object is used only to generate post-session debriefs.
        debrief = Experiment(train_case, "officer", root, config, coach, wrapped)
        traits = traits_for(uid)
        original = traits.model_dump()
        reports, rows = [], []
        for t, tier in enumerate(TIERS):
            session = practice.episode(
                f"user{uid}_practice{t}", traits, tier, None, SEED + uid * 1009 + t, reports
            )
            feedback = debrief.feedback(session)
            reports.append(feedback.report.model_dump_json())
            rows.append(
                record(train_case, session, uid, stage=t, feedback_source=feedback.report.source)
            )
            write_json(root / "rows.json", rows)
            write_json(root / "raw" / "reports.json", reports)
            if wrapped.notes:
                write_json(root / "raw" / "private_intents.json", wrapped.notes)
            print(json.dumps({"phase": "practice", "user": uid, "complete": t + 1}), flush=True)
        assert traits.model_dump() == original
        return rows

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            train_rows = [row for group in pool.map(train, USERS) for row in group]
        write_json(ROOT / "training_rows.json", train_rows)
    finally:
        write_json(
            ROOT / f"usage_dev_{dev_attempt}.json",
            {
                "before": dev_before,
                "after": dev.snapshot(),
                "learner": user_llm.usage.snapshot(),
                "coach": coach.usage.snapshot(),
            },
        )
    assert len(train_rows) == 20
    assert all(r["feedback_source"] == "llm" for r in train_rows), (
        "Template fallback; stop before test"
    )
    memories = {str(u): ROOT / "train" / f"user{u}" / "raw" / "reports.json" for u in USERS}
    frozen_json(
        ROOT / "frozen.json",
        {
            "protocol_sha256": hashlib.sha256((ROOT / "protocol.json").read_bytes()).hexdigest(),
            "memories": {
                u: hashlib.sha256(p.read_bytes()).hexdigest() for u, p in memories.items()
            },
            "core_sha256": source_hash(),
        },
    )
    final = SpendLedger(".api-budget.sqlite3.ckpt3-final")
    final_before = final.snapshot()
    final_llm = ClaudeLLM(model=protocol["learner"], effort="low", ledger=final)
    final_attempt = len(list(ROOT.glob("usage_final_*.json")))

    def assess(uid):
        wrapped = Learner(final_llm)
        root = ROOT / "assess" / f"user{uid}"
        exp = Experiment(
            test_case,
            "global_relief",
            root,
            {**protocol, "user": uid, "phase": "assessment"},
            None,
            wrapped,
        )
        reports = json.loads(memories[str(uid)].read_text())
        assert len(reports) == 5
        arms = list(protocol["arms"])
        random.Random(SEED + uid).shuffle(arms)
        traits = traits_for(uid)
        original = traits.model_dump()
        rows = []
        for arm in arms:
            session = exp.episode(
                f"user{uid}_{arm}",
                traits,
                3,
                None,
                SEED + 10000 + uid,
                reports if arm == "five_reports" else [],
            )
            rows.append(record(test_case, session, uid, arm=arm))
            write_json(root / "rows.json", rows)
            if wrapped.notes:
                write_json(root / "raw" / "private_intents.json", wrapped.notes)
            print(
                json.dumps({"phase": "assessment", "user": uid, "arm": arm, "R": rows[-1]["R"]}),
                flush=True,
            )
        assert traits.model_dump() == original
        return rows

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = [row for group in pool.map(assess, USERS) for row in group]
        write_json(ROOT / "assessment_rows.json", rows)
        pairs = []
        for uid in USERS:
            values = {r["arm"]: r["R"] for r in rows if r["user"] == uid}
            pairs.append(
                {
                    "user": uid,
                    **values,
                    "difference": values["five_reports"] - values["no_feedback"],
                }
            )
        write_json(
            ROOT / "summary.json",
            {
                "practice_episodes": len(train_rows),
                "test_episodes": len(rows),
                "pairs": pairs,
                "paired_effect": interval([p["difference"] for p in pairs], seed=SEED),
                "scope": protocol["limits"],
            },
        )
    finally:
        write_json(
            ROOT / f"usage_final_{final_attempt}.json",
            {
                "before": final_before,
                "after": final.snapshot(),
                "learner": final_llm.usage.snapshot(),
            },
        )


if __name__ == "__main__":
    main()
