import itertools
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from negotrain.cases.offers import points
from negotrain.schemas import Offer
from value_worksheet import project_memories, worksheet, worksheet_values


def test_loss_table_recovers_exact_points_for_every_package(case):
    # Include negative utilities so the transformation cannot assume all-positive tables.
    own = case.role("candidate")
    for options in own.points.values():
        for option in options:
            options[option] -= 700
    values = worksheet_values(case, "candidate")
    tables = {
        row["issue"]: {o["id"]: o["loss_from_issue_maximum"] for o in row["options"]}
        for row in values["issues"]
    }
    for combination in itertools.product(*(i.option_ids() for i in case.issues)):
        terms = dict(zip((i.id for i in case.issues), combination, strict=True))
        loss = sum(tables[i][o] for i, o in terms.items())
        utility = points(case, "candidate", Offer(terms=terms))
        assert values["own_point_upper_bound"] - loss == utility
        assert (loss > values["maximum_total_loss_to_match_walkaway"]) == (
            utility < own.reservation_value
        )


def test_worksheet_uses_only_own_sheet_and_preserves_constraint_warning(case):
    original = worksheet(case, "candidate")
    changed = case.model_copy(deep=True)
    other = changed.role("recruiter")
    other.confidential_brief = "private hidden sheet"
    other.reservation_value = 999999
    other.constraints = []
    for options in other.points.values():
        for option in options:
            options[option] = -999999
    assert worksheet(changed, "candidate") == original
    assert "not a promise of a legal or mutually acceptable deal" in original
    assert "private hidden sheet" not in original
    assert "hard constraints" in original and "CURRENT-case" in original


def test_projection_exposes_one_case_and_rejects_mutation(tmp_path):
    path = tmp_path / "raw/learner0.memories.json"
    path.parent.mkdir()
    first = {"memories": {"worksheet_reports": ["FIRST CASE ONLY"]}}
    data = {"by_case": {"first": first, "second": {"memories": {"reports": ["SECOND"]}}}}
    path.write_text(json.dumps(data))
    projected = project_memories(tmp_path, 0, "first")
    visible = projected / "raw/learner0.memories.json"
    assert json.loads(visible.read_text()) == first
    assert "SECOND" not in visible.read_text()
    assert project_memories(tmp_path, 0, "first") == projected
    visible.write_text(json.dumps({"memories": {"worksheet_reports": ["changed"]}}))
    with pytest.raises(ValueError):
        project_memories(tmp_path, 0, "first")
