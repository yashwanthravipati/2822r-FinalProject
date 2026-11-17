"""Short own-history plans and conservative per-user selection; no live assistance."""

from __future__ import annotations

import json
import math
from pathlib import Path

from pydantic import BaseModel, Field

from negotrain.consolidation import evidence_and_examples
from negotrain.learning import saved_parse
from negotrain.llm import CachedText

GENERIC = """Before opening, identify your alternative, hard constraints and most valuable
issues. Start from your own priorities, not their opening number. Before changing a
proposal, compare the full package with your previous proposal and the current offer.
Ask which issues matter to them and trade a cheaper concession for something you value.
After an unreturned concession, pause and ask for a concrete reciprocal move instead
of automatically giving more. A past proposal is not a guaranteed available alternative.
Before accepting, check the whole package against walking away and consider one feasible
conditional trade. Close an acceptable agreement when further bargaining is unlikely
to help; reciprocity is a guide, not an absolute requirement. Use the current case's
own sheet and listed terms. Historical numbers are not current targets, and you do not
know the other side's private utilities."""

SYSTEM = """Write a SHORT personal implementation plan after five negotiation practices.
You receive only the person's own sheet and visible past dialogue with own-value arithmetic.
Find one or two recurring, evidenced decision patterns that the person can recognize
and change. A concession is not automatically a mistake: it may secure an agreement.
Include successful behavior where appropriate; do not invent a weakness to fill space.
For each rule give a visible trigger, a concrete action, and an exception protecting
useful compromise or closure. Cite actual USER decision turns supporting your advice.
The learner retains all five original reports, so do not summarize them or repeat slogans.
The rendered rules together should be 100-160 words. Make them portable: no past case,
role, issue or option names, numeric point targets, claims that an alternative would
be accepted, hidden opponent utilities, detector thresholds or simulator schedules.
Do not overwrite persona traits, command perfect optimization or prescribe live moves.
This is post-practice advice that the learner may or may not apply, not a forced policy."""


class Citation(BaseModel):
    session_id: str
    turn: int = Field(ge=0)


class Rule(BaseModel):
    trigger: str = Field(max_length=400)
    action: str = Field(max_length=900)
    exception: str = Field(max_length=500)
    evidence: list[Citation] = Field(min_length=1, max_length=3)


class Plan(BaseModel):
    rules: list[Rule] = Field(min_length=1, max_length=2)

    def render(self):
        return "\n".join(
            f"When {r.trigger}: {r.action} Exception: {r.exception}" for r in self.rules
        )


def build_plan(case, sessions, llm, root: Path):
    if len(sessions) != 5:
        raise ValueError("five complete practices required")
    evidence, _ = evidence_and_examples(case, sessions)
    role = sessions[0].user_role_id
    payload = {
        "public_brief": case.public_brief,
        "issues": [i.model_dump() for i in case.issues],
        "own_sheet": case.role(role).model_dump(),
        "practice": evidence,
    }
    plan = saved_parse(
        root / "plan.json",
        llm,
        CachedText(SYSTEM),
        [{"role": "user", "content": json.dumps(payload)}],
        Plan,
        max_tokens=2048,
    )
    allowed = {(s.id, t.index) for s in sessions for t in s.turns if t.speaker == "user"}
    if any((c.session_id, c.turn) not in allowed for r in plan.rules for c in r.evidence):
        raise ValueError("plan cites an absent or non-user decision")
    return plan


def memory(reports, note=None):
    if len(reports) != 5:
        raise ValueError("all five original reports required")
    if note is None:
        return list(reports)
    # LLMUser retains the last five entries. Bundle the exact five reports into ONE
    # entry so adding a plan cannot silently displace the earliest report.
    return [json.dumps({"practice_advice": note, "original_reports": reports})]


def choose(scores, margin=0.03):
    """Two development cases; ties prefer the simplest eligible memory."""
    if set(scores) != {"reports", "generic", "personalized"}:
        raise ValueError("complete three-arm selection required")
    if any(len(v) != 2 for v in scores.values()):
        raise ValueError("two case scores per arm required")
    if not all(math.isfinite(x) for values in scores.values() for x in values):
        raise ValueError("finite development scores required")
    means = {k: sum(v) / 2 for k, v in scores.items()}
    winner = max(("reports", "generic", "personalized"), key=lambda k: means[k])
    return winner if means[winner] - means["reports"] >= margin else "reports"
