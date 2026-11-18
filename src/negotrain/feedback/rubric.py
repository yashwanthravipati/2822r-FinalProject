"""Keep observed skill evidence, constraint checks and outcome records separate."""

from __future__ import annotations

from negotrain.cases.scoring import score_offer
from negotrain.feedback.coaching import CoachingReport, Moment
from negotrain.llm import LLM
from negotrain.profiling.skills import (
    assess_session,
    assessed_observations,
    current_assessment,
    skill_counts,
)
from negotrain.rubrics import case_rubric
from negotrain.schemas import Case, Session


def rubric_summary(session: Session, case: Case) -> dict:
    labels = {s.id: s.label for s in case_rubric(case)}
    counts = skill_counts(session, case)
    # Numeric predicates are checked in code. Narrative constraints stay unverified.
    constraints = []
    role = case.role(session.user_role_id)
    for constraint in role.constraints:
        matches = [
            t.index
            for t in session.turns
            if t.offer
            and t.speaker == "user"
            and any(t.offer.terms.get(i) in banned for i, banned in constraint.disallowed.items())
        ]
        status = (
            "violation observed"
            if matches and constraint.hard and constraint.certainty != "uncertain"
            else "requires review"
            if not constraint.disallowed or constraint.certainty == "uncertain"
            else "no listed violation observed"
        )
        constraints.append(
            {
                "constraint": constraint.description,
                "status": status,
                "turns": matches,
                "source": constraint.source,
            }
        )
    if session.agreement:
        violations = score_offer(case, role.id, session.agreement).violations
    else:
        violations = []
    return {
        "skills": [
            {
                "skill_id": k,
                "skill": labels[k],
                "opportunities": n,
                "score": total / n if n else None,
            }
            for k, (total, n) in counts.items()
        ],
        "assessment_source": current_assessment(session, case).source
        if current_assessment(session, case)
        else None,
        "constraints": constraints,
        "agreement_violations": violations,
        "outcome": {
            "status": session.status,
            "commitments": [c.model_dump() for c in session.commitments],
            "criteria": [
                {"criterion": c, "status": "requires review"} for c in case.outcome_criteria
            ],
            "delivery": "not verified",
        },
    }


def rubric_report(session: Session, case: Case, llm: LLM | None = None) -> CoachingReport:
    assessment = current_assessment(session, case)
    if assessment is None and llm is not None:
        try:
            assessment = assess_session(session, case, llm)
        except (ValueError, RuntimeError):
            assessment = None
    observations = assessed_observations(session, case)
    skills = {s.id: s for s in case_rubric(case)}
    strengths = [
        f"{skills[o.skill_id].label}: {o.rationale} (score {o.score:.2f})."
        for o in observations
        if o.score >= 0.8
    ]
    weak = sorted((o for o in observations if o.score < 0.8), key=lambda o: o.score)
    moments = [
        Moment(
            turn_index=o.response_turn,
            title=skills[o.skill_id].label,
            what_happened=o.rationale,
            what_to_try=o.suggestion or skills[o.skill_id].practice,
            evidence="; ".join(f'Turn {e.turn_index}: "{e.quote}"' for e in o.evidence),
        )
        for o in weak[:3]
    ]
    return CoachingReport(
        headline=(
            "Review your skill evidence, constraints, and recorded commitments separately."
            if assessment
            else "This session needs a rubric assessment; no skill scores have been inferred."
        ),
        strengths=strengths[:3],
        improvements=[
            f"{skills[o.skill_id].label}: {o.rationale} (score {o.score:.2f})." for o in weak[:3]
        ],
        moments=moments,
        next_focus=skills[weak[0].skill_id].practice
        if weak
        else "Gather more evidence on relevant opportunities before identifying a weakness.",
        source="rubric-" + assessment.source if assessment else "rubric-unassessed",
    )
