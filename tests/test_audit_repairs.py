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
    ["nan", "infinity", "duplicate_issue", "duplicate_option", "duplicate_role", "constraint"],
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
    else:
        data["roles"][0]["constraints"] = [{"description": "bad", "disallowed": {"typo": ["x"]}}]
    with pytest.raises(ValueError):
        Case.model_validate(data)
