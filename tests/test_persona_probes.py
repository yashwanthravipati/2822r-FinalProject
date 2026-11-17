import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from evaluate_corrected_transfer import Learner, traits_for  # noqa: E402
from negotrain.counterpart.agent import CounterpartMove
from negotrain.llm import CachedText, ScriptedLLM
from negotrain.profiling.observations import ERRORS, observe
from negotrain.schemas import Turn, TurnTags
from negotrain.virtual_users import LLMUser, VirtualTraits
from persona_decision import IntentLLM  # noqa: E402
from persona_instructions import apply_enactment  # noqa: E402
from probe_isolated_personas import actor_for  # noqa: E402
from probe_persona_controls import package, probe_case, probe_prefix, run_probe  # noqa: E402


@pytest.mark.parametrize("target", list(ERRORS))
def test_each_controlled_prefix_has_legal_positive_and_negative_witnesses(target):
    case = probe_case()
    for error in (False, True):
        session = probe_prefix(case, target, "test")
        before = observe(session, case).counts[target].occurrences
        offer, accept = package(0, 0, 0), False
        raised = [i.id for i in case.issues]
        if target == "error:1" and error:
            offer = package(1, 0, 0)
        elif target == "error:2":
            offer = package(1, 1, 0) if error else package(1, 0, 0)
        elif target == "error:3" and error:
            offer = package(2, 1, 1)
        elif target == "error:4" and error:
            offer, accept = None, True
        elif target == "error:5":
            offer = package(1, 0, 0)
            raised = ["price"] if error else raised
        elif target == "error:6":
            offer = package(1, 2, 1) if error else package(1, 0, 1)
        session.add_turn(
            Turn(
                index=len(session.turns),
                speaker="user",
                text="Test action",
                offer=offer,
                accept=accept,
                tags=TurnTags(source="scripted", raised_issues=raised),
            ),
            case,
        )
        if target == "error:5":
            session.add_turn(
                Turn(index=len(session.turns), speaker="counterpart", text="Agreed", accept=True),
                case,
            )
        after = observe(session, case).counts[target].occurrences
        assert (after > before) is error


def test_enactment_preserves_case_privacy_traits_and_cached_prefixes():
    case = probe_case()
    traits = VirtualTraits(
        errors={k: 0.9 for k in ERRORS}, awareness=0.5, rapport=0.5, response={k: 0 for k in ERRORS}
    )
    original = traits.model_dump()
    actor = LLMUser(case, "buyer", traits, ScriptedLLM([]))
    prefix = actor.system.parts
    apply_enactment(actor)
    assert actor.system.parts[: len(prefix)] == prefix
    assert traits.model_dump() == original
    assert case.role("seller").confidential_brief not in actor.system
    assert actor.system.cache_indices == (0, 1, 2)


def test_isolated_probes_do_not_forbid_overlapping_errors():
    case = probe_case()
    actor = actor_for(case, "error:6", 0.9, "enactment", ScriptedLLM([]))
    payload = json.loads("{" + actor.system.parts[1][2:] + "}")
    assert set(payload["initial_tendencies"]) == {"error:6"}
    assert payload["initial_tendencies"]["error:6"]["frequency"] == 0.9
    assert "unspecified, not zero" in actor.system
    # In this prefix, the target dominated move is necessarily also a first concession.
    session = probe_prefix(case, "error:6", "coupling")
    session.add_turn(
        Turn(
            index=len(session.turns), speaker="user", text="A worse package", offer=package(1, 2, 1)
        ),
        case,
    )
    counts = observe(session, case).counts
    assert counts["error:1"].occurrences == counts["error:6"].occurrences == 1


def test_probe_resume_does_not_repeat_paid_actor_after_failed_annotation(tmp_path):
    class FailTagger:
        def parse(self, system, messages, output_type, **kwargs):
            if output_type.__name__ == "TagBatch":
                raise RuntimeError("annotation interrupted")
            return output_type(
                message="Only the price matters here.",
                offer=[{"issue_id": k, "option_id": v} for k, v in package(1, 0, 0).terms.items()],
                accept=False,
                walk_away=False,
            )

    case = probe_case()
    with pytest.raises(RuntimeError, match="annotation interrupted"):
        run_probe(tmp_path, case, "enactment", "error:5", 0.9, 0, FailTagger())
    saved = json.loads(next((tmp_path / "raw").glob("*.json")).read_text())
    assert not saved["complete"] and len(saved["session"]["turns"]) == 3

    class TagsOnly:
        def parse(self, system, messages, output_type, **kwargs):
            assert output_type.__name__ == "TagBatch"
            return output_type(
                turns=[
                    {"index": i, "fact_ids": [], "raised_issues": ["price"], "rapport": False}
                    for i in (0, 2)
                ]
            )

    row = run_probe(tmp_path, case, "enactment", "error:5", 0.9, 0, TagsOnly())
    assert row["event"] and row["occurrences"] == 2


def test_private_intent_is_removed_from_public_move():
    llm = IntentLLM(
        ScriptedLLM(
            [
                {
                    "behavioral_intent": "habit_influenced",
                    "brief_effect": "Private simulation note",
                    "message": "Here is my offer.",
                    "offer": [],
                    "accept": False,
                    "walk_away": False,
                }
            ]
        )
    )
    move = llm.parse(CachedText("System"), [], CounterpartMove)
    assert "Private simulation note" not in move.model_dump_json()
    assert llm.notes == [
        {"behavioral_intent": "habit_influenced", "brief_effect": "Private simulation note"}
    ]


@pytest.mark.parametrize("uid", [0, 2])
def test_transfer_actor_matches_the_tested_probe_instruction_exactly(uid):
    class Spy:
        def __init__(self):
            self.systems = []

        def parse(self, system, messages, output_type, **kwargs):
            self.systems.append(str(system))
            return output_type(
                behavioral_intent="habit_resisted",
                brief_effect="Decline",
                message="I decline.",
                offer=[],
                accept=False,
                walk_away=True,
            )

    case = probe_case()
    traits = traits_for(uid)
    target = next(iter(traits.errors))
    a, b = Spy(), Spy()
    actor = LLMUser(case, "buyer", traits, Learner(a))
    reference = actor_for(case, target, 0.9, "enactment", IntentLLM(b))
    session = probe_prefix(case, target, "match")
    actor.respond(session)
    reference.respond(session)
    assert a.systems == b.systems
