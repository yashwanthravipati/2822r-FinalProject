import importlib.util
from pathlib import Path

import pytest


def test_prompt_selection_uses_only_selection_scores_and_prespecified_ties():
    path = Path(__file__).parents[1] / "scripts/select_consolidation.py"
    spec = importlib.util.spec_from_file_location("selection", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = [{"user": u, "method": m, "final_G": 0.5} for u in (0, 1) for m in module.ORDER]
    rows[-2]["final_G"] = 0.6
    assert module.select(rows, [0, 1]) == {"0": "reports", "1": "workbook"}
    with pytest.raises(ValueError, match="complete"):
        module.select(rows[:-1], [0, 1])


def test_cases_are_averaged_within_persona_and_incomplete_cohorts_rejected(monkeypatch):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "consolidation_analysis", scripts / "analyze_consolidation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = []
    for case_effect in (0.2, 0.8):
        cases.append(
            [
                {
                    "user": u,
                    "method": m,
                    "baseline_G": 0.1,
                    "gain": case_effect * u,
                    "final_G": 0.1 + case_effect * u,
                }
                for u in (0, 1)
                for m in ("reports", "workbook")
            ]
        )
    result = module.aggregate(cases, [0, 1], ["reports", "workbook"])
    gain = result["summary"]["workbook"]["gain"]
    assert gain["n"] == 2  # two personas, not four persona-case observations
    assert gain["mean"] == pytest.approx(0.25)
    assert result["summary"]["reports_minus_workbook"]["mean"] == 0
    with pytest.raises(ValueError, match="incomplete paired"):
        module.aggregate([cases[0], cases[1][:-1]], [0, 1], ["reports", "workbook"])
