import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from negotrain.llm import ScriptedLLM
from negotrain.virtual_users import VirtualTraits
from teachback_memory import Answer, build_memory, corrections
from test_consolidation import practice


def test_arithmetic_correction_ignores_the_models_wrong_numbers():
    example = {"previous_own_offer_points": 170, "chosen_points": 120, "walkaway": 130}
    answer = Answer(
        own_change=50,
        surplus_over_walkaway=10,
        explanation="wrong",
        conditional_trade="ask",
        when_to_close="if worthwhile",
    )
    result = corrections([example], [answer])[0]
    assert result["correct_own_change"] == -50
    assert result["correct_surplus_over_walkaway"] == -10
    with pytest.raises(ValueError, match="one answer"):
        corrections([example], [])


def test_teachback_preserves_reports_and_information_boundary(case, tmp_path):
    import random

    sessions = [practice(case, f"practice{i}") for i in range(5)]
    reports = [f"original report {i}" for i in range(5)]
    answer = {
        "own_change": 0,
        "surplus_over_walkaway": 0,
        "explanation": "check",
        "conditional_trade": "exchange",
        "when_to_close": "if worthwhile",
    }
    learner = ScriptedLLM([{"answers": [answer, answer]}])
    coach = ScriptedLLM(
        [
            {
                "trigger": "asked for another concession",
                "action": "price it",
                "exception": "close a worthwhile deal",
            }
        ]
    )
    traits = VirtualTraits.sample(random.Random(1))
    result = build_memory(case, sessions, reports, traits, coach, learner, tmp_path)
    assert result[0][0].endswith("\n\n".join(reports))
    assert case.role("recruiter").confidential_brief not in str(learner.calls + coach.calls)
    assert "correct_own_change" in str(coach.calls)
    assert build_memory(case, sessions, reports, traits, coach, learner, tmp_path) == result
    assert len(coach.calls) == len(learner.calls) == 1
    with pytest.raises(ValueError, match="five complete"):
        build_memory(case, sessions[:4], reports, traits, coach, learner, tmp_path)
