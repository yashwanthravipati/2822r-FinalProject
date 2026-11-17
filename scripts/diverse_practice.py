"""Same five-session budget, with a shared two-session prefix and varied later cases."""

from __future__ import annotations

import json
import math
from pathlib import Path

from negotrain.cases import load_case
from negotrain.feedback.coaching import Debrief
from negotrain.simulation import episode_score
from verify_ckpt3 import check, digest, economics

SCHEDULE = ("hiring", "sim4_revisited", "hiring")


def rehearse(experiments, uid, traits, seed, initial_reports):
    if len(initial_reports) != 2:
        raise ValueError("exactly two shared practice reports required")
    reports, scores = list(initial_reports), []
    for t, key in enumerate(SCHEDULE, start=2):
        exp = experiments[key]
        session = exp.episode(
            f"learner{uid}_diverse_train{t}",
            traits,
            4,
            None,
            seed + 700000 + 1009 * uid + 100 + t,
            reports,
        )
        reports.append(exp.feedback(session).report.model_dump_json())
        scores.append(episode_score(exp.case, session))
    return reports, scores


def audit_practice(root, protocol):
    check(protocol["diverse_schedule"] == list(SCHEDULE), "practice schedule changed")
    sources = {c["key"]: c for c in protocol["practice_cases"]}
    check(set(sources) == set(SCHEDULE), "wrong practice cases")
    rows = json.loads((root / "prepare_rows.json").read_text())
    check(len(rows) == len(protocol["users"]), "missing preparation rows")
    by_user = {r["user"]: r for r in rows}
    check(set(by_user) == set(protocol["users"]), "wrong preparation cohort")
    scores, statuses, expected = [], {}, set()
    for entry in sources.values():
        check(digest(Path(entry["path"])) == entry["sha256"], "practice case changed")
    for uid in protocol["users"]:
        memory = json.loads((root / "raw" / f"learner{uid}.memories.json").read_text())["memories"]
        control, varied = memory["reports"], memory["diverse_reports"]
        check(len(control) == len(varied) == 5, "unequal practice counts")
        check(control[:2] == varied[:2], "shared prefix changed")
        check(len(by_user[uid]["new_practice_R"]) == 3, "incomplete new practice curve")
        for t, key in enumerate(SCHEDULE, start=2):
            entry = sources[key]
            case = load_case(entry["path"])
            score, _ = economics(case, entry["role"])
            stem = f"learner{uid}_diverse_train{t}"
            path = root / "practice" / key / "raw" / f"{stem}.json"
            expected.add(path)
            data = json.loads(path.read_text())
            s = data["session"]
            check(data["complete"] and s["id"] == stem, "incomplete practice")
            check(
                s["case_id"] == case.id and s["user_role_id"] == entry["role"],
                "wrong practice role/case",
            )
            check(
                s["counterpart_role_id"] == case.other_role(entry["role"]).id,
                "wrong practice counterpart",
            )
            check(
                s["counterpart_profile"]["tier"] == 4 and s["counterpart_profile"]["focus"] is None,
                "wrong practice difficulty",
            )
            check(
                s["seed"] == protocol["seed"] + 700000 + 1009 * uid + 100 + t, "wrong practice seed"
            )
            check(data["schedule_violations"] == 0, "practice schedule violation")
            value = score(s)
            check(
                math.isclose(value, by_user[uid]["new_practice_R"][t - 2], abs_tol=1e-12),
                "wrong practice score",
            )
            scores.append(value)
            statuses[s["status"]] = statuses.get(s["status"], 0) + 1
            feedback = Debrief.model_validate_json(path.with_suffix(".feedback.json").read_text())
            check(feedback.counterfactuals.session_id == stem, "wrong practice feedback")
            check(feedback.report.model_dump_json() == varied[t], "practice report changed")
    actual = {
        p
        for p in (root / "practice").glob("*/raw/*.json")
        if "session" in json.loads(p.read_text())
    }
    check(actual == expected, "unplanned or missing practice episodes")
    return {
        "new_episodes": len(scores),
        "status_counts": statuses,
        "below_walkaway": sum(v < 0 for v in scores),
    }
