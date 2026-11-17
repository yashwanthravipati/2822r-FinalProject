"""Independent replay, scoring, selection and inference for the corrected memory study."""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np

from adaptive_memory import GENERIC, Plan
from consolidation_ablate import source_hash
from evaluate_adaptive_memory import ARMS, CASES, ROOT, SEED, USERS, digest, history
from negotrain.cases import load_case
from negotrain.cases.offers import points
from negotrain.counterpart import RuleBasedCounterpart
from negotrain.evaluation import write_json
from negotrain.profiling.observations import ERRORS, observe
from negotrain.schemas import Session
from verify_ckpt3 import economics


def inference(differences, seed):
    values = np.array(differences)
    mean = float(values.mean())
    permutations = [np.mean(values * signs) for signs in itertools.product((-1, 1), repeat=8)]
    bootstrap = np.random.default_rng(seed).choice(values, size=(2000, 8)).mean(axis=1)
    return {
        "mean": mean,
        "ci95": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        "exact_sign_flip_p_two_sided": sum(abs(p) >= abs(mean) - 1e-12 for p in permutations) / 256,
    }


def main():
    protocol = json.loads((ROOT / "protocol.json").read_text())
    frozen = json.loads((ROOT / "frozen.json").read_text())
    selection = json.loads((ROOT / "selection.json").read_text())
    summary = json.loads((ROOT / "summary.json").read_text())
    assert protocol["core_sha256"] == source_hash()
    assert frozen["protocol_sha256"] == digest(ROOT / "protocol.json")
    assert selection["frozen_sha256"] == digest(ROOT / "frozen.json")
    assert selection["development_sha256"] == digest(ROOT / "development_rows.json")
    for name, sha in protocol["sources"].items():
        assert digest(Path("scripts") / name) == sha
    for mapping in (protocol["history"], frozen["memories"]):
        for path, sha in mapping.items():
            assert digest(Path(path)) == sha
    assert digest(Path("data/cases/private/sim3_inferred.json")) == protocol["training_case_sha256"]
    for uid in USERS:
        sessions, reports = history(uid)
        root = ROOT / "raw" / f"user{uid}"
        plan = Plan.model_validate(json.loads((root / "plan.json").read_text())["output"])
        allowed = {(s.id, t.index) for s in sessions for t in s.turns if t.speaker == "user"}
        assert all((c.session_id, c.turn) in allowed for r in plan.rules for c in r.evidence)
        mem = json.loads((root / "memories.json").read_text())
        assert set(mem) == set(ARMS) and mem["reports"] == reports and len(reports) == 5
        for arm, note in (("generic", GENERIC), ("personalized", plan.render())):
            assert len(mem[arm]) == 1
            assert json.loads(mem[arm][0]) == {"practice_advice": note, "original_reports": reports}

    all_rows, diagnostics = {}, []
    for phase_index, phase in enumerate(CASES):
        rows = json.loads((ROOT / f"{phase}_rows.json").read_text())
        expected = {(u, c, a) for u in USERS for c, _ in CASES[phase] for a in ARMS}
        assert len(rows) == 48
        assert {(r["user"], r["case_id"], r["arm"]) for r in rows} == expected
        all_rows[phase] = rows
        for case_index, (name, role) in enumerate(CASES[phase]):
            path = Path(f"data/cases/{name}.json")
            assert digest(path) == protocol["cases"][phase][case_index]["sha256"]
            case = load_case(path)
            score, best = economics(case, role)
            for row in [r for r in rows if r["case_id"] == name]:
                uid, arm = row["user"], row["arm"]
                root = ROOT / phase / name / f"user{uid}" / "raw"
                raw_path = root / f"user{uid}_{arm}.json"
                raw = json.loads(raw_path.read_text())
                assert raw["complete"] and not list(root.glob("*.feedback.json"))
                s = Session.model_validate(raw["session"])
                assert s.case_id == name and s.user_role_id == role
                assert s.counterpart_role_id == case.other_role(role).id
                assert s.seed == SEED + phase_index * 100000 + case_index * 10000 + uid * 100
                assert s.counterpart_profile.tier == 3 and s.counterpart_profile.focus is None
                assert math.isclose(score(raw["session"]), row["R"], abs_tol=1e-12)
                replay = Session(
                    id=s.id,
                    case_id=name,
                    user_role_id=role,
                    counterpart_role_id=s.counterpart_role_id,
                    counterpart_profile=s.counterpart_profile,
                    seed=s.seed,
                )
                bot = RuleBasedCounterpart(case, s.counterpart_role_id, s.counterpart_profile)
                violations = 0
                for turn in s.turns:
                    if replay.turns:
                        assert turn.speaker != replay.turns[-1].speaker
                    if turn.speaker == "counterpart":
                        package = turn.offer or (
                            replay.latest_offer_from("user") if turn.accept else None
                        )
                        if package:
                            violations += points(
                                case, s.counterpart_role_id, package
                            ) < bot.minimum(replay)
                    replay.add_turn(turn, case)
                assert replay.status == s.status == row["status"] and s.status != "active"
                assert replay.agreement == s.agreement
                assert violations == raw["schedule_violations"] == 0
                obs = observe(s, case)
                assert obs.untagged_user_turns == 0
                assert row["counts"] == {
                    k: obs.counts[k].model_dump(exclude={"turns"}) for k in ERRORS
                }
                diagnostics.append(
                    {
                        "phase": phase,
                        "case": name,
                        "user": uid,
                        "arm": arm,
                        "raw_sha256": digest(raw_path),
                        "R": row["R"],
                        "status": s.status,
                        "below_walkaway": row["R"] < 0,
                        "feasible_best": best,
                    }
                )
    selected = {}
    for u in USERS:
        means = {
            a: sum(r["R"] for r in all_rows["development"] if r["user"] == u and r["arm"] == a) / 2
            for a in ARMS
        }
        best = sorted(ARMS, key=lambda a: (-means[a], ARMS.index(a)))[0]
        selected[str(u)] = best if means[best] - means["reports"] >= 0.03 else "reports"
    assert selected == selection["selected"] == summary["selected"]
    means = {
        str(u): {
            a: sum(r["R"] for r in all_rows["validation"] if r["user"] == u and r["arm"] == a) / 2
            for a in ARMS
        }
        for u in USERS
    }
    assert means == summary["validation_means"]
    effects = {
        control: inference(
            [means[str(u)][selected[str(u)]] - means[str(u)][control] for u in USERS],
            protocol["bootstrap_seed"],
        )
        for control in ("reports", "generic")
    }
    for control, effect in effects.items():
        recorded = summary["selected_minus_control"][control]
        for key in effect:
            assert np.allclose(effect[key], recorded[key], atol=1e-12)
    advance = all(
        e["mean"] > 0 and e["exact_sign_flip_p_two_sided"] <= 0.05 for e in effects.values()
    )
    assert advance == summary["advance_pass"]
    usage = [json.loads(p.read_text()) for p in ROOT.glob("usage_*.json")]
    target_counts = {}
    for phase, rows in all_rows.items():
        target_counts[phase] = {}
        for arm in ARMS:
            counts = [
                r["counts"]["error:1" if r["user"] < 4 else "error:2"]
                for r in rows
                if r["arm"] == arm
            ]
            target_counts[phase][arm] = {
                key: sum(c[key] for c in counts) for key in ("occurrences", "opportunities")
            }
    result = {
        "verified_episodes": 96,
        "schedule_violations": 0,
        "missing_annotations": 0,
        "validation_arm_means": {a: sum(m[a] for m in means.values()) / 8 for a in ARMS},
        "validation_selected_mean": sum(means[u][a] for u, a in selected.items()) / 8,
        "selected_minus_control": effects,
        "personalized_minus_control_secondary": {
            control: inference(
                [means[str(u)]["personalized"] - means[str(u)][control] for u in USERS],
                protocol["bootstrap_seed"],
            )
            for control in ("reports", "generic")
        },
        "advance_pass": advance,
        "ledger_cost_usd": sum(u["after"]["actual_usd"] - u["before"]["actual_usd"] for u in usage),
        "requests": sum(u["after"]["requests"] - u["before"]["requests"] for u in usage),
        "target_counts_descriptive": target_counts,
        "diagnostics": diagnostics,
    }
    write_json(ROOT / "verification.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "diagnostics"}, indent=2))


if __name__ == "__main__":
    main()
