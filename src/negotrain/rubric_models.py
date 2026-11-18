"""Versioned contracts for contextual skill assessment and open commitments."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

NegotiationType = Literal["distributive", "integrative", "institutional"]


class SkillRubric(BaseModel):
    id: str
    label: str
    description: str
    opportunity: str
    missed: str
    intermediate: str
    effective: str
    practice: str
    steering: str
    importance: float = Field(default=1.0, ge=0, le=10)
    applicable: bool = True


class Evidence(BaseModel):
    turn_index: int = Field(ge=0)
    quote: str = Field(min_length=1)


class SkillObservation(BaseModel):
    skill_id: str
    start_turn: int = Field(ge=0)
    response_turn: int = Field(ge=0)
    opportunity: Literal["present", "absent", "uncertain"]
    score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    evidence: list[Evidence] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    suggestion: str = ""
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent(self):
        if self.start_turn > self.response_turn:
            raise ValueError("opportunity starts after the response")
        if self.opportunity != "present" and self.score is not None:
            raise ValueError("absent or uncertain opportunities cannot receive a score")
        if any(not self.start_turn <= e.turn_index <= self.response_turn for e in self.evidence):
            raise ValueError("evidence must belong to the opportunity window, without hindsight")
        return self


class SkillAssessment(BaseModel):
    version: Literal["rubric-v1"] = "rubric-v1"
    case_digest: str
    transcript_digest: str
    role_id: str
    source: Literal["human", "llm"]
    observations: list[SkillObservation] = Field(default_factory=list)


class Commitment(BaseModel):
    description: str = Field(min_length=1)
    responsible_party: str = ""
    deadline: str = ""
    required_approvals: list[str] = Field(default_factory=list)
    status: Literal["proposed", "agreed", "pending_approval", "completed", "unverified"] = (
        "proposed"
    )
    contingency: str = ""
    source: str = ""
