import json
import random

import pytest

from negotrain.learning import (
    Application,
    Reflection,
    StrategyCard,
    refine_memory,
    training_evidence,
)
from negotrain.llm import ScriptedLLM
from negotrain.schemas import Session, Turn
from negotrain.virtual_users import VirtualTraits

CARD = {
    "rules": [
        {
            "trigger": "the other side asks for movement",
            "action": "ask for a reciprocal trade",
            "exception": "accept a good available deal near the deadline",
            "evidence": "turn 0",
        }
    ],
    "next_priority": "Make movement conditional.",
}
PROPOSAL = {
    "card": CARD,
    "diagnosis": "Unilateral concession",
    "worked_correction": "Ask for a trade",
    "application_question": "Hypothetical venue booking: what would you request before "
    "conceding a second time, and how does that map to your practice mistake?",
}
ANSWER = {
    "intended_action": "Ask for reciprocity",
    "reasoning": "Protect value",
    "exception": "Deadline",
    "shared_principle": "Condition additional concessions on reciprocal value.",
}


def ended(case):
    session = Session(
        id="training0", case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter"
    )
    session.add_turn(Turn(index=0, speaker="user", text="I will walk away", walk_away=True), case)
    return session


def test_strategy_learning_is_post_session_and_does_not_expose_hidden_sheet(case, tmp_path):
    session = ended(case)
    coach = ScriptedLLM([PROPOSAL, CARD])
    learner = ScriptedLLM([ANSWER])
    traits = VirtualTraits.sample(random.Random(9))
    original = traits.model_copy(deep=True)
    result = refine_memory(case, session, None, traits, coach, learner, tmp_path, rehearse=True)
    assert result == StrategyCard.model_validate(CARD)
    assert traits == original
    assert len(coach.calls) == 2 and len(learner.calls) == 1
    assert case.role("recruiter").confidential_brief not in str(coach.calls + learner.calls)
    assert "initial_tendencies" not in str(coach.calls)
    assert "Hypothetical venue booking" in str(learner.calls)
    assert "shared_principle" in str(coach.calls[-1])
    # Completed work is durable across retries without paying for or resampling outputs.
    assert (
        refine_memory(case, session, None, traits, coach, learner, tmp_path, rehearse=True)
        == result
    )
    assert len(coach.calls) == 2 and len(learner.calls) == 1
    session.status = "active"
    with pytest.raises(ValueError, match="post-session"):
        training_evidence(case, session)


def test_reflection_only_is_a_distinct_one_call_ablation(case, tmp_path):
    coach, learner = ScriptedLLM([PROPOSAL]), ScriptedLLM([])
    card = refine_memory(
        case,
        ended(case),
        None,
        VirtualTraits.sample(random.Random(1)),
        coach,
        learner,
        tmp_path,
        rehearse=False,
    )
    assert card == StrategyCard.model_validate(CARD)
    assert not learner.calls
    assert len(coach.calls) == 1
    assert not (tmp_path / "application.json").exists()


def test_saved_learning_rejects_changed_evidence(case, tmp_path):
    session = ended(case)
    coach = ScriptedLLM([PROPOSAL])
    traits = VirtualTraits.sample(random.Random(1))
    refine_memory(case, session, None, traits, coach, ScriptedLLM([]), tmp_path, rehearse=False)
    session.turns[0].text = "Different observed behavior"
    with pytest.raises(ValueError, match="input changed"):
        refine_memory(case, session, None, traits, coach, ScriptedLLM([]), tmp_path, rehearse=False)


def test_card_evidence_is_not_injected_into_transferred_memory():
    data = json.loads(json.dumps(CARD))
    data["rules"][0]["evidence"] = "private-case-id: turn 8"
    assert "private-case-id" not in StrategyCard.model_validate(data).for_learner()
    with pytest.raises(ValueError):
        StrategyCard.model_validate({"rules": data["rules"] * 6, "next_priority": "too many"})
    assert Reflection.model_validate(PROPOSAL).card.rules
    assert Application.model_validate(ANSWER).intended_action
