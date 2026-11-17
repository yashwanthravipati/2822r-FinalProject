import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from adaptive_memory import Plan, build_plan, choose, memory
from evaluate_adaptive_memory import CASES
from probe_persona_controls import probe_case, probe_prefix


def test_plan_payload_is_own_visible_and_citations_must_name_user_decisions(tmp_path):
    case = probe_case()
    sessions = [probe_prefix(case, "error:1", f"practice{i}") for i in range(5)]
    for s in sessions:
        s.status = "walked_away"
    own_turn = next(t.index for t in sessions[0].turns if t.speaker == "user")

    class Recorder:
        def parse(self, system, messages, schema, **kwargs):
            self.payload = json.loads(messages[0]["content"])
            return Plan.model_validate(
                {
                    "rules": [
                        {
                            "trigger": "I am about to concede again",
                            "action": "check the whole package",
                            "exception": "close a worthwhile deal",
                            "evidence": [{"session_id": sessions[0].id, "turn": own_turn}],
                        }
                    ]
                }
            )

    llm = Recorder()
    build_plan(case, sessions, llm, tmp_path / "a")
    first = llm.payload
    other = case.other_role("buyer")
    other.reservation_value += 12345
    for values in other.points.values():
        for option in values:
            values[option] += 54321
    build_plan(case, sessions, llm, tmp_path / "b")
    assert llm.payload == first
    assert set(first) == {"public_brief", "issues", "own_sheet", "practice"}
    assert "initial_tendencies" not in json.dumps(first)
    saved = tmp_path / "b" / "plan.json"
    data = json.loads(saved.read_text())
    data["output"]["rules"][0]["evidence"][0]["turn"] = 9999
    saved.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="absent or non-user"):
        build_plan(case, sessions, llm, tmp_path / "b")


def test_advice_keeps_all_five_reports_after_actor_truncation():
    reports = [f"original report {i}" for i in range(5)]
    retained = memory(reports, "personal advice")[-5:]
    assert json.loads(retained[0])["original_reports"] == reports
    assert memory(reports) == reports
    with pytest.raises(ValueError):
        memory(reports[:-1], "advice")


def test_selector_uses_mean_margin_and_conservative_ties():
    assert (
        choose({"reports": [0.5, 0.5], "generic": [0.6, 0.6], "personalized": [0.6, 0.6]})
        == "generic"
    )
    assert (
        choose({"reports": [0.5, 0.5], "generic": [0.51, 0.51], "personalized": [0.9, 0.1]})
        == "reports"
    )
    assert (
        choose({"reports": [0.5, 0.5], "generic": [0.4, 0.4], "personalized": [0.6, 0.7]})
        == "personalized"
    )
    with pytest.raises(ValueError):
        choose({"reports": [0.5], "generic": [0.6, 0.6], "personalized": [0.7, 0.7]})
    with pytest.raises(ValueError):
        choose({"reports": [0.5, 0.5], "generic": [0.6, 0.6], "personalized": [float("nan"), 0.7]})
    development = {c[0] for c in CASES["development"]}
    validation = {c[0] for c in CASES["validation"]}
    assert not development & validation
    assert not (development | validation) & {"sim4", "cedar_warehouse"}
