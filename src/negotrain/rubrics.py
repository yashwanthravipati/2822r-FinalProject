"""Teaching profiles, public rubrics, and safe role projections. No inferred utilities."""

from __future__ import annotations

from negotrain.rubric_models import NegotiationType, SkillRubric
from negotrain.schemas import Case

TYPE_LABELS = {
    "distributive": "Distributive bargaining",
    "integrative": "Integrative deal-making",
    "institutional": "Institutional conflict and coordination",
}

# Public definitions contain no case-specific confidential material. Role examples belong
# in RoleSheet.skill_notes and are projected only to that role.
_ROWS = [
    (
        "rapport",
        "Building rapport and appealing to shared values",
        "Acknowledge concerns and use the counterpart's aims, mission and values constructively. "
        "Contextually appropriate small talk can count; politeness alone does not establish trust.",
        (
            "An opening, concern, tension, or stated value creates a reason for "
            "constructive engagement."
        ),
        "Dismisses a concern or uses a mission statement as an unsupported accusation.",
        "Acknowledges a concern or value without connecting it to the discussion.",
        "Responds respectfully and connects a relevant concern or value to a shared purpose.",
        "Acknowledge their concern and connect the discussion to a relevant shared aim or value.",
        (
            "Express a role-grounded concern or value and allow constructive "
            "engagement. Do not reward keywords with concessions."
        ),
    ),
    (
        "interests",
        "Understanding interests, constraints, and decision-making",
        (
            "Explore motivations beneath positions and clarify constraints, "
            "stakeholders and authority. "
        )
        + "Use tags interests, constraints, and authority to distinguish missed subskills.",
        "A demand, ambiguous restriction, or unresolved approval creates a need for clarification.",
        "Assumes a demand is a fixed constraint or overlooks relevant authority.",
        "Asks a generic question without checking the relevant motivation or approval.",
        "Explores and checks a relevant underlying interest, constraint, or decision dependency.",
        "Ask why the position matters and clarify who can authorize a workable arrangement.",
        (
            "State a role-grounded position before its rationale; answer "
            "relevant follow-ups truthfully. Preserve actual authority."
        ),
    ),
    (
        "facts",
        "Establishing facts and shared criteria",
        (
            "Distinguish verified facts, claims and uncertainty; explore "
            "standards for judging options."
        ),
        "A disputed claim, unknown fact, or choice of standards needs examination.",
        "Treats an uncertain claim as established or disregards relevant evidence.",
        "Mentions uncertainty or a criterion without explaining how to resolve or use it.",
        "Checks the relevant evidence or agrees how to apply a suitable criterion.",
        "Identify the uncertain claim and propose how to verify it or evaluate options fairly.",
        (
            "Surface a genuine uncertainty or criterion from the role; preserve "
            "provenance and do not invent contradictory facts."
        ),
    ),
    (
        "leverage",
        "Recognizing and using leverage",
        (
            "Recognize, ground and use consequential contributions, dependencies "
            "and credible alternatives. "
        )
        + (
            "Use tags recognition, grounding, and use. Cooperation can express "
            "leverage without threats."
        ),
        (
            "A request or obstacle makes the learner's supported contribution or "
            "alternative consequential."
        ),
        "Misses consequential supported leverage or exaggerates a dependency or alternative.",
        "Recognizes a contribution but does not connect it to a concrete proposal or request.",
        "Accurately connects a consequential contribution or alternative to a relevant proposal.",
        "Explain the contribution they depend on and connect it to a concrete, credible request.",
        (
            "Raise a real need or obstacle that makes contributions relevant, "
            "without announcing the learner's leverage or automatically yielding."
        ),
    ),
    (
        "options",
        "Developing options that address multiple interests",
        "Build and test alternatives using discovered interests and explicit constraints.",
        "Expressed interests or an impasse provide a basis to explore another arrangement.",
        "Repeats a position or offers an option that ignores known constraints.",
        "Suggests an alternative without connecting interests or checking feasibility.",
        "Develops and tests a feasible alternative addressing multiple expressed interests.",
        "Propose an alternative linked to both sides' stated interests and check its feasibility.",
        (
            "Engage with alternatives on their merits, explain genuine "
            "constraints, and avoid volunteering a complete solution."
        ),
    ),
    (
        "commitments",
        "Securing credible commitments and follow-through",
        (
            "Clarify responsibilities, approvals, timelines and contingencies. A "
            "promise is not delivery."
        ),
        "A tentative understanding or promise needs clarification before action or closure.",
        (
            "Treats an unsupported assurance as settled or leaves a "
            "consequential dependency unexamined."
        ),
        (
            "Records a next step but leaves a relevant owner, approval, deadline "
            "or contingency unclear."
        ),
        (
            "Clarifies the consequential implementation details, or explicitly "
            "records why approval is pending."
        ),
        (
            "Specify who does what, by when, with which approvals and a "
            "contingency if implementation fails."
        ),
        (
            "Distinguish willingness from authority. Allow clarification of "
            "actual dependencies; never invent authorization."
        ),
    ),
]


def default_rubric(kind: NegotiationType) -> list[SkillRubric]:
    weights = {
        "institutional": (1, 1, 1, 1, 1, 1),
        "integrative": (1, 1.5, 1, 1, 1.5, 1),
        "distributive": (1, 1, 1.5, 1.5, 0.5, 1),
    }[kind]
    return [
        SkillRubric(
            id="skill:" + row[0],
            label=row[1],
            description=row[2],
            opportunity=row[3],
            missed=row[4],
            intermediate=row[5],
            effective=row[6],
            practice=row[7],
            steering=row[8],
            importance=weight,
        )
        for row, weight in zip(_ROWS, weights, strict=True)
    ]


def case_rubric(case: Case) -> list[SkillRubric]:
    return [r for r in (case.rubric or default_rubric(case.negotiation_type)) if r.applicable]


def enable_rubric(case: Case, kind: NegotiationType) -> Case:
    """Preserve original point tables, disabling them for institutional cases."""
    data = case.model_dump()
    data.update(framework_version="rubric-v1", negotiation_type=kind)
    if kind != case.negotiation_type or not case.uses_rubric:
        data.update(rubric=[s.model_dump() for s in default_rubric(kind)], rubric_reviewed=False)
    if kind == "institutional":
        data["numeric_scoring"] = False
    return Case.model_validate(data)


def role_context(case: Case, role_id: str) -> dict:
    """No other role sheet, inaccessible source, or hidden point benchmark enters this payload."""
    role = case.role(role_id).model_dump()
    if not case.is_scored:
        role.pop("points", None)
        role.pop("reservation_value", None)
    return {
        "title": case.title,
        "public_brief": case.public_brief,
        "negotiation_type": case.negotiation_type,
        "own_role": role,
        "issues": [i.model_dump() for i in case.issues],
        "sources": [s.model_dump() for s in case.source_documents if role_id in s.visible_to],
        "rubric": [s.model_dump() for s in case_rubric(case)],
        "outcome_criteria": case.outcome_criteria,
    }


def steering(case: Case, focus: str | None, tier: int) -> str:
    skill = next((s for s in case_rubric(case) if s.id == focus), None)
    openness = (
        "Explain relevant concerns readily when asked."
        if tier <= 2
        else "Require specific follow-up questions before elaborating concerns."
        if tier <= 4
        else (
            "Be guarded and ask for concrete justification, but answer relevant questions honestly."
        )
    )
    return (
        f"Teaching profile: {TYPE_LABELS[case.negotiation_type]}. {openness}\n"
        "Keep facts, authority, constraints and available resources unchanged. Do not coach, "
        "invent approval, bluff about facts, or make concessions merely for a polite phrase.\n"
        + (
            skill.steering
            if skill
            else "Provide ordinary opportunities for discussion without a targeted skill."
        )
    )
