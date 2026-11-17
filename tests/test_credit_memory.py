import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from credit_memory import build_memory, select_credit
from negotrain.llm import ScriptedLLM
from test_consolidation import PLAN, practice


def feedback(session_id, gain=0.2, interval=(0.1, 0.3), turn=2):
    action = {
        "offer": None,
        "accept": True,
        "walk_away": False,
        "text": "Agreed",
        "hindsight": False,
        "private_detector_metadata": "must not enter prompt",
    }
    return {
        "counterfactuals": {
            "session_id": session_id,
            "estimates": [
                {
                    "turn_index": turn,
                    "delta_interval": list(interval),
                    "scored_actual": {"outcomes": [0.1, 0.2], "action": action},
                    "scored_selected": {
                        "outcomes": [0.1 + gain, 0.2 + gain],
                        "action": {**action, "hindsight": True},
                    },
                }
            ],
        }
    }


def test_credit_prefers_supported_terminal_gain_and_distinct_sessions():
    first = feedback("first", 0.2)
    first["counterfactuals"]["estimates"].append(
        feedback("first", 0.3)["counterfactuals"]["estimates"][0]
    )
    uncertain = feedback("uncertain", 0.7, (-0.1, 0.9))
    second = feedback("second", 0.1, (0.01, 0.2))
    negative = feedback("negative", -0.2, (-0.3, -0.1))
    selected = select_credit([uncertain, first, negative, second])
    assert [e["session_id"] for e in selected] == ["first", "second"]
    assert selected[0]["mean_gain"] == pytest.approx(0.3)
    assert "private_detector_metadata" not in str(selected)
    assert selected[0]["scored_selected"]["hindsight"] is True
    assert select_credit([negative])[0]["mean_gain"] == pytest.approx(-0.2)
    assert select_credit([]) == []


@pytest.mark.parametrize("problem", ["missing_pair", "nonfinite", "interval"])
def test_credit_rejects_invalid_evidence(problem):
    item = feedback("one")
    estimate = item["counterfactuals"]["estimates"][0]
    if problem == "missing_pair":
        estimate["scored_selected"]["outcomes"].pop()
    elif problem == "nonfinite":
        estimate["scored_actual"]["outcomes"][0] = float("nan")
    else:
        estimate["delta_interval"] = [0.3, 0.1]
    with pytest.raises(ValueError):
        select_credit([item])


def test_credit_memory_is_role_visible_uncertain_and_resumable(case, tmp_path):
    sessions = [practice(case, "first"), practice(case, "second")]
    feedbacks = [feedback("first"), feedback("second", 0.1, (-0.1, 0.3))]
    coach = ScriptedLLM([PLAN])
    result = build_memory(case, sessions, ["visible debrief"], feedbacks, coach, tmp_path)
    memories, selected, _ = result
    assert "Estimated difference +0.200" in memories[0]
    assert "not an observed alternative outcome" in memories[0]
    assert "interval [-0.100, +0.300]" in memories[0]
    assert "private_detector_metadata" not in str(coach.calls)
    assert case.role("recruiter").confidential_brief not in str(coach.calls)
    assert "initial_tendencies" not in str(coach.calls)
    assert "visible debrief" in str(coach.calls)
    assert len(selected) == 2
    assert build_memory(case, sessions, ["visible debrief"], feedbacks, coach, tmp_path) == result
    assert len(coach.calls) == 1
    changed = copy.deepcopy(feedbacks)
    changed[0]["counterfactuals"]["session_id"] = "wrong"
    with pytest.raises(ValueError, match="alignment"):
        build_memory(case, sessions, [], changed, coach, tmp_path)
    assert len(coach.calls) == 1


def test_credit_rejects_opponent_turn_and_falls_back_without_evidence(case, tmp_path):
    sessions = [practice(case, "first")]
    coach = ScriptedLLM([])
    with pytest.raises(ValueError, match="own decision"):
        build_memory(case, sessions, [], [feedback("first", turn=1)], coach, tmp_path)
    item = feedback("first")
    item["counterfactuals"]["estimates"] = []
    memory, examples, plan = build_memory(case, sessions, [], [item], coach, tmp_path)
    assert "No counterfactual evidence" in memory[0] and examples == [] and plan is None
    assert coach.calls == []
