import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from final_personal_audit import ARMS, CASES, paired_stats
from freeze_residual_cases import cases
from train_residual_cohort import NEW_USERS, SEED, USERS, traits_for
from verify_ckpt3 import economics


def test_final_inference_requires_sixteen_independent_histories():
    result = paired_stats([0.1] * 16)
    assert result["positive_and_p_05"]
    assert result["exact_sign_flip_p_two_sided"] == 2 / 65536
    assert result["n"] == 16
    assert paired_stats([0.1] * 8 + [-0.1] * 8)["exact_sign_flip_p_two_sided"] == 1
    assert not paired_stats([-0.1] * 16)["positive_and_p_05"]
    for bad in ([0.1] * 15, [0.1] * 15 + [float("nan")]):
        with pytest.raises(ValueError):
            paired_stats(bad)


def test_final_cases_and_cohort_keep_scope_and_valid_surplus_bounds():
    assert ARMS == ("reports", "generic", "personalized")
    assert {c[0] for c in CASES} == {"pine_learning", "willow_kitchen"}
    assert len(USERS) == 16 and len(NEW_USERS) == 8
    assert sum("error:1" in traits_for(u).errors for u in USERS) == 8
    assert len({SEED + u * 1009 + t for u in NEW_USERS for t in range(5)}) == 40
    for case, role in cases():
        _, best = economics(case, role)
        assert best > case.role(role).reservation_value
        assert case.other_role(role).constraints and case.role(role).constraints
