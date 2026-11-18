"""Component evaluation against human references; no simulated learner or learning claims."""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field, model_validator

from negotrain.counterpart.agent import CounterpartAgent
from negotrain.llm import LLM
from negotrain.profiling.skills import validate_assessment
from negotrain.rubric_models import SkillAssessment
from negotrain.schemas import Case, CounterpartProfile, Session


class ReferenceExample(BaseModel):
    id: str
    conversation_id: str
    split: str = "test"
    case: Case
    session: Session
    reference: SkillAssessment
    prediction: SkillAssessment | None = None

    @model_validator(mode="after")
    def validate_references(self):
        if self.reference.source != "human":
            raise ValueError("reference assessments must have human provenance")
        validate_assessment(self.reference, self.session, self.case)
        if self.prediction is not None:
            validate_assessment(self.prediction, self.session, self.case)
        return self


def _pr(tp: int, fp: int, fn: int) -> dict:
    return {
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def evaluate_diagnosis(
    examples: list[ReferenceExample], *, split: str = "test", weakness_threshold: float = 0.5
) -> dict:
    if not 0 <= weakness_threshold <= 1:
        raise ValueError("weakness threshold must be in [0,1]")
    seen_ids = set()
    splits: dict[str, set[str]] = defaultdict(set)
    rows = defaultdict(list)
    for ex in examples:
        if ex.id in seen_ids:
            raise ValueError("duplicate benchmark example id")
        seen_ids.add(ex.id)
        splits[ex.conversation_id].add(ex.split)
        if len(splits[ex.conversation_id]) > 1:
            raise ValueError("a conversation crosses development/test splits")
        if ex.split != split:
            continue
        predicted = (
            {(o.response_turn, o.skill_id): o for o in ex.prediction.observations}
            if ex.prediction
            else {}
        )
        for gold in ex.reference.observations:
            if gold.opportunity == "uncertain":
                continue
            pred = predicted.get((gold.response_turn, gold.skill_id))
            rows[gold.skill_id].append((gold, pred))
    result = {}
    for skill, items in sorted(rows.items()):
        tp = fp = fn = wtp = wfp = wfn = 0
        errors, scored_gold, predicted_count = [], 0, 0
        for gold, pred in items:
            gp = gold.opportunity == "present"
            pp = pred is not None and pred.opportunity == "present"
            predicted_count += pred is not None and pred.opportunity != "uncertain"
            tp += gp and pp
            fp += not gp and pp
            fn += gp and not pp
            if gp and gold.score is not None:
                scored_gold += 1
                ps = pred.score if pp else None
                if ps is not None:
                    errors.append(abs(gold.score - ps))
                gw = gold.score < weakness_threshold
                pw = ps is not None and ps < weakness_threshold
                wtp += gw and pw
                wfp += not gw and pw
                wfn += gw and not pw
            elif not gp and pp and pred.score is not None and pred.score < weakness_threshold:
                wfp += 1
        result[skill] = {
            "opportunity": _pr(tp, fp, fn),
            "weakness": _pr(wtp, wfp, wfn),
            "score_mae": sum(errors) / len(errors) if errors else None,
            "score_coverage": len(errors) / scored_gold if scored_gold else None,
            "scored_reference_opportunities": scored_gold,
            "predicted_scores": len(errors),
            "opportunity_coverage": predicted_count / len(items),
            "reference_labels": len(items),
        }
    return {
        "split": split,
        "weakness_threshold": weakness_threshold,
        "skills": result,
        "note": (
            "Missing scores are abstentions, not zero. Metrics do not establish human learning."
        ),
    }


class SteeringRating(BaseModel):
    example_id: str
    conversation_id: str
    focus: str | None
    target_opportunity: bool
    case_adherence: bool
    unintended_change: bool
    source: str = "human"


class FeedbackRating(BaseModel):
    example_id: str
    correctness: float = Field(ge=0, le=1)
    relevance: float = Field(ge=0, le=1)
    actionability: float = Field(ge=0, le=1)
    grounding: float = Field(ge=0, le=1)
    source: str = "human"


def evaluate_steering(ratings: list[SteeringRating]) -> dict:
    if any(r.source != "human" for r in ratings):
        raise ValueError("steering reference ratings must be human annotations")
    grouped = defaultdict(list)
    for rating in ratings:
        grouped[rating.focus or "none"].append(rating)
    return {
        focus: {
            "n": len(items),
            **{
                key: sum(getattr(r, key) for r in items) / len(items)
                for key in ("target_opportunity", "case_adherence", "unintended_change")
            },
        }
        for focus, items in grouped.items()
    }


def evaluate_feedback(ratings: list[FeedbackRating]) -> dict:
    if any(r.source != "human" for r in ratings):
        raise ValueError("feedback reference ratings must be human annotations")
    return {
        "n": len(ratings),
        **{
            key: sum(getattr(r, key) for r in ratings) / len(ratings) if ratings else None
            for key in ("correctness", "relevance", "actionability", "grounding")
        },
    }


def steering_responses(
    case: Case, prefix: Session, profiles: list[CounterpartProfile], llm: LLM
) -> list[dict]:
    """Generate one counterpart response per setting to an unchanged learner prefix."""
    if prefix.status != "active" or not case.uses_rubric:
        raise ValueError("steering evaluation requires an active rubric transcript prefix")
    if prefix.turns and prefix.turns[-1].speaker != "user":
        raise ValueError("prefix must end with a fixed learner response")
    responses = []
    for profile in profiles:
        session = prefix.model_copy(deep=True, update={"counterpart_profile": profile})
        turn = CounterpartAgent(case, session.counterpart_role_id, profile, llm).respond(session)
        responses.append(
            {"focus": profile.focus, "tier": profile.tier, "turn": turn.model_dump(mode="json")}
        )
    return responses
