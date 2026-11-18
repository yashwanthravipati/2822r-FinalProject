import json
import random

import pytest
from pydantic import ValidationError

from negotrain.cases.parser import ParsedCase, to_case
from negotrain.cases.scoring import efficiency, score_offer
from negotrain.counterpart.agent import CounterpartAgent
from negotrain.counterpart.profiles import TIERS
from negotrain.counterpart.rule_based import RuleBasedCounterpart
from negotrain.curriculum import next_scenario
from negotrain.feedback.coaching import build_report
from negotrain.feedback.rollouts import analyze_session
from negotrain.feedback.rubric import rubric_summary
from negotrain.llm import ScriptedLLM
from negotrain.prep import build_prep
from negotrain.profiling.belief import BetaBelief
from negotrain.profiling.profile import build_profile
from negotrain.profiling.skills import (
    assess_session,
    assessment_key,
    build_skill_profile,
    choose_skill,
    current_assessment,
    skill_counts,
    validate_assessment,
)
from negotrain.rubric_evaluation import ReferenceExample, evaluate_diagnosis, steering_responses
from negotrain.rubric_models import Commitment, Evidence, SkillAssessment, SkillObservation
from negotrain.rubrics import case_rubric, enable_rubric, role_context
from negotrain.schemas import Case, Constraint, Issue, RoleSheet, Session, SourceDocument, Turn
from negotrain.sessions import SessionStore


@pytest.fixture
def institution():
    return Case(
        id="coordination",
        title="Service coordination",
        public_brief="Agree a service pathway.",
        framework_version="rubric-v1",
        negotiation_type="institutional",
        numeric_scoring=False,
        issues=[Issue(id="pathway", name="Pathway", options=[])],
        roles=[
            RoleSheet(
                id="provider",
                name="Provider",
                confidential_brief="We supply specialist capacity.",
                skill_notes={"skill:leverage": "LEARNER_ONLY_NOTE"},
                constraints=[
                    Constraint(description="Approval required", approval_required="Board")
                ],
            ),
            RoleSheet(id="agency", name="Agency", confidential_brief="OTHER_SECRET"),
        ],
        source_documents=[
            SourceDocument(name="agency.txt", text="OTHER_SOURCE_SECRET", visible_to=["agency"])
        ],
        outcome_criteria=["Approval dependencies recorded"],
    )


@pytest.fixture
def transcript(institution):
    return Session(
        case_id=institution.id,
        user_role_id="provider",
        counterpart_role_id="agency",
        counterpart_profile=TIERS[2],
        status="impasse",
        turns=[
            Turn(index=0, speaker="counterpart", text="Who can help us deliver this?"),
            Turn(index=1, speaker="user", text="We have the specialist team."),
            Turn(index=2, speaker="counterpart", text="What do you propose?"),
            Turn(index=3, speaker="user", text="Our team could support a pilot. FUTURE_TEXT"),
        ],
    )


def observation(score=0.4, turn=1, start=0, skill="skill:leverage", opportunity="present"):
    return SkillObservation(
        skill_id=skill,
        start_turn=start,
        response_turn=turn,
        opportunity=opportunity,
        score=score,
        evidence=[
            Evidence(
                turn_index=turn,
                quote="We have the specialist team."
                if turn == 1
                else "Our team could support a pilot.",
            )
        ],
        rationale="Contribution recognized; request needs clarification.",
        suggestion="Connect it to a request.",
    )


def annotate(session, case, observations, source="human"):
    session.assessment = SkillAssessment(
        **assessment_key(session, case), source=source, observations=observations
    )
    return session.assessment


def test_beta_fractional_scores_and_forgetting():
    b = BetaBelief()
    b.update(0.4, 1, 0.8)
    assert b.alpha == pytest.approx(1.4)
    assert b.beta == pytest.approx(1.6)
    assert b.mean == pytest.approx(1.4 / 3)
    b.update(1.0, 1, 0.5)
    assert (b.alpha, b.beta) == pytest.approx((2.2, 1.3))
    assert b.opportunities == 2
    with pytest.raises(ValueError):
        b.update(float("nan"), 1, 1)


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf")])
def test_effectiveness_is_bounded(value):
    with pytest.raises(ValidationError):
        observation(value)


def test_fractional_scores_missing_and_overlap(institution, transcript):
    annotate(
        transcript,
        institution,
        [
            observation(),
            observation(0.9, turn=3, start=0),
            observation(None, turn=3, start=2, skill="skill:rapport", opportunity="absent"),
        ],
    )
    counts = skill_counts(transcript, institution)
    assert counts["skill:leverage"] == (0.4, 1)
    assert counts["skill:rapport"] == (0, 0)
    profile = build_skill_profile([(transcript, institution)], (institution, "provider"))
    assert profile.at_tier(2)["skill:leverage"].mean == pytest.approx(1.4 / 3)
    assert profile.at_tier(2)["skill:rapport"].opportunities == 0
    assert not profile.at_tier(4)
    assert choose_skill(profile, institution, 2, policy="greedy") == "skill:leverage"
    assert choose_skill(profile, institution, 2, policy="none") is None
    assert choose_skill(profile, institution, 2, policy="random", rng=random.Random(1))


def test_unknown_opportunity_cannot_have_score():
    with pytest.raises(ValidationError):
        observation(0.3, opportunity="uncertain")


def test_assessment_drift_evidence_and_future_rejected(institution, transcript):
    a = annotate(transcript, institution, [observation()])
    validate_assessment(a, transcript, institution)
    altered = a.model_copy(deep=True)
    altered.observations[0].evidence[0].quote = "fabricated"
    with pytest.raises(ValueError, match="exact"):
        validate_assessment(altered, transcript, institution)
    transcript.turns[1].text += " edited"
    assert current_assessment(transcript, institution) is None
    with pytest.raises(ValidationError):
        SkillObservation(
            skill_id="skill:leverage",
            start_turn=0,
            response_turn=1,
            opportunity="present",
            score=0.5,
            rationale="test",
            evidence=[Evidence(turn_index=3, quote="future")],
        )


def test_prefix_only_assessment_atomicity(institution, transcript):
    batches = [
        {
            "observations": [
                observation(0.35, turn=t, start=t, skill=s.id).model_dump()
                for s in case_rubric(institution)
            ]
        }
        for t in (1, 3)
    ]
    llm = ScriptedLLM(batches)
    result = assess_session(transcript, institution, llm)
    assert len(result.observations) == 12
    first = llm.calls[0][1][0]["content"]
    assert "FUTURE_TEXT" not in first
    assert "OTHER_SECRET" not in first and "OTHER_SOURCE_SECRET" not in first
    assert "LEARNER_ONLY_NOTE" in first
    before = transcript.assessment.model_dump()
    with pytest.raises(ValueError):
        assess_session(transcript, institution, ScriptedLLM([{"observations": []}]))
    assert transcript.assessment.model_dump() == before


def test_unscored_case_prep_coaching_and_persistence(institution, transcript, tmp_path):
    from negotrain.schemas import Offer

    offer = Offer(custom_terms={"pathway": "Pilot subject to board approval"})
    assert score_offer(institution, "provider", offer).points is None
    assert efficiency(institution, offer) is None
    prep = build_prep(institution, "provider")
    assert prep.numbers is None
    assert prep.framework_version == "rubric-v1"
    report = build_report(transcript, institution)
    assert not report.strengths and not report.moments
    assert "needs a rubric assessment" in report.headline
    annotate(transcript, institution, [observation()])
    transcript.commitments.append(
        Commitment(description="Seek board approval", status="pending_approval")
    )
    store = SessionStore(tmp_path)
    store.save(transcript)
    loaded = store.load(transcript.id)
    assert loaded.commitments[0].status == "pending_approval"
    assert loaded.assessment.observations[0].score == 0.4
    summary = rubric_summary(loaded, institution)
    assert summary["constraints"][0]["status"] == "requires review"
    assert summary["outcome"]["delivery"] == "not verified"
    assert build_report(loaded, institution).moments[0].turn_index == 1
    cf = analyze_session(loaded, institution, lambda: pytest.fail("must not run numeric simulator"))
    assert cf.n_rollouts == 0 and cf.skipped_reason


def test_counterpart_steering_and_no_private_learner_leak(institution, transcript):
    prefix = transcript.model_copy(
        deep=True, update={"turns": transcript.turns[:2], "status": "active"}
    )
    move = dict(
        message="Let us clarify the approvals for that contribution.",
        offer=[],
        accept=False,
        walk_away=False,
    )
    llm = ScriptedLLM([move, move])
    profiles = [TIERS[2].model_copy(update={"focus": "skill:leverage"}), TIERS[4]]
    results = steering_responses(institution, prefix, profiles, llm)
    assert len(results) == 2 and len(prefix.turns) == 2
    system = llm.calls[0][0]
    assert "OTHER_SECRET" in system
    assert "LEARNER_ONLY_NOTE" not in system
    assert "automatic" in system or "automatically" in system
    assert (
        CounterpartAgent(institution, "agency", profiles[0], ScriptedLLM([])).minimum(prefix)
        is None
    )
    assert (
        "Offline practice"
        in RuleBasedCounterpart(institution, "agency", profiles[0]).respond(prefix).text
    )


def test_contextual_profile_and_curriculum(institution, transcript):
    annotate(transcript, institution, [observation(0.0)])
    profile = build_profile(
        "anonymous", [(transcript, institution)], context=(institution, "provider")
    )
    spec = next_scenario(profile, [(transcript, institution)], [institution.id])
    assert spec.focus == "skill:leverage" and spec.tier == 2
    # No full agreement does not automatically demote a learner.
    assert profile.skills.at_tier(2)["skill:leverage"].alpha == 1.0
    assert "active_case" not in profile.model_dump()


def test_parser_no_invented_utility_and_legacy_migration(case):
    parsed = ParsedCase(
        id="unscored",
        title="Institution",
        public_brief="Coordinate access.",
        negotiation_type="institutional",
        numeric_scoring=False,
        issues=[{"id": "access", "name": "Access", "options": []}],
        roles=[dict(id=r, name=r, confidential_brief=r, inferred=False) for r in ["a", "b"]],
        scoring_notes="No point tables supplied.",
    )
    result = to_case(parsed)
    assert result.uses_rubric and not result.is_scored
    assert result.roles[0].points == {} and result.roles[0].reservation_value is None
    upgraded = enable_rubric(case, "institutional")
    assert not upgraded.is_scored and case.is_scored
    assert upgraded.roles[0].points == case.roles[0].points
    assert len(case_rubric(upgraded)) == 6


def test_benchmark_reports_continuous_error_and_abstention(institution, transcript):
    ref = annotate(transcript, institution, [observation(0.3)])
    pred = ref.model_copy(deep=True)
    pred.source = "llm"
    pred.observations[0].score = 0.5
    example = ReferenceExample(
        id="one",
        conversation_id="c1",
        case=institution,
        session=transcript,
        reference=ref,
        prediction=pred,
    )
    metrics = evaluate_diagnosis([example])["skills"]["skill:leverage"]
    assert metrics["score_mae"] == pytest.approx(0.2)
    assert metrics["score_coverage"] == 1
    assert metrics["weakness"]["fn"] == 1
    example.prediction = None
    metrics = evaluate_diagnosis([example])["skills"]["skill:leverage"]
    assert metrics["score_mae"] is None and metrics["score_coverage"] == 0
    with pytest.raises(ValueError, match="crosses"):
        evaluate_diagnosis([example, example.model_copy(update={"id": "two", "split": "dev"})])
    with pytest.raises(ValidationError, match="human"):
        ReferenceExample(
            id="bad", conversation_id="c2", case=institution, session=transcript, reference=pred
        )


def test_role_projection_hides_inferred_points_and_other_sources(institution):
    context = json.dumps(role_context(institution, "provider"))
    assert "OTHER_SECRET" not in context and "OTHER_SOURCE_SECRET" not in context
    assert "reservation_value" not in context and '"points"' not in context


def test_formal_action_evidence_and_unassessed_custom_terms(institution, transcript):
    from negotrain.profiling.skills import evidence_text
    from negotrain.schemas import Offer

    transcript.turns[1].text = ""
    transcript.turns[1].offer = Offer(custom_terms={"pathway": "Seek board approval"})
    obs = observation(0.65)
    obs.evidence = [Evidence(turn_index=1, quote=evidence_text(transcript.turns[1]))]
    annotate(transcript, institution, [obs])
    validate_assessment(transcript.assessment, transcript, institution)
    assert skill_counts(transcript, institution)["skill:leverage"] == (0.65, 1)
    transcript.assessment = None
    assert not build_report(transcript, institution).strengths


def test_assistant_omits_inferred_points_and_private_other_role(case):
    from negotrain.assistant import context_sections

    upgraded = enable_rubric(case, "institutional")
    own, other = upgraded.roles
    other.confidential_brief = "DO_NOT_REVEAL_OTHER_BRIEF"
    sections = context_sections(upgraded, own.id, "Rehearse")
    sheet = json.loads(next(s.text for s in sections if s.title == "Your role sheet"))
    assert "points" not in sheet and "reservation_value" not in sheet
    assert "DO_NOT_REVEAL_OTHER_BRIEF" not in "".join(s.text for s in sections)
