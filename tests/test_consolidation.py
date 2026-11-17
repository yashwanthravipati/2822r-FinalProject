import importlib.util
import random
from pathlib import Path

import pytest

from negotrain.cases.offers import best_offer_for, points
from negotrain.consolidation import PROCEDURE, Workbook, consolidate, evidence_and_examples
from negotrain.llm import ScriptedLLM
from negotrain.schemas import Session, Turn
from negotrain.virtual_users import VirtualTraits


def practice(case, name, *, counterpart_accepts=False):
    session = Session(
        id=name, case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter"
    )
    first = best_offer_for(case, "candidate")
    session.add_turn(Turn(index=0, speaker="user", text="My opening", offer=first), case)
    if counterpart_accepts:
        session.add_turn(Turn(index=1, speaker="counterpart", text="Agreed", accept=True), case)
    else:
        offer = first.model_copy(deep=True)
        offer.terms["salary"] = "s130"
        session.add_turn(
            Turn(index=1, speaker="counterpart", text="A reasonable change", offer=offer), case
        )
        session.add_turn(Turn(index=2, speaker="user", text="Agreed", accept=True), case)
    return session


PLAN = {
    "diagnosis": "Accepted a costly change without a return",
    "opening_plan": "Choose a high-value whole package",
    "offer_audit": "Calculate each changed term's cost",
    "closing_plan": "Compare against the current alternative",
    "lessons": [
        {
            "trigger": "a new request",
            "action": "ask for reciprocity",
            "exception": "if costless",
            "evidence": "practice turn 2",
        }
    ],
    "corrections": [
        "Price the change and ask for a conditional return",
        "Compare the whole package before accepting",
    ],
}


def test_consolidation_uses_own_visible_evidence_and_checked_examples(case, tmp_path):
    sessions = [practice(case, "first"), practice(case, "second")]
    llm = ScriptedLLM([PLAN])
    workbook, examples = consolidate(case, sessions, ["visible debrief"], llm, tmp_path)
    content = workbook.for_learner(examples)
    assert content.startswith(PROCEDURE)
    assert all(x["chosen_points"] - x["previous_own_offer_points"] == -3000 for x in examples)
    assert "a change of -3000" in content and "NOT current-case targets" in content
    assert "practice turn 2" not in content  # private evidence references are not carried over
    assert case.role("recruiter").confidential_brief not in str(llm.calls)
    assert "initial_tendencies" not in str(llm.calls)
    assert "visible debrief" in str(llm.calls)
    # Resumption preserves the same learned output instead of resampling the coach.
    assert consolidate(case, sessions, ["visible debrief"], llm, tmp_path)[0] == workbook
    assert len(llm.calls) == 1
    with pytest.raises(ValueError, match="input changed"):
        consolidate(case, sessions, ["different debrief"], llm, tmp_path)


def test_acceptance_arithmetic_and_successful_opening_fallback(case):
    session = practice(case, "opening", counterpart_accepts=True)
    evidence, examples = evidence_and_examples(case, [session])
    expected = points(case, "candidate", session.turns[0].offer)
    assert evidence[0]["turns"][-1]["own_points"] == expected
    assert examples[0]["reference"] == "walkaway"
    plan = Workbook.model_validate({**PLAN, "corrections": ["Keep checking value"]})
    assert "My walk-away alternative" in plan.for_learner(examples)
    active = session.model_copy(update={"status": "active"})
    with pytest.raises(ValueError, match="completed"):
        evidence_and_examples(case, [active])


def test_hidden_opponent_sheet_does_not_change_consolidation_evidence(case):
    session = practice(case, "one")
    changed = case.model_copy(deep=True)
    other = changed.role("recruiter")
    other.confidential_brief = "hidden different private instructions"
    other.reservation_value = 999999
    for table in other.points.values():
        for option in table:
            table[option] *= -3
    assert evidence_and_examples(case, [session]) == evidence_and_examples(changed, [session])


spec = importlib.util.spec_from_file_location(
    "consolidation_runner", Path(__file__).parents[1] / "scripts/consolidation_evaluate.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_assessment_resets_actor_and_uses_same_frozen_history_memory(case, tmp_path):
    memories = {m: [f"memory for {m}"] for m in runner.METHODS}
    runner.write_json(tmp_path / "raw/learner0.memories.json", {"memories": memories})
    before = (tmp_path / "raw/learner0.memories.json").read_bytes()

    class Experiment:
        raw = tmp_path / "assessment/raw"

        def __init__(self):
            self.calls = []

        def probe(self, key, traits, seed, feedback=None):
            self.calls.append((key, seed, list(feedback or [])))
            return 0.4 if feedback else 0.2

    exp = Experiment()
    traits = VirtualTraits.sample(random.Random(9))
    original = traits.model_copy(deep=True)
    rows = runner.assess_one(exp, tmp_path, 0, traits, 11, runner.METHODS, 0)
    assert len(exp.calls) == 5 and exp.calls[0][2] == []
    assert len({c[1] for c in exp.calls}) == 1
    assert sorted(c[2] for c in exp.calls[1:]) == sorted(memories.values())
    assert all(r["gain"] == pytest.approx(0.2) for r in rows)
    assert traits == original and (tmp_path / "raw/learner0.memories.json").read_bytes() == before


def test_comparisons_are_paired_by_persona_and_do_not_drop_missing_rows():
    rows = [
        {"user": u, "method": m, "baseline_G": 0.1, "final_G": 0.1 + gain, "gain": gain}
        for u in (1, 0)
        for m, gain in (("reports", 0.1 * u), ("workbook", 0.1 * u + 0.1))
    ]
    assert runner.summarize(rows)["workbook_minus_reports"]["mean"] == pytest.approx(0.1)
    with pytest.raises(ValueError, match="incomplete paired"):
        runner.summarize(rows[:-1])
    with pytest.raises(ValueError, match="duplicate"):
        runner.summarize(rows + rows[:1])
