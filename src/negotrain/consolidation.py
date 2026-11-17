"""Turn five completed practice histories into an executable, evidence-backed workbook."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from negotrain.cases.offers import points
from negotrain.learning import StrategyRule, saved_parse
from negotrain.llm import LLM, CachedText, cached_json
from negotrain.schemas import Case, Session

PROCEDURE = """Negotiation decision procedure:
Use the CURRENT case's own point table and hard constraints; never reuse numbers from a
past case. A persuasive description does not change the value of the listed formal terms.
1. Before opening, identify your walk-away and highest-value legal package. Aim high on
your important issues. Name an ambitious complete package and ask about their priorities;
do not concede several useful terms simply because their opening sounds reasonable.
2. Before every formal move, privately add up your points issue by issue. Compare your
last proposal, their current complete offer, and the package you are about to send. Check
which exact terms changed, their point cost to you, and what you received in exchange.
An earlier proposal is a comparison point, not a guarantee that it remains available.
3. Price each new request as a new trade. If a change costs you value, ask for a specific
return on an issue you care about. Try cheaper concessions first. Do not accept a loss
merely because it is described as consistent, practical, fair, or nearly agreed. Ask why
an asserted limit is binding, while treating genuinely established constraints seriously.
4. On rejection, seek a differently composed package rather than repeatedly shrinking
your own demand. Preserve gains already secured, test a conditional exchange, and compare
whole-package value. Never assume you know the other side's private utility table.
5. Before accepting, calculate the current offer's surplus over your actual alternative.
If there is a credible chance of a useful trade, make one concrete conditional counter.
If no better reachable package is likely and the offer beats walking away, close it.
Do not let an acceptable deal expire just to follow a rule, and preserve rapport.
Only the formal package counts; verify that your message and formal action agree."""

CONSOLIDATE_SYSTEM = """You are consolidating a learner's FIVE completed negotiation
rehearsals and debriefs into a portable practice workbook. This is post-session coaching,
not live assistance. You see the learner's own case information and their observed
history, not hidden opponent utilities or planted persona probabilities.

The fixed decision procedure will accompany your output. Personalize its execution using
the observed failures and successful moves; do not repeat generic slogans. In particular,
distinguish the numerical value of a formal offer from a persuasive verbal explanation.
Prioritize when the learner should stop, calculate a change, and ask for a reciprocal
trade. Preserve flexibility and the value of closing an acceptable deal. Do not invent
hard limits, infer causality from a single event, or recommend always refusing concessions.

Return an opening plan, offer-audit routine, closing plan, and at most THREE conditional
lessons. Keep these transferable: no case/role names, specific issue/option IDs, or fixed
point targets from this case. Explain how to recompute them from a new own-role sheet.
Do not overwrite the persona, instruct perfect optimization, or exploit simulator tiers,
deadline counters, hidden preferences, or detector internals.

The supplied practice comparisons have arithmetic computed by code. Write one correction
for each comparison in the same order, using only its available own-visible evidence.
Show a better decision process or conditional request, not an invented successful outcome.
Do not claim the other side would accept the correction. These are labeled historical
examples; their numerical facts will be rendered by code. Your correction need not repeat
the figures. In evidence fields cite actual session IDs/turns. Aim for 300-450 words total
in your transferable plans, lessons and corrections, excluding the fixed procedure."""


class Workbook(BaseModel):
    diagnosis: str
    opening_plan: str
    offer_audit: str
    closing_plan: str
    lessons: list[StrategyRule] = Field(min_length=1, max_length=3)
    corrections: list[str] = Field(min_length=1, max_length=2)

    def for_learner(self, examples: list[dict], *, include_examples=True):
        text = (
            PROCEDURE
            + "\n\nYour personalized practice plan:\nOpening: "
            + self.opening_plan
            + "\nOffer check: "
            + self.offer_audit
            + "\nClosing: "
            + self.closing_plan
        )
        for rule in self.lessons:
            text += f"\nWhen {rule.trigger}: {rule.action} Exception: {rule.exception}"
        if include_examples:
            for example, correction in zip(examples, self.corrections, strict=True):
                previous = example["previous_own_offer_points"]
                current = example["chosen_points"]
                delta = current - previous
                reference = (
                    "My previous proposal"
                    if example["reference"] == "prior_proposal"
                    else "My walk-away alternative"
                )
                text += (
                    "\n\nHistorical practice example (past-case units, NOT current-case targets): "
                    f"{reference} was worth {previous:g} to me. "
                    f"I then {example['action']} a package worth {current:g}: "
                    f"a change of {delta:+g}. My walk-away was {example['walkaway']:g}. "
                    + (
                        "The earlier proposal was not necessarily still available. "
                        if example["reference"] == "prior_proposal"
                        else ""
                    )
                    + f"Correction to my decision process: {correction}"
                )
        return text


def evidence_and_examples(case: Case, sessions: list[Session]):
    if not sessions or any(s.status == "active" for s in sessions):
        raise ValueError("consolidation requires completed practice sessions")
    role = sessions[0].user_role_id
    if any(s.case_id != case.id or s.user_role_id != role for s in sessions):
        raise ValueError("practice histories must share their case and own role")
    evidence, comparisons, openings = [], [], []
    for session in sessions:
        previous_own = None
        latest = {"user": None, "counterpart": None}
        transcript = []
        for turn in session.turns:
            if turn.offer:
                latest[turn.speaker] = turn.offer
            other = "counterpart" if turn.speaker == "user" else "user"
            chosen = turn.offer or (latest[other] if turn.accept else None)
            value = (
                points(case, role, chosen)
                if chosen and chosen.is_complete(case) and not chosen.custom_terms
                else None
            )
            transcript.append(
                {
                    "turn": turn.index,
                    "speaker": turn.speaker,
                    "message": turn.text,
                    "formal_offer": turn.offer.model_dump() if turn.offer else None,
                    "own_points": value,
                    "accept": turn.accept,
                    "walk_away": turn.walk_away,
                }
            )
            if turn.speaker == "user" and value is not None:
                if previous_own is not None:
                    comparisons.append(
                        {
                            "session_id": session.id,
                            "turn": turn.index,
                            "previous_own_offer_points": previous_own,
                            "chosen_points": value,
                            "walkaway": case.role(role).reservation_value,
                            "action": "accepted" if turn.accept else "proposed",
                            "reference": "prior_proposal",
                        }
                    )
                else:
                    openings.append(
                        {
                            "session_id": session.id,
                            "turn": turn.index,
                            "previous_own_offer_points": case.role(role).reservation_value,
                            "chosen_points": value,
                            "walkaway": case.role(role).reservation_value,
                            "action": "accepted" if turn.accept else "proposed",
                            "reference": "walkaway",
                        }
                    )
                previous_own = value
        evidence.append({"session_id": session.id, "status": session.status, "turns": transcript})
    # Choose informative loss comparisons deterministically, never from assessment scores.
    comparisons = comparisons or openings
    comparisons.sort(key=lambda x: x["chosen_points"] - x["previous_own_offer_points"])
    examples = []
    for comparison in comparisons:
        if comparison["session_id"] not in {x["session_id"] for x in examples}:
            examples.append(comparison)
        if len(examples) == 2:
            break
    if not examples:
        raise ValueError("practice contains no comparable own decisions")
    return evidence, examples


def consolidate(
    case: Case,
    sessions: list[Session],
    reports: list[str],
    coach: LLM,
    root: Path,
    *,
    instruction: str = CONSOLIDATE_SYSTEM,
):
    evidence, examples = evidence_and_examples(case, sessions)
    role = sessions[0].user_role_id
    visible = {
        "public_brief": case.public_brief,
        "issues": [issue.model_dump() for issue in case.issues],
        "own_sheet": case.role(role).model_dump(),
    }
    workbook = saved_parse(
        root / "workbook.json",
        coach,
        CachedText(instruction, "\n" + json.dumps(visible)),
        [
            {
                "role": "user",
                "content": cached_json(
                    {"practice": evidence, "visible_debriefs": reports, "comparisons": examples},
                    cache_indices=(),
                ),
            }
        ],
        Workbook,
        max_tokens=4096,
    )
    if len(workbook.corrections) != len(examples):
        raise ValueError("workbook corrections must match supplied practice comparisons")
    return workbook, examples
