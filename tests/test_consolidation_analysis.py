import importlib.util
from pathlib import Path

import pytest


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
