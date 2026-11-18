"""Rubric feedback and continuous Beta profiles for the main rehearsal flow."""

from __future__ import annotations

import streamlit as st

from negotrain.app.style import md
from negotrain.curriculum import next_scenario
from negotrain.feedback.coaching import Debrief, build_report
from negotrain.feedback.rubric import rubric_summary
from negotrain.profiling.skills import (
    assess_session,
    assessment_key,
    current_assessment,
    validate_assessment,
)
from negotrain.rubric_models import SkillAssessment
from negotrain.schemas import Case, Session
from negotrain.sessions import SessionStore


def render_feedback(session: Session, case: Case, store: SessionStore) -> None:
    from negotrain.app import views

    assessment = current_assessment(session, case)
    st.caption(
        f"Assessment uses up to {session.user_turns} model calls, one per learner response. "
        "Scores measure effectiveness from 0 (missed) to 1 (effective)."
    )
    if st.button(
        "Assess skills" if assessment is None else "Reassess skills",
        disabled=not views.online(),
        type="primary",
    ):
        try:
            with st.spinner("Assessing contextual opportunities…"):
                assess_session(session, case, views.llm("low"))
                store.save(session)
        except Exception as exc:
            st.error(f"Assessment failed; no new scores were saved: {md(exc)}")
        else:
            st.rerun()
    upload = st.file_uploader(
        "Import a human rubric assessment", type=["json"], key=f"assessment_{session.id}"
    )
    if upload is not None and st.button("Use human assessment"):
        try:
            candidate = SkillAssessment.model_validate_json(upload.getvalue())
            if candidate.source != "human":
                raise ValueError("the imported reference assessment must have human provenance")
            validate_assessment(candidate, session, case)
            session.assessment = candidate
            store.save(session)
        except ValueError as exc:
            st.error(md(exc))
        else:
            st.rerun()
    template = SkillAssessment(**assessment_key(session, case), source="human")
    st.download_button(
        "Download annotation template",
        template.model_dump_json(indent=2),
        file_name=f"assessment-{session.id}.json",
        mime="application/json",
    )
    if st.button("Generate feedback", key="rubric_feedback"):
        report = build_report(session, case)
        store.save_artifact(session.id, "feedback", Debrief(report=report))
    views._render_report(build_report(session, case))
    summary = rubric_summary(session, case)
    st.subheader("Constraints")
    if summary["constraints"]:
        st.dataframe(summary["constraints"], hide_index=True)
    else:
        st.caption("No explicit constraints were recorded; this does not establish feasibility.")
    st.subheader("Commitments and outcome")
    st.json(summary["outcome"], expanded=True)
    if summary["agreement_violations"]:
        st.warning("; ".join(summary["agreement_violations"]))
    with st.expander("Assessment evidence"):
        if assessment:
            st.json(assessment.model_dump(), expanded=False)
    with st.expander("Transcript"):
        for turn in session.turns:
            views.render_turn(case, session, turn)


def render_profile(prof, hist) -> None:
    from negotrain.app import views

    st.caption(
        f"{prof.skills.assessed_sessions} assessed sessions; "
        f"{prof.skills.missing_sessions} sessions without current assessments."
    )
    rows = []
    for tier, beliefs in prof.skills.strata.items():
        for key, belief in beliefs.items():
            lo, hi = belief.interval()
            rows.append(
                {
                    "Skill": prof.labels[key],
                    "Difficulty": tier,
                    "Estimated effectiveness": belief.mean if belief.opportunities else None,
                    "Beta interval": f"{lo:.2f}–{hi:.2f}",
                    "Opportunities": belief.opportunities,
                }
            )
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info("Complete a rehearsal and assess its opportunities to build your profile.")
    st.caption(
        "Beta updates use fractional success/failure evidence. Intervals are model estimates, "
        "not yet calibrated against human annotations. Difficulty levels are kept separate."
    )
    spec = next_scenario(prof, hist, [prof.active_case.id])
    st.info(spec.rationale)
    if st.button("Start this rehearsal →", type="primary"):
        st.session_state["preset"] = spec
        st.session_state.pop("session", None)
        views.go("rehearse")
