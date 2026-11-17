import random
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from diverse_practice import SCHEDULE, rehearse
from negotrain.virtual_users import VirtualTraits
from test_consolidation import practice


def test_varied_practice_preserves_prefix_count_traits_and_sequential_reports(case):
    calls = []

    class Experiment:
        def __init__(self, label):
            self.label, self.case = label, case

        def episode(self, key, traits, tier, focus, seed, reports):
            calls.append((self.label, key, tier, focus, seed, list(reports)))
            return practice(case, key, counterpart_accepts=True)

        def feedback(self, session):
            return SimpleNamespace(report=SimpleNamespace(model_dump_json=lambda: session.id))

    experiments = {key: Experiment(key) for key in set(SCHEDULE)}
    traits = VirtualTraits.sample(random.Random(7))
    before = traits.model_copy(deep=True)
    prefix = ["first shared report", "second shared report"]
    reports, scores = rehearse(experiments, 3, traits, 17, prefix)
    assert tuple(c[0] for c in calls) == SCHEDULE
    assert [len(c[-1]) for c in calls] == [2, 3, 4]
    assert all(c[2:4] == (4, None) for c in calls)
    assert [c[4] for c in calls] == [17 + 700000 + 1009 * 3 + 100 + t for t in (2, 3, 4)]
    assert reports[:2] == prefix and len(reports) == 5 and len(scores) == 3
    assert reports[2:] == [c[1] for c in calls]
    assert len(prefix) == 2 and traits == before
    with pytest.raises(ValueError, match="exactly two"):
        rehearse(experiments, 3, traits, 17, reports)
