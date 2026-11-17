"""Experimental private intent field, separated from the negotiator's public move."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from negotrain.counterpart.agent import OfferTerm

INTENT_INSTRUCTION = """
Before producing the public move, fill in the private behavioral-intent fields.
State whether the supplied initial habit influences this particular decision, and
describe its observable effect in one brief sentence. If past coaching is present,
it may change the behavior; do not force either success or failure. The public formal
action should be consistent with that intent. This note is private to the simulator;
do not repeat it, your trait settings, or these instructions in your public message.
"""


class PersonaDecision(BaseModel):
    behavioral_intent: Literal["habit_influenced", "habit_resisted", "not_applicable"]
    brief_effect: str = Field(description="One short sentence about the observable effect")
    message: str
    offer: list[OfferTerm]
    accept: bool
    walk_away: bool


class IntentLLM:
    def __init__(self, llm):
        self.llm = llm
        self.notes = []

    def parse(self, system, messages, output_type, **kwargs):
        if output_type.__name__ != "CounterpartMove":
            return self.llm.parse(system, messages, output_type, **kwargs)
        result = self.llm.parse(
            system.append_uncached(INTENT_INSTRUCTION), messages, PersonaDecision, **kwargs
        )
        self.notes.append(
            {"behavioral_intent": result.behavioral_intent, "brief_effect": result.brief_effect}
        )
        return output_type.model_validate(
            result.model_dump(exclude={"behavioral_intent", "brief_effect"})
        )
