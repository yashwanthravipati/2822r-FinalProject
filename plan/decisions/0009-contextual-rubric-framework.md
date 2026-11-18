# 0009: Contextual rubrics and continuous Beta skill beliefs

- **Status:** accepted; implemented with offline validation, empirical evaluation pending
- **Date:** 2026-11-18
- **Deciders:** user-directed revision of report Section 1

## Decision

The main application uses negotiation-specific rubrics, focusing on institutional conflict
and coordination. The six dimensions are rapport/shared values; interests/constraints/
authority; facts/criteria; leverage; options; and commitments/follow-through.

An applicable, assessable opportunity receives an effectiveness score in [0,1], with 0
missed and 1 effective. Intermediate values represent effectiveness, not assessor confidence.
Missing, uncertain and inapplicable assessments are excluded. Overlapping observations
of the same skill opportunity count once. Evidence must quote the learner-visible transcript
prefix. Private role examples are projected to their authorized role only.

Retain the Beta model. An opportunity contributes q success and 1-q failure evidence;
updates preserve the prior while discounting accumulated evidence. Fractional observations
make this an evidence-weighting approximation, not an exact continuous-data likelihood.
Profiles initially pool only matching case/role/rubric and difficulty, avoiding unsupported
claims of transfer. The rejected three-category Dirichlet proposal is superseded.

Institutional cases need no utility tables. Skill assessments, mechanically checkable
constraint findings, and recorded outcome/commitment details remain separate. Dialogue
steering preserves case facts and authority, and never rewards rapport keywords with
automatic concessions. Earlier point-based experiments remain a legacy evaluation path.

## Validation

Diagnosis is evaluated against human reference annotations, with opportunity precision/recall,
continuous-score errors and explicit coverage. Fixed-prefix steering and human feedback
ratings are separate evaluations. No synthetic trainee gains establish human learning.
No live study, human annotation reliability, or model calibration is claimed by implementing
these contracts. See T-024 through T-027 and report Section 1.
