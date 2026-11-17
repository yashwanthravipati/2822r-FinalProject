import itertools
import json
import random

import pytest

from negotrain.cases.scoring import efficiency, joint_points, max_joint_offer, score_offer
from negotrain.llm import ScriptedLLM
from negotrain.profiling.observations import ERRORS
from negotrain.schemas import Case, Constraint, Offer
from negotrain.virtual_users import WEAKNESS_DESCRIPTIONS, LLMUser, VirtualTraits


def test_every_numeric_weakness_has_meaning_without_changing_traits(case):
    traits = VirtualTraits.sample(random.Random(1))
    before = traits.model_dump()
    a = LLMUser(case, "candidate", traits, ScriptedLLM([]), ["old feedback"])
    b = LLMUser(case, "candidate", traits, ScriptedLLM([]), ["new feedback"])
    payload = json.loads("{" + a.system.parts[1][2:] + "}")
    assert set(payload["initial_tendencies"]) == set(ERRORS) == set(WEAKNESS_DESCRIPTIONS)
    for key, value in payload["initial_tendencies"].items():
        assert value["frequency"] == traits.errors[key]
        assert value["name"] == ERRORS[key]
        assert value["description"] == WEAKNESS_DESCRIPTIONS[key]
    assert traits.model_dump() == before
    assert a.system.parts[:2] == b.system.parts[:2]
    assert case.role("recruiter").confidential_brief not in a.system


def test_efficiency_denominator_respects_constraints_from_either_role(case):
    unconstrained = max_joint_offer(case)
    case.roles[0].constraints.append(
        Constraint(description="ban", disallowed={"salary": [unconstrained.terms["salary"]]})
    )
    case.roles[1].constraints.append(
        Constraint(description="ban", disallowed={"remote": [unconstrained.terms["remote"]]})
    )
    best = max_joint_offer(case)
    assert all(score_offer(case, r.id, best).valid for r in case.roles)
    legal = []
    for options in itertools.product(*(i.option_ids() for i in case.issues)):
        offer = Offer(terms=dict(zip([i.id for i in case.issues], options, strict=True)))
        if all(score_offer(case, r.id, offer).valid for r in case.roles):
            legal.append(joint_points(case, offer))
    assert joint_points(case, best) == max(legal)
    assert efficiency(case, best) == 1


@pytest.mark.parametrize(
    "defect",
    [
        "nan",
        "infinity",
        "duplicate_issue",
        "duplicate_option",
        "duplicate_role",
        "constraint",
        "extra_issue_points",
        "extra_option_points",
        "blank_case",
        "blank_issue",
        "blank_role",
        "blank_option",
    ],
)
def test_bad_case_data_is_rejected_before_simulation(case, defect):
    data = case.model_dump()
    if defect == "nan":
        data["roles"][0]["reservation_value"] = float("nan")
    elif defect == "infinity":
        data["roles"][0]["points"]["salary"]["s150"] = float("inf")
    elif defect == "duplicate_issue":
        data["issues"].append(data["issues"][0])
    elif defect == "duplicate_option":
        data["issues"][0]["options"].append(data["issues"][0]["options"][0])
    elif defect == "duplicate_role":
        data["roles"].append(data["roles"][0])
    elif defect == "extra_issue_points":
        data["roles"][0]["points"]["unlisted"] = {"x": 1000000}
    elif defect == "extra_option_points":
        data["roles"][0]["points"]["salary"]["unlisted"] = 1000000
    elif defect == "blank_case":
        data["id"] = " "
    elif defect == "blank_issue":
        data["issues"][0]["id"] = " "
    elif defect == "blank_role":
        data["roles"][0]["id"] = " "
    elif defect == "blank_option":
        data["issues"][0]["options"][0]["id"] = " "
    else:
        data["roles"][0]["constraints"] = [{"description": "bad", "disallowed": {"typo": ["x"]}}]
    with pytest.raises(ValueError):
        Case.model_validate(data)


@pytest.mark.parametrize("extra_issue", [False, True])
def test_scorer_rejects_unlisted_terms_even_if_point_tables_are_mutated(case, extra_issue):
    offer = Offer(terms={i.id: i.option_ids()[0] for i in case.issues})
    if extra_issue:
        case.roles[0].points["unlisted_issue"] = {"unlisted": 1000000}
        offer.terms["unlisted_issue"] = "unlisted"
    else:
        case.roles[0].points["salary"]["unlisted"] = 1000000
        offer.terms["salary"] = "unlisted"
    result = score_offer(case, case.roles[0].id, offer)
    assert not result.valid
    assert any("unknown term" in message for message in result.violations)
    assert result.points < 1000000
