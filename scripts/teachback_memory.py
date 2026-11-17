"""Post-practice arithmetic teach-back, retaining all five original coaching reports."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from negotrain.consolidation import evidence_and_examples
from negotrain.learning import saved_parse
from negotrain.llm import CachedText
from negotrain.virtual_users import LLMUser


class Answer(BaseModel):
    own_change: float = Field(allow_inf_nan=False)
    surplus_over_walkaway: float = Field(allow_inf_nan=False)
    explanation: str
    conditional_trade: str
    when_to_close: str


class Teachback(BaseModel):
    answers: list[Answer] = Field(min_length=1, max_length=2)


class Reminder(BaseModel):
    trigger: str = Field(max_length=250)
    action: str = Field(max_length=600)
    exception: str = Field(max_length=350)


SYSTEM = """After five completed practices, correct the learner's teach-back using
the supplied exact own-utility arithmetic. Numbers are computed from their own sheet.
Write ONE brief portable conditional reminder addressing the demonstrated reasoning
gap. Preserve useful flexibility: conceding can secure a better terminal deal, an old
proposal is not a standing alternative, and refusal can lose a worthwhile agreement.
Focus on pricing the whole package and exchanging a costly concession for an explicit
return, without making reciprocity an absolute rule. If their answer is sound, reinforce
its most useful decision check rather than inventing a failure. Reports remain available.
No past-case numbers, case/role/issue names, simulator mechanics, hidden utilities,
persona overrides, perfect-optimization commands, or invented successful alternatives.
The reminder should be about 100 words; it is advice, not a guarantee or live move."""


def corrections(examples, answers):
    if len(examples) != len(answers):
        raise ValueError("one answer per historical comparison required")
    return [
        {
            "comparison": example,
            "answer": answer.model_dump(),
            "correct_own_change": example["chosen_points"] - example["previous_own_offer_points"],
            "correct_surplus_over_walkaway": example["chosen_points"] - example["walkaway"],
        }
        for example, answer in zip(examples, answers, strict=True)
    ]


def build_memory(case, sessions, reports, traits, coach, learner, root: Path):
    if len(sessions) != 5 or len(reports) != 5:
        raise ValueError("five complete sessions and reports required")
    evidence, examples = evidence_and_examples(case, sessions)
    selected = {e["session_id"] for e in examples}
    actor = LLMUser(case, sessions[0].user_role_id, traits, learner, reports)
    answers = saved_parse(
        root / "teachback.json",
        learner,
        actor.system,
        [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "instruction": "Practice is finished. Explain each of these own historical "
                        "decisions in order. Compute the point change and surplus over walk-away. "
                        "Explain what return, if any, justified the concession, propose a "
                        "conditional "
                        "trade process, and say when closing is better than demanding more. Do not "
                        "assume the earlier proposal was still available or that an alternative "
                        "would have been accepted. Use only the supplied evidence.",
                        "comparisons": examples,
                        "histories": [e for e in evidence if e["session_id"] in selected],
                    }
                ),
            }
        ],
        Teachback,
        max_tokens=2048,
    )
    corrected = corrections(examples, answers.answers)
    reminder = saved_parse(
        root / "reminder.json",
        coach,
        CachedText(SYSTEM),
        [{"role": "user", "content": json.dumps({"corrected_teachback": corrected})}],
        Reminder,
        max_tokens=1024,
    )
    text = (
        "Post-practice personal reminder:\nWhen "
        + reminder.trigger
        + ": "
        + reminder.action
        + " Exception: "
        + reminder.exception
        + "\n\nAll five original practice reports follow. Historical figures describe "
        "those cases only; use the current case's own sheet for new decisions.\n\n"
        + "\n\n".join(reports)
    )
    return [text], corrected, reminder.model_dump()
