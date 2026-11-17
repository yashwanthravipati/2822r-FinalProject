"""Verify all fresh Cedar confirmation outcomes, frozen memories and paired inference."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np

from consolidation_ablate import source_hash
from evaluate_fresh_confirmation import ROOT, SEED, TIERS, USERS
from negotrain.cases import load_case
from negotrain.cases.offers import points
from negotrain.counterpart import RuleBasedCounterpart
from negotrain.evaluation import write_json
from negotrain.profiling.observations import ERRORS, observe
from negotrain.schemas import Session
from verify_ckpt3 import economics


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((ROOT / "protocol.json").read_text())
    frozen = json.loads((ROOT / "frozen.json").read_text())
    assert protocol["core_sha256"] == frozen["core_sha256"] == source_hash()
    assert digest(ROOT / "protocol.json") == frozen["protocol_sha256"]
    for name, sha in protocol["sources"].items():
        assert digest(Path("scripts") / name) == sha
    train = load_case("data/cases/private/sim3_inferred.json")
    test = load_case("data/cases/cedar_warehouse.json")
    for case, key in ((train, "training"), (test, "test")):
        assert (
            hashlib.sha256(case.model_dump_json().encode()).hexdigest()
            == protocol[f"{key}_case_sha256"]
        )
    train_rows = json.loads((ROOT / "training_rows.json").read_text())
    test_rows = json.loads((ROOT / "assessment_rows.json").read_text())
    assert len(train_rows) == 40 and len(test_rows) == 16
    assert {(r["user"], r["stage"]) for r in train_rows} == {
        (u, t) for u in USERS for t in range(5)
    }
    assert {(r["user"], r["arm"]) for r in test_rows} == {
        (u, a) for u in USERS for a in protocol["arms"]
    }
    diagnostics = {"practice": [], "assessment": []}
    for phase, rows, case, role in (
        ("practice", train_rows, train, "officer"),
        ("assessment", test_rows, test, "owner"),
    ):
        score, best = economics(case, role)
        for row in rows:
            uid = row["user"]
            if phase == "practice":
                t = row["stage"]
                root = ROOT / "train" / f"user{uid}"
                key, tier, seed = f"user{uid}_practice{t}", TIERS[t], SEED + uid * 1009 + t
            else:
                root = ROOT / "assess" / f"user{uid}"
                key, tier, seed = f"user{uid}_{row['arm']}", 3, SEED + 10000 + uid
            path = root / "raw" / f"{key}.json"
            raw = json.loads(path.read_text())
            assert raw["complete"]
            session = Session.model_validate(raw["session"])
            assert session.case_id == case.id and session.user_role_id == role
            assert session.counterpart_role_id == case.other_role(role).id
            assert (
                session.counterpart_profile.tier == tier
                and session.counterpart_profile.focus is None
            )
            assert session.seed == seed
            assert math.isclose(score(raw["session"]), row["R"], abs_tol=1e-12)
            replay = Session(
                id=session.id,
                case_id=case.id,
                user_role_id=role,
                counterpart_role_id=session.counterpart_role_id,
                counterpart_profile=session.counterpart_profile,
                seed=seed,
            )
            bot = RuleBasedCounterpart(
                case, session.counterpart_role_id, session.counterpart_profile
            )
            violations = 0
            for turn in session.turns:
                if replay.turns:
                    assert turn.speaker != replay.turns[-1].speaker
                if turn.speaker == "counterpart":
                    package = turn.offer or (
                        replay.latest_offer_from("user") if turn.accept else None
                    )
                    if package:
                        violations += points(
                            case, session.counterpart_role_id, package
                        ) < bot.minimum(replay)
                replay.add_turn(turn, case)
            assert replay.status == session.status and replay.agreement == session.agreement
            assert violations == raw["schedule_violations"] == 0
            obs = observe(session, case)
            assert obs.untagged_user_turns == 0
            assert row["counts"] == {k: obs.counts[k].model_dump(exclude={"turns"}) for k in ERRORS}
            diagnostics[phase].append(
                {
                    "id": key,
                    "R": row["R"],
                    "status": session.status,
                    "below_walkaway": row["R"] < 0,
                    "feasible_best": best,
                    "raw_sha256": digest(path),
                }
            )
    for uid in USERS:
        root = ROOT / "train" / f"user{uid}" / "raw"
        assert digest(root / "reports.json") == frozen["memories"][str(uid)]
        reports = json.loads((root / "reports.json").read_text())
        assert len(reports) == 5
        for t, report in enumerate(reports):
            debrief = json.loads((root / f"user{uid}_practice{t}.feedback.json").read_text())
            assert json.loads(report) == debrief["report"]
            assert debrief["report"]["source"] == "llm"
        assert not list((ROOT / "assess" / f"user{uid}" / "raw").glob("*.feedback.json"))
    summary = json.loads((ROOT / "summary.json").read_text())
    diffs = []
    for uid in USERS:
        values = {r["arm"]: r["R"] for r in test_rows if r["user"] == uid}
        diff = values["five_reports"] - values["no_feedback"]
        pair = next(p for p in summary["pairs"] if p["user"] == uid)
        assert all(math.isclose(pair[k], v, abs_tol=1e-12) for k, v in values.items())
        assert math.isclose(pair["difference"], diff, abs_tol=1e-12)
        diffs.append(diff)
    assert math.isclose(summary["paired_effect"]["mean"], np.mean(diffs), abs_tol=1e-12)
    bootstrap = (
        np.random.default_rng(SEED)
        .choice(diffs, size=(2000, len(diffs)), replace=True)
        .mean(axis=1)
    )
    permutations = [
        np.mean(np.array(diffs) * signs) for signs in itertools.product((-1, 1), repeat=len(diffs))
    ]
    usage = [json.loads(p.read_text()) for p in ROOT.glob("usage_*.json")]
    result = {
        "verified_practice_episodes": 40,
        "verified_test_episodes": 16,
        "schedule_violations": 0,
        "missing_annotations": 0,
        "paired_mean": float(np.mean(diffs)),
        "empirical_bootstrap_ci95": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        "exact_sign_flip_p_two_sided": sum(
            abs(x) >= abs(np.mean(diffs)) - 1e-12 for x in permutations
        )
        / len(permutations),
        "ledger_cost_usd": sum(u["after"]["actual_usd"] - u["before"]["actual_usd"] for u in usage),
        "requests": sum(u["after"]["requests"] - u["before"]["requests"] for u in usage),
        "core_sha256": source_hash(),
        "diagnostics": diagnostics,
    }
    effect = summary["paired_effect"]
    assert effect["exact_sign_flip_p_two_sided"] == result["exact_sign_flip_p_two_sided"]
    assert effect["confirmation_pass"] == (
        result["paired_mean"] > 0 and result["exact_sign_flip_p_two_sided"] <= 0.05
    )
    result["confirmation_pass"] = effect["confirmation_pass"]
    assert np.allclose(effect["ci95"], result["empirical_bootstrap_ci95"], atol=1e-12)
    write_json(ROOT / "verification.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "diagnostics"}, indent=2))


if __name__ == "__main__":
    main()
