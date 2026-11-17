import importlib.util
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from negotrain.learning import StrategyCard
from negotrain.schemas import Session, Turn
from negotrain.virtual_users import VirtualTraits

spec = importlib.util.spec_from_file_location(
    "ckpt3_runner", Path(__file__).parents[1] / "scripts" / "ckpt3_evaluate.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class FakeExperiment:
    def __init__(self, case, root):
        self.case, self.role, self.raw = case, "candidate", root / "raw"
        self.probes, self.episodes = [], []

    def probe(self, key, traits, seed, feedback=None):
        self.probes.append((key, list(feedback or []), traits.model_dump()))
        return 0.1 if feedback else 0.0

    def episode(self, key, traits, tier, focus, seed, feedback):
        self.episodes.append((key, tier, focus, list(feedback)))
        session = Session(
            id=key, case_id=self.case.id, user_role_id="candidate", counterpart_role_id="recruiter"
        )
        session.add_turn(Turn(index=0, speaker="user", text="stop", walk_away=True), self.case)
        return session

    def feedback(self, session):
        return SimpleNamespace(
            report=SimpleNamespace(model_dump_json=lambda: "report:" + session.id)
        )


def test_training_branches_reset_memory_and_preserve_persona(case, tmp_path, monkeypatch):
    updates = []
    card = StrategyCard.model_validate(
        {
            "rules": [
                {
                    "trigger": "an offer",
                    "action": "compare value",
                    "exception": "if infeasible reject",
                    "evidence": "turn 0",
                }
            ],
            "next_priority": "Compare value",
        }
    )

    def refine(case, session, previous, traits, coach, learner, root, *, rehearse):
        updates.append((session.id, previous, rehearse))
        return card

    monkeypatch.setattr(runner, "refine_memory", refine)
    exp = FakeExperiment(case, tmp_path)
    traits = VirtualTraits.sample(random.Random(1))
    original = traits.model_copy(deep=True)
    rows = runner.train_one(exp, tmp_path, 0, traits, {"seed": 7, "rounds": 2}, None, None)
    assert traits == original
    assert len(rows) == 3 and len(exp.episodes) == 6 and len(exp.probes) == 4
    for method in runner.METHODS:
        episodes = [r for r in exp.episodes if f"_{method}_" in r[0]]
        assert episodes[0][3] == []
        assert [r[1] for r in episodes] == [2, 2]
        assert all(r[2] is None for r in episodes)
        assert episodes[1][3]
    assert sum(previous is None for _, previous, _ in updates) == 2
    assert sum(rehearse for _, _, rehearse in updates) == 2
    assert len(runner.memory(tmp_path, 0, "reports")) == 2
    assert runner.memory(tmp_path, 0, "rehearsal") == [card.for_learner()]


def test_transfer_uses_detached_baseline_and_frozen_memory_only(case, tmp_path):
    for method in runner.METHODS:
        runner.write_json(tmp_path / "raw" / f"learner0_{method}.json", {"memory": [method]})
    exp = FakeExperiment(case, tmp_path / "heldout")
    traits = VirtualTraits.sample(random.Random(1))
    rows = runner.transfer_one(exp, tmp_path, 0, traits, {"seed": 7})
    assert len(rows) == 4
    assert len(exp.probes) == 5 and exp.probes[0][1] == []
    assert not exp.episodes
    for method in runner.METHODS:
        assert next(p for p in exp.probes if f"_{method}_after" in p[0])[1] == [method]
        assert runner.memory(tmp_path, 0, method) == [method]
    assert all(r["gain"] == pytest.approx(0.1) for r in rows)


def test_paired_summary_aligns_personas_and_rejects_missing_pairs():
    rows = [
        {"user": u, "method": m, "baseline_G": 0.2, "final_G": 0.2 + g, "gain": g}
        for u in (1, 0)
        for m, g in (("reports", 0.1 * u), ("rehearsal", 0.1 * u + 0.2))
    ]
    result = runner.summarize(list(reversed(rows)))
    assert result["rehearsal_minus_reports"]["mean"] == pytest.approx(0.2)
    with pytest.raises(ValueError, match="incomplete paired"):
        runner.summarize(rows[:-1])
