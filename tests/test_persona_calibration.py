import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from calibrate_personas import CASES, SEEDS, episode, summarize  # noqa: E402
from negotrain.profiling.observations import ERRORS


def test_exposure_does_not_coach_the_calibration_actor(case, tmp_path):
    class Spy:
        def parse(self, system, messages, output_type, **kwargs):
            if output_type.__name__ == "CounterpartMove":
                payload = json.loads("{" + system.parts[2][2:])
                assert payload["past_coaching"] == []
                assert payload["pre_session_practice_callout"] is None
                assert case.role("recruiter").confidential_brief not in system
                return output_type(
                    message="I will decline.", offer=[], accept=False, walk_away=True
                )
            return output_type(
                turns=[{"index": 1, "fact_ids": [], "raised_issues": [], "rapport": False}]
            )

    row = episode(tmp_path, case, "candidate", "error:3", 0.9, SEEDS[0], Spy())
    saved = json.loads(next((tmp_path / "raw").glob("*.json")).read_text())
    assert saved["complete"]
    assert saved["session"]["counterpart_profile"]["focus"] == "error:3"
    assert row["untagged_user_turns"] == 0
    assert row["schedule_violations"] == 0


def test_missing_opportunities_remain_missing_and_pairs_must_be_complete():
    rows = [
        {
            "case": c,
            "target": k,
            "level": level,
            "seed": seed,
            "counts": {e: {"opportunities": 0, "occurrences": 0} for e in ERRORS},
        }
        for c, _ in CASES
        for k in ERRORS
        for level in (0.1, 0.9)
        for seed in SEEDS
    ]
    result = summarize(rows)
    assert not result["all_six_positive_direction"]
    assert all(
        g["conditional_rate"] is None for w in result["weaknesses"] for g in w["groups"].values()
    )
    with pytest.raises(ValueError):
        summarize(rows[:-1])
    with pytest.raises(ValueError):
        summarize(rows + [rows[0]])
