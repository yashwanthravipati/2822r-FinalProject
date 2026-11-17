"""Bounded, evidence-grounded strategy memory learned between rehearsals.

This is GEPA-inspired reflective mutation, not a full genetic/Pareto optimizer. The
optional learner application and correction require only two extra short model calls.
All content is post-session; no live action is supplied by the coach.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from negotrain.cases.offers import points
from negotrain.evaluation import write_json
from negotrain.llm import LLM, CachedText, cached_json
from negotrain.profiling.observations import observe
from negotrain.schemas import Case, Session
from negotrain.simulation import episode_score
from negotrain.virtual_users import LLMUser, VirtualTraits


class StrategyRule(BaseModel):
    trigger: str = Field(description="Observable situation in which to use the rule")
    action: str = Field(description="Specific decision procedure, not a vague aspiration")
    exception: str = Field(description="When the rule should be relaxed or not applied")
    evidence: str = Field(
        description="Training session/turn supporting the change; no invented events"
    )


class StrategyCard(BaseModel):
    rules: list[StrategyRule] = Field(min_length=1, max_length=5)
    next_priority: str = Field(description="One concrete habit to practise next")

    def for_learner(self) -> str:
        # Evidence remains auditable privately, but case identifiers/details are not
        # carried into the new case. Text is advice the learner can choose to apply.
        rules = "\n".join(
            f"{i + 1}. When {r.trigger}: {r.action} Exception: {r.exception}"
            for i, r in enumerate(self.rules)
        )
        return (
            "Your accumulated negotiation practice notes:\n"
            + rules
            + ("\nCurrent priority: " + self.next_priority)
        )


class Reflection(BaseModel):
    card: StrategyCard
    diagnosis: str = Field(description="One important observed failure or successful habit")
    worked_correction: str = Field(
        description="A concrete correction using only user-visible facts"
    )
    application_question: str = Field(
        description="A self-contained fictional negotiation in a different everyday domain, "
        "asking the learner to apply and map the same strategic principle"
    )


class Application(BaseModel):
    intended_action: str
    reasoning: str
    exception: str
    shared_principle: str = Field(
        default="",
        description="How the training mistake and fictional scenario share the same structure",
    )


GENERIC_CARD = """Negotiation practice notes:
1. Before opening, identify your walk-away alternative, hard constraints, high-value issues,
and low-cost concessions. Set an ambitious but defensible package rather than adopting the
other side's first number.
2. Ask which issues matter most to the other side. Distinguish stated positions from
underlying interests. Use their answers to offer conditional trades across issues, keeping
high-value terms while moving on lower-cost ones.
3. Before each concession, check what you received for the last one. Ask for reciprocity;
do not keep bidding against yourself. Smaller concessions can signal that you are near a
limit, but do not reject a useful trade merely to avoid conceding first.
4. Compare complete packages using your own point table and constraints. An apparently
attractive single term may hide losses elsewhere. Avoid an offer that is worse on every
relevant dimension than an available alternative.
5. Near the deadline, weigh an available acceptable deal against the risk of no agreement.
Confirm the whole package and implementation responsibilities; do not let a good feasible
deal expire simply because it falls short of your initial aspiration. Preserve rapport,
ask clarifying questions, and never assume access to hidden counterpart utilities."""

REFLECT_SYSTEM = """You are a negotiation coach updating a student's personal practice card
AFTER a completed rehearsal. Your goal is better performance on a different future case
after at most five rehearsals, not simply fewer detector flags. Use the observed transcript,
own-role utilities, terminal result, and previous card. Treat detector counts as fallible
signals. Do not infer a causal lesson from a single coincidence. A good deal can require
conceding; refusing all movement or letting a favorable deal expire can be costly.

Keep at most FIVE conditional rules, about 180-260 words in the card total. Preserve useful
prior rules and revise only what evidence warrants. Prioritize this learner's most costly,
actionable mistake; do not reset to a generic checklist every time. Each rule needs an
observable trigger, concrete action, and an exception. Reference actual training turns in
the evidence field. The card's trigger/action/exception/priority must transfer: no case or
role names, specific package IDs, numbers from the case, or claimed hidden utilities.
Abstract domain-specific nouns into their economic function: write 'high-value issue',
'low-cost concession', 'implementation constraint', or 'available alternative', not salary,
cash, bonus, a border policy, or a clinical procedure. A learner in a different domain must
be able to recognize the trigger without translating case jargon. Retain a compact core
check for hard constraints, walk-away value, and whole-package utility even when recent
training happened not to expose a violation. Build personalization around that check rather
than replacing general decision discipline with a narrow trick from the last transcript.
Do not claim an earlier offer is still available unless the counterpart has left it open.
Never rewrite the learner's persona or instruct them to stop role-playing their tendencies.

Give a brief worked correction using only facts the learner could know at the observed
turn and their own utility table. Do not reveal or invent hidden counterpart preferences.
Then write ONE short application question in a DIFFERENT fictional everyday negotiation
(e.g. booking a venue, buying equipment, or arranging a service). Label it hypothetical,
supply all relevant priorities/constraints in the question, and ask the learner to choose
an action AND map its underlying strategic principle back to the observed mistake. The
scenario must contrast a tempting mistake with a better conditional strategy; avoid a
trivial request to repeat your rule. Do not borrow a real future case or include political,
security, medical, or humanitarian settings. Invented analogy details are not facts about
the actual training case. The card is advice, not a script.
Do not instruct the learner to exploit simulator tiers, countdown mechanics, or detector
implementation. Explain uncertainty and genuine economic tradeoffs instead."""

REVISE_SYSTEM = """You are a negotiation coach completing a brief post-practice application
check. Read the proposed strategy card, worked correction, learner's answer, and original
training evidence. Check whether the learner mapped the same strategic structure across
the two situations, not just repeated your wording. Clarify misunderstood rules while
retaining supported useful habits. Do not use invented analogy events as observed evidence
about the learner; cite the real training turns or explicitly label the application answer.
Return the final card, at most five conditional rules and about 180-260 words. Include
trigger, action, exception, and source evidence. If the learner understood, preserve the
card rather than invent new lessons. No future-case information, role names, package IDs,
case-specific numbers, hidden utilities, or instructions that overwrite their persona may
enter the transferable card. This is a teaching correction, not a model-graded reward."""


def saved_parse(path: Path, llm: LLM, system: str, messages: list, schema, max_tokens=3072):
    """Resume completed reflection stages without paying twice; reject stale inputs."""
    digest = hashlib.sha256(
        json.dumps([str(system), messages], sort_keys=True).encode()
    ).hexdigest()
    if path.exists():
        record = json.loads(path.read_text())
        if record["input_sha256"] != digest:
            raise ValueError("saved learning input changed; use a new run directory")
        return schema.model_validate(record["output"])
    output = llm.parse(system, messages, schema, max_tokens=max_tokens)
    write_json(path, {"input_sha256": digest, "output": output.model_dump(mode="json")})
    return output


def training_evidence(case: Case, session: Session) -> dict:
    if session.status == "active":
        raise ValueError("strategy learning is post-session only")
    return {
        "session_id": session.id,
        "terminal_R": episode_score(case, session),
        "status": session.status,
        "counts": observe(session, case).model_dump(mode="json"),
        "transcript": [
            {
                "index": t.index,
                "speaker": t.speaker,
                "text": t.text,
                "offer": t.offer.model_dump() if t.offer else None,
                "own_points": points(case, session.user_role_id, t.offer)
                if t.offer and t.offer.is_complete(case) and not t.offer.custom_terms
                else None,
                "accept": t.accept,
                "walk_away": t.walk_away,
            }
            for t in session.turns
        ],
    }


def refine_memory(
    case: Case,
    session: Session,
    previous: StrategyCard | None,
    traits: VirtualTraits,
    coach: LLM,
    learner: LLM,
    root: Path,
    *,
    rehearse: bool,
) -> StrategyCard:
    visible = {
        "public_brief": case.public_brief,
        "issues": [i.model_dump() for i in case.issues],
        "own_sheet": case.role(session.user_role_id).model_dump(),
    }
    system = CachedText(REFLECT_SYSTEM + "\n" + json.dumps(visible))
    evidence = training_evidence(case, session)
    context = cached_json(
        {"previous_card": previous.model_dump() if previous else None},
        {"observations": evidence},
        cache_indices=(),
    )
    proposal = saved_parse(
        root / "proposal.json", coach, system, [{"role": "user", "content": context}], Reflection
    )
    if not rehearse:
        return proposal.card
    actor = LLMUser(case, session.user_role_id, traits, learner, [proposal.card.for_learner()])
    application = saved_parse(
        root / "application.json",
        learner,
        actor.system,
        [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "instruction": (
                            "The practice negotiation is over. Apply the coaching lesson "
                            "to the separate hypothetical scenario in the question. State "
                            "an action, why it helps, when it fails, and the shared principle "
                            "linking this scenario to your practice mistake. Hypothetical "
                            "details do not change the actual case facts."
                        ),
                        "worked_correction": proposal.worked_correction,
                        "question": proposal.application_question,
                    }
                ),
            }
        ],
        Application,
        max_tokens=1024,
    )
    return saved_parse(
        root / "revision.json",
        coach,
        CachedText(REVISE_SYSTEM + "\n" + json.dumps(visible)),
        [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "proposal": proposal.model_dump(),
                        "application": application.model_dump(),
                        "observations": evidence,
                    }
                ),
            }
        ],
        StrategyCard,
    )
