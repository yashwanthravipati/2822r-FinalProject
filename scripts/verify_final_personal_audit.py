"""Verify every final comparison, practice source, frozen memory and inference."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from adaptive_memory import GENERIC, Plan
from consolidation_ablate import source_hash
from final_personal_audit import ARMS, CASES, OLD_PLANS, ROOT, SEED
from negotrain.cases import load_case
from negotrain.cases.offers import points
from negotrain.counterpart import RuleBasedCounterpart
from negotrain.evaluation import write_json
from negotrain.profiling.observations import ERRORS, observe
from negotrain.schemas import Session
from train_residual_cohort import ROOT as COHORT
from train_residual_cohort import SEED as TRAIN_SEED
from train_residual_cohort import USERS, digest, history_root, load_history
from verify_ckpt3 import economics


def audit_episode(path, case, role, tier, seed, row=None):
    raw = json.loads(path.read_text())
    assert raw["complete"]
    s = Session.model_validate(raw["session"])
    assert s.case_id == case.id and s.user_role_id == role
    assert s.counterpart_role_id == case.other_role(role).id and s.seed == seed
    assert s.counterpart_profile.tier == tier and s.counterpart_profile.focus is None
    score, best = economics(case, role)
    value = score(raw["session"])
    replay = Session(
        id=s.id,
        case_id=case.id,
        user_role_id=role,
        counterpart_role_id=s.counterpart_role_id,
        counterpart_profile=s.counterpart_profile,
        seed=seed,
    )
    bot = RuleBasedCounterpart(case, s.counterpart_role_id, s.counterpart_profile)
    violations = 0
    for turn in s.turns:
        if replay.turns:
            assert turn.speaker != replay.turns[-1].speaker
        if turn.speaker == "counterpart":
            package = turn.offer or (replay.latest_offer_from("user") if turn.accept else None)
            if package:
                violations += points(case, s.counterpart_role_id, package) < bot.minimum(replay)
        replay.add_turn(turn, case)
    assert replay.status == s.status and replay.agreement == s.agreement
    assert violations == raw["schedule_violations"] == 0
    obs = observe(s, case)
    assert obs.untagged_user_turns == 0
    if row is not None:
        assert math.isclose(value, row["R"], abs_tol=1e-12)
        assert s.status == row["status"]
        assert row["counts"] == {k: obs.counts[k].model_dump(exclude={"turns"}) for k in ERRORS}
    return {
        "raw_sha256": digest(path),
        "R": value,
        "status": s.status,
        "below_walkaway": value < 0,
        "feasible_best": best,
    }


def inference(values):
    assert len(values) == 16 and np.isfinite(values).all()
    data = np.array(values)
    signed_sums = np.array([0.0])
    for v in data:
        signed_sums = np.concatenate((signed_sums + v, signed_sums - v))
    mean = float(np.mean(data))
    p = float(np.mean(np.abs(signed_sums / 16) >= abs(mean) - 1e-12))
    bootstrap = np.random.default_rng(SEED).choice(data, size=(10000, 16)).mean(axis=1)
    return {
        "mean": mean,
        "ci95": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        "exact_sign_flip_p_two_sided": p,
    }


def main():
    protocol = json.loads((ROOT / "protocol.json").read_text())
    frozen = json.loads((ROOT / "frozen.json").read_text())
    assert source_hash() == protocol["core_sha256"]
    assert frozen["protocol_sha256"] == digest(ROOT / "protocol.json")
    assert frozen["cohort_freeze_sha256"] == digest(COHORT / "histories_frozen.json")
    assert protocol["cohort_protocol_sha256"] == digest(COHORT / "training_protocol.json")
    assert protocol["case_allocation_sha256"] == digest(ROOT / "case_allocation_amendment.json")
    for name, sha in protocol["sources"].items():
        assert digest(Path("scripts") / name) == sha
    for mapping in (frozen["history"], frozen["memories"], protocol["old_plans"]):
        for path, sha in mapping.items():
            assert digest(Path(path)) == sha
    amendment = json.loads((ROOT / "case_allocation_amendment.json").read_text())
    assert amendment["original_manifest_sha256"] == digest(COHORT / "confirmation_cases.json")
    assert amendment["prior_recorded_negotiations"] == 0
    training = json.loads((COHORT / "training_protocol.json").read_text())
    for name, sha in training["sources"].items():
        assert digest(Path("scripts") / name) == sha
    assert source_hash() == training["core_sha256"]
    assert digest(Path("data/cases/private/sim3_inferred.json")) == training["case_sha256"]
    train_case = load_case("data/cases/private/sim3_inferred.json")
    old_protocol = json.loads(
        Path("results/ckpt3/corrected-confirmation-v1/protocol.json").read_text()
    )
    practice = []
    for u in USERS:
        sessions, reports = load_history(u)
        for t, _s in enumerate(sessions):
            seed = (old_protocol["seed"] if u < 8 else TRAIN_SEED) + u * 1009 + t
            raw = history_root(u) / f"user{u}_practice{t}.json"
            checked = audit_episode(raw, train_case, "officer", (2, 2, 4, 4, 4)[t], seed)
            practice.append({"user": u, "stage": t, **checked})
            feedback = json.loads(
                (history_root(u) / f"user{u}_practice{t}.feedback.json").read_text()
            )
            assert json.loads(reports[t]) == feedback["report"]
            assert feedback["report"]["source"] == "llm"
        root = ROOT / "raw" / f"user{u}"
        saved_plan = json.loads((root / "plan.json").read_text())
        if u < 8:
            assert saved_plan == json.loads((OLD_PLANS / f"user{u}" / "plan.json").read_text())
        plan = Plan.model_validate(saved_plan["output"])
        valid = {(s.id, t.index) for s in sessions for t in s.turns if t.speaker == "user"}
        assert all((c.session_id, c.turn) in valid for r in plan.rules for c in r.evidence)
        mem = json.loads((root / "memories.json").read_text())
        assert set(mem) == set(ARMS) and mem["reports"] == reports
        for arm, note in (("generic", GENERIC), ("personalized", plan.render())):
            assert len(mem[arm]) == 1
            assert json.loads(mem[arm][0]) == {"practice_advice": note, "original_reports": reports}

    rows = json.loads((ROOT / "assessment_rows.json").read_text())
    assert len(rows) == 96
    assert {(r["user"], r["case_id"], r["arm"]) for r in rows} == {
        (u, c, a) for u in USERS for c, _ in CASES for a in ARMS
    }
    final = []
    for ci, (name, role) in enumerate(CASES):
        path = Path(f"data/cases/{name}.json")
        assert digest(path) == protocol["cases"][ci]["sha256"]
        assert digest(path) == amendment["cases"][ci]["sha256"]
        case = load_case(path)
        for r in [row for row in rows if row["case_id"] == name]:
            u, arm = r["user"], r["arm"]
            root = ROOT / "assessment" / name / f"user{u}" / "raw"
            assert not list(root.glob("*.feedback.json"))
            checked = audit_episode(
                root / f"user{u}_{arm}.json", case, role, 3, SEED + ci * 10000 + u * 100, r
            )
            final.append({"user": u, "case": name, "arm": arm, **checked})
    means = {
        str(u): {a: sum(r["R"] for r in rows if r["user"] == u and r["arm"] == a) / 2 for a in ARMS}
        for u in USERS
    }
    summary = json.loads((ROOT / "summary.json").read_text())
    assert means == summary["history_level_means"]
    effects = {
        c: inference([means[str(u)]["personalized"] - means[str(u)][c] for u in USERS])
        for c in ("reports", "generic")
    }
    for control, effect in effects.items():
        for k, v in effect.items():
            assert np.allclose(v, summary["personalized_minus_control"][control][k], atol=1e-12)
    passed = all(
        e["mean"] > 0 and e["exact_sign_flip_p_two_sided"] <= 0.05 for e in effects.values()
    )
    assert passed == summary["confirmation_pass"]
    usage = [json.loads(p.read_text()) for p in ROOT.glob("usage_*.json")]
    result = {
        "verified_source_practices": 80,
        "verified_final_episodes": 96,
        "schedule_violations": 0,
        "missing_annotations": 0,
        "arm_means": {a: sum(m[a] for m in means.values()) / 16 for a in ARMS},
        "personalized_minus_control": effects,
        "confirmation_pass": passed,
        "target_counts_descriptive": {
            a: {
                key: sum(
                    r["counts"]["error:1" if r["user"] % 8 < 4 else "error:2"][key]
                    for r in rows
                    if r["arm"] == a
                )
                for key in ("occurrences", "opportunities")
            }
            for a in ARMS
        },
        "ledger_cost_usd": sum(u["after"]["actual_usd"] - u["before"]["actual_usd"] for u in usage),
        "requests": sum(u["after"]["requests"] - u["before"]["requests"] for u in usage),
        "diagnostics": {"practice": practice, "final": final},
    }
    write_json(ROOT / "verification.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "diagnostics"}, indent=2))


if __name__ == "__main__":
    main()
