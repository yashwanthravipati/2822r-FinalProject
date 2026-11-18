"""Rubric feedback and continuous Beta profiles for the main rehearsal flow.

Skill scores are effectiveness from 0 (missed) to 1 (effective), one per assessed
opportunity. Missing assessments stay missing: nothing here turns "not assessed" into a
low score, and constraints and commitments are shown separately from skills.
"""

from __future__ import annotations

import streamlit as st

from negotrain.app import style
from negotrain.app.style import md
from negotrain.feedback.coaching import Debrief, build_report
from negotrain.feedback.rubric import rubric_summary
from negotrain.profiling.skills import (
    assess_session,
    assessment_key,
    current_assessment,
    validate_assessment,
)
from negotrain.rubric_models import SkillAssessment
from negotrain.rubrics import case_rubric
from negotrain.schemas import Case, Session
from negotrain.sessions import SessionStore

CONSTRAINT_TONES = {
    "violation observed": "bad",
    "requires review": "warn",
    "no listed violation observed": "good",
}


def effectiveness(score: float | None) -> str:
    if score is None:
        return "Not assessed"
    if score >= 0.67:
        return f"Effective · {score:.0%}"
    if score >= 0.34:
        return f"Partly effective · {score:.0%}"
    return f"Missed · {score:.0%}"


def render_feedback(session: Session, case: Case, store: SessionStore) -> None:
    from negotrain.app import views

    assessment = current_assessment(session, case)
    summary = rubric_summary(session, case)
    report = build_report(session, case)
    _keep_report(session, store, report)

    tabs = st.tabs(["Skills and coaching", "Next steps and constraints", "Transcript", "Research"])
    with tabs[0]:
        style.section(
            "Skills in this rehearsal",
            "Each moment where a skill mattered is scored from missed to effective, using what "
            "you actually said.",
        )
        if assessment is None:
            style.empty(
                "Not assessed yet",
                f"Assessment reads each of your {session.user_turns} messages (one AI call "
                "each) and quotes the evidence for every score.",
            )
        else:
            _skill_scores(summary, assessment, case)
        if st.button(
            "Assess skills" if assessment is None else "Reassess skills",
            disabled=not views.online(),
            type="primary" if assessment is None else "secondary",
            icon=":material/fact_check:",
        ):
            try:
                with st.spinner("Assessing your skills…"):
                    assess_session(session, case, views.llm("low"))
                    store.save(session)
            except Exception as exc:  # noqa: BLE001 - keep the page usable, save nothing
                st.error(f"Assessment failed; no new scores were saved: {md(exc)}")
            else:
                st.rerun()
        if not views.online():
            style.muted("Assessing skills needs the AI connection (see Settings).")
        style.section("Coaching")
        views._render_report(report)
    with tabs[1]:
        _commitments_and_constraints(summary)
    with tabs[2]:
        for turn in session.turns:
            views.render_turn(case, session, turn)
    with tabs[3]:
        _research_tools(session, case, store, assessment)


def _keep_report(session: Session, store: SessionStore, report) -> None:
    """Save the deterministic rubric report so the assistant and history can read it."""
    saved = store.load_artifact(session.id, "feedback", Debrief)
    if saved is None or saved.report != report:
        usefulness = saved.usefulness if saved else None
        store.save_artifact(session.id, "feedback", Debrief(report=report, usefulness=usefulness))


def _skill_scores(summary: dict, assessment: SkillAssessment, case: Case) -> None:
    items = []
    for row in summary["skills"]:
        n, score = row["opportunities"], row["score"]
        meta = (
            f"{n} moment{'s' if n != 1 else ''} assessed"
            if n
            else "No moment for this skill came up in this rehearsal"
        )
        tone = "neutral" if score is None else "good" if score >= 0.67 else "warn"
        lo = hi = score if score is not None else 0.0
        items.append(
            style.meter(
                row["skill"], score, lo, hi, meta, tone=tone, value_text=effectiveness(score)
            )
        )
    style.meters(items)
    source = "a person" if assessment.source == "human" else "the AI assessor"
    labels = {s.id: s.label for s in case_rubric(case)}
    with st.expander(
        f"Evidence for each score (assessed by {source})", icon=":material/format_quote:"
    ):
        present = [o for o in assessment.observations if o.opportunity == "present"]
        if not present:
            st.caption("No scored moments.")
        for obs in present:
            quotes = "".join(
                f'<div class="nt-quote">#{e.turn_index}: “{style.esc(e.quote)}”</div>'
                for e in obs.evidence
            )
            tip = (
                f'<div class="nt-callout accent"><b class="t">Try</b>{style.esc(obs.suggestion)}'
                "</div>"
                if obs.suggestion
                else ""
            )
            style.html(
                f'<div class="nt-card" style="margin-bottom:.7rem"><h3>'
                f"{style.esc(labels.get(obs.skill_id, obs.skill_id))} · "
                f"{style.esc(effectiveness(obs.score))}</h3>{quotes}"
                f"<p>{style.esc(obs.rationale)}</p>{tip}</div>"
            )


def _commitments_and_constraints(summary: dict) -> None:
    from negotrain.app.views import COMMITMENT_STATUS, STATUS

    style.section(
        "Next steps and commitments",
        f"Outcome: {STATUS.get(summary['outcome']['status'], ('Unknown', ''))[0]}. A promise "
        "is not delivery: check who owns each step and what it depends on.",
    )
    commitments = summary["outcome"]["commitments"]
    if not commitments:
        style.empty("No next steps recorded", "Record them during a rehearsal, before finishing.")
    for c in commitments:
        details = [
            ("Owner", c.get("responsible_party")),
            ("Timing", c.get("deadline")),
            ("Approvals needed", ", ".join(c.get("required_approvals") or [])),
            ("If it can't proceed", c.get("contingency")),
        ]
        rows = "".join(
            f"<tr><td>{style.esc(k)}</td><td>{style.esc(v)}</td></tr>" for k, v in details if v
        )
        status = COMMITMENT_STATUS.get(c.get("status"), c.get("status", ""))
        style.html(
            f'<div class="nt-offer"><div class="nt-offer-head"><span>'
            f'{style.esc(c["description"])}</span><span class="w">{style.esc(status)}</span>'
            f"</div><table>{rows}</table></div>"
        )
    if summary["agreement_violations"]:
        style.callout(
            "; ".join(summary["agreement_violations"]), "bad", title="The agreement breaks a rule"
        )
    style.section(
        "Constraints", "Limits from your role sheet and whether the session respected them."
    )
    if not summary["constraints"]:
        style.muted("No explicit constraints were recorded; that doesn't establish feasibility.")
    for c in summary["constraints"]:
        turns = ", ".join(f"#{t}" for t in c["turns"])
        tone = CONSTRAINT_TONES.get(c["status"], "neutral")
        tags = style.badge_html(c["status"].capitalize(), tone)
        if turns:
            tags += style.badge_html(f"Turns {turns}")
        source = (
            f'<p class="nt-muted">Source: {style.esc(c["source"])}</p>' if c.get("source") else ""
        )
        style.html(
            '<div class="nt-card" style="margin-bottom:.6rem">'
            f"<h3>{style.esc(c['constraint'])}</h3>"
            f'<div class="nt-badges">{tags}</div>{source}</div>'
        )


def _research_tools(
    session: Session, case: Case, store: SessionStore, assessment: SkillAssessment | None
) -> None:
    style.section(
        "Human reference annotations",
        "For validating the assessor: download a template, annotate it, and import it here.",
    )
    template = SkillAssessment(**assessment_key(session, case), source="human")
    st.download_button(
        "Download annotation template",
        template.model_dump_json(indent=2),
        file_name=f"assessment-{session.id}.json",
        mime="application/json",
        icon=":material/download:",
    )
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
    if assessment:
        with st.expander("Raw assessment"):
            st.json(assessment.model_dump(), expanded=False)


def render_profile(prof, hist) -> None:
    skills = prof.skills
    style.section(
        "Your skills",
        f"Based on {skills.assessed_sessions} assessed session"
        f"{'s' if skills.assessed_sessions != 1 else ''}"
        + (f" ({skills.missing_sessions} more not assessed yet)" if skills.missing_sessions else "")
        + ". Estimates are kept separate by difficulty, so easier practice doesn't look like "
        "improvement.",
    )
    rows = []
    if not skills.strata:
        style.empty(
            "No skill estimates yet",
            "Finish a rehearsal, then press Assess skills on the Feedback page.",
        )
    for tier in sorted(skills.strata, key=lambda t: int(t) if str(t).isdigit() else 0):
        beliefs = skills.strata[tier]
        items = []
        for key, belief in beliefs.items():
            lo, hi = belief.interval()
            n = belief.opportunities
            value = belief.mean if n else None
            meta = (
                f"Based on {n:g} moment{'s' if n != 1 else ''} · likely between {lo:.0%} and "
                f"{hi:.0%}"
                if n
                else "No assessed moments at this difficulty yet"
            )
            tone = "neutral" if value is None else "good" if value >= 0.67 else "accent"
            items.append(style.meter(prof.labels[key], value, lo, hi, meta, tone=tone))
            rows.append(
                {
                    "Skill": prof.labels[key],
                    "Difficulty": tier,
                    "Estimated effectiveness": value,
                    "Beta interval": f"{lo:.2f}–{hi:.2f}",
                    "Opportunities": n,
                }
            )
        style.html(f'<div class="nt-kicker" style="margin-top:1rem">At difficulty {tier}</div>')
        style.meters(items)
    with st.expander("Detailed estimates", icon=":material/table:"):
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        st.caption(
            "Beta updates use fractional success/failure evidence. Intervals are model "
            "estimates, not yet calibrated against human annotations."
        )
