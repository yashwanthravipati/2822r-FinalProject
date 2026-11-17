import importlib.util
import itertools
import json
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


def test_independent_training_audit_rejects_wrong_seeds_and_curves(case, tmp_path, monkeypatch):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "audit_training", scripts / "analyze_consolidation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    case_path = tmp_path / "case.json"
    case_path.write_text(case.model_dump_json())
    terms = next(
        dict(zip((i.id for i in case.issues), options, strict=True))
        for options in itertools.product(*(i.option_ids() for i in case.issues))
        if all(
            sum(r.points[i.id][o] for i, o in zip(case.issues, options, strict=True))
            >= r.reservation_value
            for r in case.roles
        )
    )
    protocol = {
        "users": [0],
        "seed": 10,
        "methods": ["reports"],
        "probe_tiers": [1, 3, 5],
        "training_tiers": [2, 2, 4, 4, 4],
    }
    expected = {
        f"learner0_{stage}_t{t}": (t, 10 + t)
        for stage in ("baseline", "reports_after")
        for t in (1, 3, 5)
    }
    expected.update(
        {
            f"learner0_reports_train{i}": (t, 110 + i)
            for i, t in enumerate(protocol["training_tiers"])
        }
    )
    score, _ = module.economics(case, "candidate")
    for key, (tier, seed) in expected.items():
        s = {
            "id": key,
            "case_id": case.id,
            "user_role_id": "candidate",
            "counterpart_role_id": "recruiter",
            "seed": seed,
            "counterpart_profile": {"tier": tier},
            "status": "agreed",
            "agreement": {"terms": terms, "custom_terms": []},
        }
        module.write_json(
            tmp_path / "raw" / f"{key}.json",
            {"session": s, "complete": True, "schedule_violations": 0},
        )
    value = score(s)
    row = {
        "user": 0,
        "method": "reports",
        "baseline_G": value,
        "final_G": value,
        "gain": 0,
        "training_R": [value] * 5,
    }
    row_path = tmp_path / "raw/learner0.training.json"
    module.write_json(row_path, row)
    entry = {"path": str(case_path), "role": "candidate"}
    assert module.audit_case(tmp_path, entry, protocol, training=True)[1]["episodes"] == 11
    row["training_R"][0] += 0.1
    module.write_json(row_path, row)
    with pytest.raises(ValueError, match="training curve"):
        module.audit_case(tmp_path, entry, protocol, training=True)
    path = tmp_path / "raw/learner0_baseline_t1.json"
    changed = json.loads(path.read_text())
    changed["session"]["seed"] += 1
    module.write_json(path, changed)
    with pytest.raises(ValueError, match="seed"):
        module.audit_case(tmp_path, entry, protocol, training=True)


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
