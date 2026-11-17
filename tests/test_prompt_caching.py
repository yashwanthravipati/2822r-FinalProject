"""Offline cache-prefix and billing regressions; no provider calls."""

import json
import random
from types import SimpleNamespace

import pytest

from negotrain.budget import SpendLedger
from negotrain.counterpart import TIERS, CounterpartAgent
from negotrain.feedback.coaching import _prompt, outcome_summary
from negotrain.llm import CachedText, ClaudeLLM, ScriptedLLM, Usage, cached_json
from negotrain.profiling.tagging import tag_session
from negotrain.schemas import Session, Turn
from negotrain.virtual_users import LLMUser, VirtualTraits


class Client:
    def __init__(self):
        self.beta = SimpleNamespace(messages=self)
        self.requests = []

    def with_options(self, **kwargs):
        return self

    def create(self, **request):
        self.requests.append(request)
        return SimpleNamespace(
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=10,
                cache_creation_input_tokens=1000,
                cache_read_input_tokens=2000,
                cache_creation=SimpleNamespace(
                    ephemeral_5m_input_tokens=400, ephemeral_1h_input_tokens=600
                ),
            ),
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="ok")],
        )


def gateway(tmp_path, ttl="5m"):
    return ClaudeLLM(client=Client(), ledger=SpendLedger(tmp_path / "ledger"), cache_ttl=ttl)


def texts(blocks):
    return [b["text"] for b in blocks]


def test_json_sections_preserve_the_original_text():
    sections = ({"case": {"unicode": "α", "list": [1, 2]}}, {"persona": 0.2}, {"memory": []})
    value = cached_json(*sections, prefix="instructions\n")
    assert value == "instructions\n" + json.dumps({k: v for s in sections for k, v in s.items()})
    assert "".join(texts(value.blocks())) == value
    with pytest.raises(ValueError):
        cached_json({"same": 1}, {"same": 2})


def test_gateway_does_not_cache_the_changing_suffix_or_mutate_messages(tmp_path):
    llm = gateway(tmp_path, "1h")
    system = CachedText("case", "persona", "coaching")
    content = CachedText("history", "deadline=19", cache_indices=(0,))
    messages = [{"role": "user", "content": content}]
    request = llm._request(system, messages, 100)
    assert "cache_control" not in request  # no automatic write of the changing suffix
    assert [b["cache_control"]["ttl"] for b in request["system"]] == ["1h"] * 3
    blocks = request["messages"][0]["content"]
    assert blocks[0]["cache_control"]["ttl"] == "5m"
    assert "cache_control" not in blocks[1]
    assert messages[0]["content"] is content
    blocks[0]["text"] = "mutation"
    assert llm._request(system, messages, 100)["messages"][0]["content"][0]["text"] == "history"


def test_breakpoint_overflow_fails_before_reservation_or_network(tmp_path):
    llm = gateway(tmp_path)
    with pytest.raises(ValueError, match="four"):
        llm.complete(CachedText("1", "2", "3", "4"), [{"role": "user", "content": CachedText("5")}])
    assert llm.ledger.snapshot()["requests"] == 0
    assert llm.client.requests == []
    with pytest.raises(ValueError, match="cache_ttl"):
        gateway(tmp_path, "2h")


def test_plain_prompts_keep_automatic_caching(tmp_path):
    llm = gateway(tmp_path)
    request = llm._request("system", [{"role": "user", "content": "hello"}], 100)
    assert request["cache_control"]["ttl"] == "5m"
    assert request["messages"][0]["content"] == "hello"


def test_mixed_ttl_provider_usage_settles_exact_cost(tmp_path):
    llm = gateway(tmp_path, "1h")
    assert llm.complete("system", [{"role": "user", "content": "hello"}]) == "ok"
    # Opus: ordinary input $4, output $20, reads $0.20, 5m writes $5, 1h writes $8 / MTok.
    expected = (100 * 4 + 10 * 20 + 2000 * 0.2 + 400 * 5 + 600 * 8) / 1e6
    assert llm.ledger.snapshot()["actual_usd"] == pytest.approx(expected, abs=1e-6)
    usage = llm.usage.snapshot()
    assert usage["cache_creation_1h_input_tokens"] == 600
    assert usage["cache_creation_5m_input_tokens"] == 400
    assert usage["cache_hit_calls"] == 1
    assert usage["cache_read_fraction"] == pytest.approx(2000 / 3100)
    assert usage["estimated_usd"] == pytest.approx(expected)
    assert usage["estimated_uncached_usd"] == pytest.approx((3100 * 4 + 10 * 20) / 1e6)


def test_missing_ttl_breakdown_uses_conservative_request_rate():
    usage = Usage(fallback_cache_ttl="1h")
    usage.add(SimpleNamespace(input_tokens=0, output_tokens=0, cache_creation_input_tokens=1000))
    assert usage.cost() == pytest.approx(0.008)
    assert Usage().snapshot()["cache_read_fraction"] == 0


def test_persona_and_coaching_changes_preserve_their_shared_prefixes(case):
    traits = VirtualTraits.sample(random.Random(1))
    llm = ScriptedLLM([])
    first = LLMUser(case, "candidate", traits, llm, ["one"]).system
    changed_feedback = LLMUser(case, "candidate", traits, llm, ["two"]).system
    assert first.parts[:2] == changed_feedback.parts[:2]
    assert first.parts[2] != changed_feedback.parts[2]
    other = LLMUser(case, "candidate", VirtualTraits.sample(random.Random(2)), llm).system
    assert first.parts[0] == other.parts[0]
    assert first.parts[1] != other.parts[1]
    assert case.role("recruiter").confidential_brief not in first


def test_growing_user_transcript_retains_prior_cache_boundary(case, tmp_path):
    llm = ScriptedLLM([{"message": "hello", "offer": [], "accept": False, "walk_away": False}] * 2)
    actor = LLMUser(case, "candidate", VirtualTraits.sample(random.Random(1)), llm)
    session = Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")
    session.add_turn(Turn(index=0, speaker="counterpart", text="Welcome"), case)
    session.add_turn(actor.respond(session), case)
    before = llm.calls[0][1][0]["content"]
    session.add_turn(Turn(index=2, speaker="counterpart", text="Your proposal?"), case)
    actor.respond(session)
    after = llm.calls[1][1][0]["content"]
    end = before.cache_indices[0] + 1
    assert before.parts[:end] == after.parts[:end]
    assert json.loads(before)["moves_remaining"] == 20
    assert json.loads(after)["moves_remaining"] == 19
    assert len(json.loads(after)["conversation"]) == 3
    request = gateway(tmp_path)._request(actor.system, llm.calls[1][1], 100)
    assert sum("cache_control" in b for b in request["system"]) == 3
    assert sum("cache_control" in b for b in request["messages"][0]["content"]) == 1
    assert "cache_control" not in request["messages"][0]["content"][-1]


def test_counterpart_history_stops_before_both_controller_notes(case, tmp_path):
    llm = ScriptedLLM([{"message": "Welcome"}])
    agent = CounterpartAgent(case, "recruiter", TIERS[3], llm)
    other_tier = CounterpartAgent(case, "recruiter", TIERS[5], llm)
    assert agent.system.parts[0] == other_tier.system.parts[0]
    session = Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")
    session.add_turn(Turn(index=0, speaker="user", text="Hello"), case)
    agent.respond(session)
    content = llm.calls[0][1][-1]["content"]
    assert isinstance(content, CachedText)
    assert content.parts[0] == "Hello"
    assert "Private note" in content and "Controller" in content
    request = gateway(tmp_path)._request(agent.system, llm.calls[0][1], 100)
    blocks = request["messages"][-1]["content"]
    assert "cache_control" in blocks[0]
    assert all("cache_control" not in b for b in blocks[1:])


def test_tagger_cache_contains_only_role_scoped_stable_context(case):
    session = Session(case_id=case.id, user_role_id="candidate", counterpart_role_id="recruiter")
    session.add_turn(Turn(index=0, speaker="user", text="Hello"), case)
    llm = ScriptedLLM(
        [{"turns": [{"index": 0, "fact_ids": [], "raised_issues": [], "rapport": False}]}]
    )
    tag_session(session, case, llm)
    content = llm.calls[0][1][0]["content"]
    assert content.cache_indices == (0,)
    assert "expected_user_turn_indices" not in content.parts[0]
    assert "Hello" not in content.parts[0]
    assert case.role("recruiter").confidential_brief not in content
    assert json.loads(content)["expected_user_turn_indices"] == [0]


def test_debrief_reuses_case_prefix_across_outcomes(case):
    session = Session(
        case_id=case.id,
        user_role_id="candidate",
        counterpart_role_id="recruiter",
        counterpart_profile=TIERS[2],
        status="impasse",
    )
    before = _prompt(session, case, outcome_summary(session, case), {}, [], None)
    session.counterpart_profile = TIERS[4]
    after = _prompt(session, case, outcome_summary(session, case), {}, [], None)
    assert before.parts[0] == after.parts[0]
    assert before.parts[1] != after.parts[1]
    assert before.cache_indices == (0,)
