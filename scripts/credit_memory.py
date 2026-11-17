"""Post-session memory grounded in modeled terminal credit, with explicit uncertainty."""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

from negotrain.consolidation import PROCEDURE, Workbook, evidence_and_examples
from negotrain.learning import saved_parse
from negotrain.llm import CachedText, cached_json

SYSTEM = """Consolidate five completed negotiation rehearsals into a portable personal
practice plan. You receive own-role facts, visible histories, debriefs, and post-session
counterfactual estimates. The estimates use a simulated continuation model; they are NOT
observed outcomes of taking an alternative and may be biased. Their intervals use very
few rollouts. Hindsight information does not imply access to a future opponent's sheet.

Teach decisions that improve the eventual agreement, not merely preserve the value of
an earlier demand. A concession can be necessary and productive. Distinguish a modeled
improvement from a guaranteed reachable agreement. Explain how to identify an opportunity,
compare whole packages, test a conditional trade, and close a worthwhile deal. Do not
teach rigid refusal or score chasing. Respect current-case alternatives and constraints.

Return an opening plan, offer-audit routine, closing plan, and at most three conditional
rules. Use evidence across the five sessions, including successes. No case/role names,
issue/option IDs or fixed point targets in the portable plans. The fixed decision procedure
will be included, so personalize rather than repeat it. Do not overwrite persona traits,
claim perfect optimization, or exploit simulator schedules, hidden utilities or detectors.

For each supplied credit example write exactly one correction in the same order. Explain
the observed decision and what the modeled alternative suggests about the decision process.
If its mean is nonpositive, do not claim the alternative is better. If its interval includes
zero, call the lesson tentative. The numbers will be rendered by code. Distinguish past-case
evidence from current-case targets. Use the actual session/turn in evidence fields. Keep
the transferable plans, rules and corrections around 350–450 words total."""


def select_credit(feedbacks):
    candidates = []
    for feedback in feedbacks:
        data = feedback["counterfactuals"]
        for estimate in data["estimates"]:
            actual = estimate["scored_actual"]["outcomes"]
            alternative = estimate["scored_selected"]["outcomes"]
            if not actual or len(actual) != len(alternative):
                raise ValueError("paired complete rollout outcomes required")
            if not all(math.isfinite(x) for x in actual + alternative):
                raise ValueError("nonfinite rollout outcome")
            delta = statistics.mean(b - a for a, b in zip(actual, alternative, strict=True))
            lo, hi = estimate["delta_interval"]
            if not math.isfinite(lo) or not math.isfinite(hi) or lo > hi:
                raise ValueError("invalid credit interval")
            actions = {}
            for name in ("scored_actual", "scored_selected"):
                action = estimate[name]["action"]
                actions[name] = {
                    k: action.get(k) for k in ("offer", "accept", "walk_away", "text", "hindsight")
                }
            candidates.append(
                {
                    "session_id": data["session_id"],
                    "turn": estimate["turn_index"],
                    "actual_mean": statistics.mean(actual),
                    "alternative_mean": statistics.mean(alternative),
                    "mean_gain": delta,
                    "interval": [lo, hi],
                    "rollouts": len(actual),
                    **actions,
                }
            )
    positive = [e for e in candidates if e["mean_gain"] > 0]
    pool = positive or candidates
    pool.sort(key=lambda e: (-(e["interval"][0] > 0), -e["mean_gain"], e["session_id"], e["turn"]))
    chosen = []
    for candidate in pool:
        if candidate["session_id"] not in {e["session_id"] for e in chosen}:
            chosen.append(candidate)
        if len(chosen) == (2 if positive else 1):
            break
    return chosen


def build_memory(case, sessions, reports, feedbacks, coach, root: Path):
    evidence, _ = evidence_and_examples(case, sessions)
    if [f["counterfactuals"]["session_id"] for f in feedbacks] != [s.id for s in sessions]:
        raise ValueError("feedback/history alignment changed")
    examples = select_credit(feedbacks)
    if not examples:
        return (
            [
                PROCEDURE
                + "\nNo counterfactual evidence was available to justify an additional correction."
            ],
            [],
            None,
        )
    by_id = {s.id: s for s in sessions}
    for example in examples:
        s = by_id[example["session_id"]]
        if s.turns[example["turn"]].speaker != "user":
            raise ValueError("credit must refer to an own decision")
    role = sessions[0].user_role_id
    visible = {
        "public_brief": case.public_brief,
        "issues": [i.model_dump() for i in case.issues],
        "own_sheet": case.role(role).model_dump(),
    }
    plan = saved_parse(
        root / "credit_plan.json",
        coach,
        CachedText(SYSTEM, "\n" + json.dumps(visible)),
        [
            {
                "role": "user",
                "content": cached_json(
                    {
                        "practice": evidence,
                        "visible_debriefs": reports,
                        "credit_examples": examples,
                    },
                    cache_indices=(),
                ),
            }
        ],
        Workbook,
        max_tokens=4096,
    )
    if len(plan.corrections) != len(examples):
        raise ValueError("one correction per supplied credit example required")
    memory = plan.for_learner([], include_examples=False)
    for e, correction in zip(examples, plan.corrections, strict=True):
        lo, hi = e["interval"]
        memory += (
            "\n\nHistorical modeled feedback (past-case normalized surplus, NOT a current target): "
            f"simulated continuation of my actual decision averaged {e['actual_mean']:.3f}; "
            f"the tested alternative averaged {e['alternative_mean']:.3f}. "
            f"Estimated difference {e['mean_gain']:+.3f}, interval [{lo:+.3f}, {hi:+.3f}], "
            f"from {e['rollouts']} paired continuations. This is uncertain model feedback, "
            f"not an observed alternative outcome or a guarantee. Lesson: {correction}"
        )
    return [memory], examples, plan.model_dump()
