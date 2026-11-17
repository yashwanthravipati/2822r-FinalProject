"""Screen named LLM weaknesses using fresh matched high/low, uncoached episodes."""

from __future__ import annotations

import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from consolidation_ablate import source_hash
from consolidation_evaluate import frozen_json
from negotrain.budget import SpendLedger
from negotrain.cases import load_case
from negotrain.cases.offers import points
from negotrain.counterpart import TIERS, RuleBasedCounterpart
from negotrain.evaluation import write_json
from negotrain.llm import ClaudeLLM
from negotrain.profiling.observations import ERRORS, observe
from negotrain.profiling.tagging import tag_session
from negotrain.schemas import Session
from negotrain.simulation import episode_score
from negotrain.virtual_users import LLMUser, VirtualTraits

CASES = (("cloudline_hiring", "candidate"), ("harbor_analytics", "buyer"))
SEEDS = (2822111710, 2822111711)


def persona(target, level):
    return VirtualTraits(
        errors={k: level if k == target else 0.3 for k in ERRORS},
        awareness=0.5,
        rapport=0.5,
        response={k: 0 for k in ERRORS},
    )


def episode(root, case, role, target, level, seed, llm):
    key = f"{case.id}_{target.replace(':', '')}_{level}_{seed}"
    path = root / "raw" / f"{key}.json"
    traits = persona(target, level)
    original = traits.model_dump()
    # Controller exposure is deliberately separate from the learner's practice callout.
    actor = LLMUser(case, role, traits, llm, feedback=[], focus=None)
    profile = TIERS[3].model_copy(update={"focus": target})
    session = Session(
        id=key,
        participant_id=key,
        case_id=case.id,
        user_role_id=role,
        counterpart_role_id=case.other_role(role).id,
        counterpart_profile=profile,
        seed=seed,
    )
    violations, complete = 0, False
    if path.exists():
        saved = json.loads(path.read_text())
        session = Session.model_validate(saved["session"])
        violations, complete = saved["schedule_violations"], saved["complete"]
    bot = RuleBasedCounterpart(case, session.counterpart_role_id, profile)
    user_next = (
        session.turns[-1].speaker == "counterpart"
        if session.turns
        else target != "error:3" and random.Random(seed).random() < 0.5
    )

    def save(done):
        write_json(
            path,
            {
                "complete": done,
                "session": session.model_dump(mode="json"),
                "schedule_violations": violations,
            },
        )

    while session.status == "active":
        if user_next:
            turn = actor.respond(session)
        else:
            minimum = bot.minimum(session)
            turn = bot.respond(session)
            package = turn.offer or (session.latest_offer_from("user") if turn.accept else None)
            if package:
                violations += points(case, session.counterpart_role_id, package) < minimum
        session.add_turn(turn, case)
        save(False)
        user_next = not user_next
    if not complete:
        tag_session(session, case, llm)
        save(True)
    assert traits.model_dump() == original
    obs = observe(session, case)
    return {
        "id": key,
        "case": case.id,
        "role": role,
        "target": target,
        "level": level,
        "seed": seed,
        "R": episode_score(case, session),
        "status": session.status,
        "user_turns": session.user_turns,
        "schedule_violations": violations,
        "untagged_user_turns": obs.untagged_user_turns,
        "counts": {k: obs.counts[k].model_dump(exclude={"turns"}) for k in ERRORS},
    }


def summarize(rows):
    expected = {
        (c, k, level, seed)
        for c, _ in CASES
        for k in ERRORS
        for level in (0.1, 0.9)
        for seed in SEEDS
    }
    actual = {(r["case"], r["target"], r["level"], r["seed"]) for r in rows}
    if actual != expected or len(rows) != len(expected):
        raise ValueError("A complete, unique matched cohort is required")
    result = []
    for target in ERRORS:
        groups = {}
        for level in (0.1, 0.9):
            group = [r for r in rows if r["target"] == target and r["level"] == level]
            counts = [r["counts"][target] for r in group]
            opps = sum(c["opportunities"] for c in counts)
            occurrences = sum(c["occurrences"] for c in counts)
            groups[str(level)] = {
                "episodes": len(group),
                "opportunities": opps,
                "occurrences": occurrences,
                "episodes_with_opportunity": sum(c["opportunities"] > 0 for c in counts),
                "episode_error_fraction": sum(c["occurrences"] > 0 for c in counts) / len(group),
                "conditional_rate": occurrences / opps if opps else None,
            }
        delta = groups["0.9"]["episode_error_fraction"] - groups["0.1"]["episode_error_fraction"]
        result.append(
            {
                "target": target,
                "name": ERRORS[target],
                "groups": groups,
                "high_minus_low_episode_fraction": delta,
            }
        )
    return {
        "complete_episodes": len(rows),
        "weaknesses": result,
        "scope": "Descriptive screening, four matched pairs per weakness; no efficacy claim",
        "all_six_positive_direction": all(r["high_minus_low_episode_fraction"] > 0 for r in result),
    }


def main():
    root = Path("results/ckpt3/persona-calibration-v1")
    cases = [(load_case(f"data/cases/{name}.json"), role) for name, role in CASES]
    protocol = {
        "source_sha256": source_hash(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": {c.id: hashlib.sha256(c.model_dump_json().encode()).hexdigest() for c, _ in cases},
        "seeds": list(SEEDS),
        "target_levels": [0.1, 0.9],
        "other_error_levels": 0.3,
        "awareness": 0.5,
        "rapport": 0.5,
        "expected_episodes": 48,
        "learner": "claude-sonnet-5-5",
        "effort": "low",
        "feedback": [],
        "learner_focus": None,
        "counterpart": "rule-based, tier 3, target focus",
        "primary": "fraction of episodes exhibiting the target error, high minus low",
        "secondary": "Opportunity coverage and conditional rate; zero opportunities=null",
        "interpretation": "Diagnostic only; all six positive directions needed to advance",
        "limitations": (
            "Four pairs/error; endogenous opportunities; unseeded LLM; rule-based opponent"
        ),
        "sim4_used": False,
        "cedar_used": False,
    }
    frozen_json(root / "protocol.json", protocol)
    ledger = SpendLedger(".api-budget.sqlite3.ckpt3-dev")
    llm = ClaudeLLM(model=protocol["learner"], effort="low", ledger=ledger)
    attempt = len(list(root.glob("usage_*.json")))
    before = ledger.snapshot()
    jobs = [
        (c, role, target, level, seed)
        for c, role in cases
        for target in ERRORS
        for seed in SEEDS
        for level in (0.1, 0.9)
    ]
    random.Random(SEEDS[0]).shuffle(jobs)
    rows, errors = [], []
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(episode, root, *job, llm): job for job in jobs}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    row = future.result()
                    rows.append(row)
                    write_json(root / "rows.json", sorted(rows, key=lambda r: r["id"]))
                    print(
                        json.dumps({"complete": len(rows), "id": row["id"], "R": row["R"]}),
                        flush=True,
                    )
                except Exception as exc:
                    errors.append(
                        {
                            "case": job[0].id,
                            "target": job[2],
                            "level": job[3],
                            "seed": job[4],
                            "type": type(exc).__name__,
                        }
                    )
                    write_json(root / "failures.json", errors)
                    print(json.dumps(errors[-1]), flush=True)
        if errors:
            raise RuntimeError(f"{len(errors)} failed episodes; no complete-cohort summary")
        write_json(root / "summary.json", summarize(rows))
    finally:
        write_json(
            root / f"usage_{attempt}.json",
            {"before": before, "after": ledger.snapshot(), "learner": llm.usage.snapshot()},
        )


if __name__ == "__main__":
    main()
