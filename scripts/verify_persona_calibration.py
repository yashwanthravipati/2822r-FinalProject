"""Verify the corrected behavioral screen from durable sessions without API calls."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from calibrate_personas import CASES, summarize
from consolidation_ablate import source_hash
from negotrain.cases import load_case
from negotrain.cases.offers import points
from negotrain.counterpart import RuleBasedCounterpart
from negotrain.evaluation import write_json
from negotrain.profiling.observations import ERRORS, observe
from negotrain.schemas import Session
from verify_ckpt3 import check, economics


def main():
    root = Path("results/ckpt3/persona-calibration-v1")
    protocol = json.loads((root / "protocol.json").read_text())
    rows = json.loads((root / "rows.json").read_text())
    summary = json.loads((root / "summary.json").read_text())
    check(summary == summarize(rows), "summary disagrees with complete cohort")
    check(source_hash() == protocol["source_sha256"], "core changed")
    check(
        hashlib.sha256(Path("scripts/calibrate_personas.py").read_bytes()).hexdigest()
        == protocol["runner_sha256"],
        "runner changed",
    )
    cases = {name: (load_case(f"data/cases/{name}.json"), role) for name, role in CASES}
    scorers = {}
    for name, (case, role) in cases.items():
        check(
            hashlib.sha256(case.model_dump_json().encode()).hexdigest() == protocol["cases"][name],
            "case changed",
        )
        scorers[name] = economics(case, role)
    check(len(list((root / "raw").glob("*.json"))) == len(rows), "unexpected raw sessions")
    violations = below = untagged = agreed = 0
    hashes = {}
    for row in rows:
        path = root / "raw" / f"{row['id']}.json"
        hashes[row["id"]] = hashlib.sha256(path.read_bytes()).hexdigest()
        saved = json.loads(path.read_text())
        check(saved["complete"], "incomplete session")
        session = Session.model_validate(saved["session"])
        case, role = cases[row["case"]]
        check(session.user_role_id == role and session.case_id == case.id, "wrong case/role")
        check(session.seed == row["seed"], "wrong controller seed")
        check(session.counterpart_profile.focus == row["target"], "wrong exposure")
        check(session.counterpart_profile.tier == 3, "wrong tier")
        score = scorers[case.id][0](saved["session"])
        check(math.isclose(score, row["R"], abs_tol=1e-12), "incorrect terminal score")
        agreed += session.status == "agreed"
        below += session.status == "agreed" and score < 0
        replay = Session(
            id=session.id,
            participant_id=session.participant_id,
            case_id=case.id,
            user_role_id=role,
            counterpart_role_id=session.counterpart_role_id,
            counterpart_profile=session.counterpart_profile,
            seed=session.seed,
        )
        bot = RuleBasedCounterpart(case, session.counterpart_role_id, session.counterpart_profile)
        local_violations = 0
        for turn in session.turns:
            if turn.speaker == "counterpart":
                package = turn.offer or (replay.latest_offer_from("user") if turn.accept else None)
                if package:
                    local_violations += points(
                        case, session.counterpart_role_id, package
                    ) < bot.minimum(replay)
            replay.add_turn(turn, case)
        check(replay.status == session.status, "terminal replay disagrees")
        check(
            local_violations == saved["schedule_violations"] == row["schedule_violations"],
            "schedule count disagrees",
        )
        violations += local_violations
        obs = observe(session, case)
        check(
            row["counts"] == {k: obs.counts[k].model_dump(exclude={"turns"}) for k in ERRORS},
            "detector counts disagree",
        )
        untagged += obs.untagged_user_turns
    usage = [json.loads(p.read_text()) for p in root.glob("usage_*.json")]
    result = {
        "verified_episodes": len(rows),
        "agreed": agreed,
        "below_walkaway": below,
        "schedule_violations": violations,
        "untagged_user_turns": untagged,
        "independent_feasible_maxima": {k: s[1] for k, s in scorers.items()},
        "ledger_cost_usd": sum(u["after"]["actual_usd"] - u["before"]["actual_usd"] for u in usage),
        "requests": sum(u["after"]["requests"] - u["before"]["requests"] for u in usage),
        "source_sha256": source_hash(),
        "session_hashes": hashes,
    }
    write_json(root / "verification.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "session_hashes"}, indent=2))


if __name__ == "__main__":
    main()
