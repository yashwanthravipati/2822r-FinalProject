import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import evaluate_corrected_transfer as pilot
import evaluate_fresh_confirmation as confirmation


def test_exact_confirmation_rule_requires_positive_direction_and_all_pairs():
    positive = confirmation.paired_stats([0.1] * 8)
    assert positive["exact_sign_flip_p_two_sided"] == 2 / 256
    assert positive["confirmation_pass"]
    zero = confirmation.paired_stats([0.1] * 4 + [-0.1] * 4)
    assert zero["exact_sign_flip_p_two_sided"] == 1
    assert not zero["confirmation_pass"]
    assert not confirmation.paired_stats([-0.1] * 8)["confirmation_pass"]
    with pytest.raises(ValueError):
        confirmation.paired_stats([0.1] * 7)


def test_confirmation_preserves_profiles_and_uses_new_controller_seeds():
    expected = [pilot.traits_for(0).model_dump()] * 4 + [pilot.traits_for(2).model_dump()] * 4
    assert [confirmation.traits_for(u).model_dump() for u in confirmation.USERS] == expected
    old = {pilot.SEED + u * 1009 + t for u in pilot.USERS for t in range(5)}
    new = {confirmation.SEED + u * 1009 + t for u in confirmation.USERS for t in range(5)}
    assert not old & new
    assert len(new) == 40
