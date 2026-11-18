"""Pages of the NegoTrain app. main.py wires them into navigation.

The app runs locally for one person, so there is no sign-in: sessions are stored under one
implicit participant id. The only screen until a scenario exists is setup (page_setup):
case files -> parsed case -> role -> "active scenario". Then Prepare (brief + training plan),
Rehearse, Feedback (post-session only), Progress, and Real negotiation all work on that
scenario; "Switch scenario" in the sidebar goes back to setup.

Presentation rules: plain language first (difficulty, share of the possible gains), research
detail (rollout counts, intervals, raw features) one click away in expanders or tabs; one
primary action per screen; long case prose rendered through ``style.md`` so dollar amounts
don't turn into LaTeX.

Information hiding: the counterpart's sheet is never rendered before a session ends, and the
counterpart agent never receives the user's sheet. Without an API key (or with
NEGOTRAIN_OFFLINE=1) everything runs on the rule-based counterpart and template feedback.
"""

from __future__ import annotations

import hashlib
import os
import random
from pathlib import Path

import streamlit as st
from pydantic import BaseModel

from negotrain import config
from negotrain.app import style
from negotrain.app.style import md
from negotrain.cases import case_library, save_private_case
from negotrain.cases.documents import UPLOAD_TYPES, extract_documents
from negotrain.cases.offers import surplus_share
from negotrain.cases.parser import parse_case, parse_documents
from negotrain.cases.scoring import score_offer
from negotrain.counterpart import TIERS, CounterpartAgent, RuleBasedCounterpart
from negotrain.counterpart.profiles import DIALS
from negotrain.curriculum import ScenarioSpec, counterpart_for, focus_callout, next_scenario
from negotrain.feedback import (
    CoachingReport,
    CounterfactualReport,
    Debrief,
    analyze_session,
    build_report,
    estimate_calls,
    outcome_summary,
)
from negotrain.feedback.rubric import rubric_summary
from negotrain.llm import ClaudeCodeLLM, ClaudeLLM, LLMRefusal, check_api_key
from negotrain.prep import Prep, build_prep, prep_key
from negotrain.profiling import build_profile, extract_features
from negotrain.profiling.profile import load_calibration
from negotrain.profiling.tagging import tag_session
from negotrain.rubric_models import Commitment
from negotrain.rubrics import TYPE_LABELS, case_rubric, enable_rubric
from negotrain.schemas import Case, CounterpartProfile, Offer, Participant, Session, Turn
from negotrain.sessions import SessionStore

# Filled in by main.py so pages can link to each other with st.switch_page.
PAGES: dict[str, st.Page] = {}

EST_COST_PER_CALL = 0.03  # USD, conservative for claude-opus-5-5 at low effort

# How participants rate the real counterpart, mapped onto the same 0-1 dials the AI uses.
DIAL_QUESTIONS = {
    "anchoring": "How extreme was their opening position?",
    "concession_rate": "How readily did they give ground?",
    "cooperativeness": "How open were they to trades and joint problem-solving?",
    "aggression": "How forceful or aggressive were they?",
    "disclosure": "How much did they share about their priorities?",
    "bluffing": "How much did they seem to exaggerate or bluff?",
    "concession_floor": "How much value did they insist on keeping in the end?",
}
RATING_SCALE = {"Not at all": 0.0, "A little": 0.25, "Somewhat": 0.5, "Quite": 0.75, "Very": 1.0}

# Plain names for the counterpart tiers (counterpart.profiles uses internal slugs).
DIFFICULTY_NAMES = {
    1: "Open and cooperative",
    2: "Collaborative but firm",
    3: "Guarded realist",
    4: "Tough anchorer",
    5: "Hardball",
}
STATUS = {
    "agreed": ("Deal reached", "good"),
    "impasse": ("No deal", "bad"),
    "active": ("In progress", "warn"),
    "abandoned": ("Abandoned", "neutral"),
}
SHORT_STATUS = {"agreed": "Deal", "impasse": "No deal", "active": "Ongoing", "abandoned": "Stopped"}
COMMITMENT_STATUS = {
    "proposed": "Proposed",
    "agreed": "Agreed",
    "pending_approval": "Waiting for approval",
    "completed": "Completed",
    "unverified": "Not yet verified",
}


def difficulty(tier: int | None) -> str:
    if tier is None:
        return "Difficulty not recorded"
    return f"Difficulty {tier} of 5 · {DIFFICULTY_NAMES.get(tier, TIERS[tier].name)}"


def session_label(session: Session) -> str:
    tier = session.counterpart_profile.tier if session.counterpart_profile else None
    level = f"Difficulty {tier}" if tier else session.kind.capitalize()
    return f"{session.created_at:%b %d, %H:%M} · {level} · {STATUS[session.status][0]}"


def percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


# --------------------------------------------------------------------------- resources


def _key_fingerprint() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "") + os.getenv("ANTHROPIC_AUTH_TOKEN", "")
    return hashlib.sha256(key.encode()).hexdigest()[:8]


BACKENDS = {
    "claude-code": "Claude Code (your Claude plan)",
    "api": "Anthropic API key",
    "offline": "Offline (no AI)",
}


def default_backend() -> str:
    choice = config.backend()
    if config.offline():
        return "offline"
    if choice in BACKENDS:
        return choice
    if config.claude_bin():
        return "claude-code"
    return "api" if config.has_api_key() else "offline"


def backend() -> str:
    """The backend in use: the Settings choice, falling back to offline when its
    prerequisite (the CLI or a key) is missing."""
    choice = st.session_state.get("backend") or default_backend()
    if choice == "claude-code" and not config.claude_bin():
        return "offline"
    if choice == "api" and not config.has_api_key():
        return "offline"
    return choice


@st.cache_resource
def _llm(kind: str, effort: str, fingerprint: str) -> ClaudeLLM | ClaudeCodeLLM:
    if kind == "claude-code":
        return ClaudeCodeLLM(effort=effort)
    return ClaudeLLM(effort=effort)


def llm(effort: str | None = None) -> ClaudeLLM | ClaudeCodeLLM:
    return _llm(backend(), effort or config.effort(), _key_fingerprint())


def online() -> bool:
    return backend() != "offline"


def library() -> dict[str, tuple[Case, object]]:
    return case_library()


def participant() -> Participant:
    """Local, single-user app: one implicit participant (NEGOTRAIN_PARTICIPANT, default
    "local"). Sessions are still keyed by it so profiles and the study data work unchanged."""
    return Participant(id=config.participant_id(), consented=True)


class ActiveScenario(BaseModel):
    """The case and role everything after the setup step works on (persisted locally)."""

    case_id: str
    role_id: str


def active_scenario() -> tuple[Case, str] | None:
    state = SessionStore().load_artifact("current", "state", ActiveScenario)
    if state is None:
        return None
    lib = library()
    if state.case_id not in lib:
        return None
    case = lib[state.case_id][0]
    return (case, state.role_id) if state.role_id in [r.id for r in case.roles] else None


def set_active_scenario(case_id: str, role_id: str) -> None:
    SessionStore().save_artifact(
        "current", "state", ActiveScenario(case_id=case_id, role_id=role_id)
    )
    for key in ("session", "case", "preset", "preset_role", "feedback_session"):
        st.session_state.pop(key, None)


def clear_active_scenario() -> None:
    path = SessionStore().root / "state" / "current.json"
    path.unlink(missing_ok=True)
    st.session_state.pop("setup_case_id", None)


def counterpart_factory(session: Session, case: Case, *, use_llm: bool, effort: str):
    """A zero-argument factory. Reads Streamlit state now, because rollouts call it from
    worker threads where session state is unavailable."""
    profile = session.counterpart_profile or TIERS[3]
    role_id = session.counterpart_role_id
    if use_llm:
        client = llm(effort)
        enforce = st.session_state.get("enforce_schedule", True)
        return lambda: CounterpartAgent(case, role_id, profile, client, enforce_schedule=enforce)
    return lambda: RuleBasedCounterpart(case, role_id, profile)


def make_counterpart(session: Session, case: Case):
    return counterpart_factory(session, case, use_llm=online(), effort=config.chat_effort())()


def history(pid: str) -> list[tuple[Session, Case]]:
    lib = library()
    return [(s, lib[s.case_id][0]) for s in SessionStore().for_participant(pid) if s.case_id in lib]


def current_profile(pid: str, hist: list[tuple[Session, Case]]):
    reports = {}
    store = SessionStore()
    for session, _ in hist:
        debrief = store.load_artifact(session.id, "feedback", Debrief)
        if debrief and debrief.counterfactuals:
            reports[session.id] = debrief.counterfactuals
    context = active_scenario()
    calibration = (
        load_calibration(*context, config.REPO_ROOT / "results" / "calibration")
        if context and not context[0].uses_rubric
        else None
    )
    return build_profile(pid, hist, reports=reports, context=context, calibration=calibration)


def finished_rehearsals(pid: str, case: Case, role_id: str) -> list[Session]:
    return [
        s
        for s in SessionStore().for_participant(pid)
        if s.kind == "rehearsal"
        and s.case_id == case.id
        and s.user_role_id == role_id
        and s.status in ("agreed", "impasse")
    ]


def go(page: str) -> None:
    """Switch page (falls back to a rerun when pages aren't registered, as in tests)."""
    if page in PAGES:
        st.switch_page(PAGES[page])
    st.rerun()


# --------------------------------------------------------------------------- shared rendering


def render_sheet(case: Case, role_id: str, *, title: str) -> None:
    """A role's confidential sheet: brief, point table (if scored), and constraints."""
    role = case.role(role_id)
    st.markdown(f"**{md(title)}: {md(role.name)}**")
    if role.inferred:
        style.callout(
            "This sheet was estimated from the other materials; it wasn't in the case files.",
            "warn",
        )
    st.markdown(md(role.confidential_brief))
    if case.is_scored:
        style.points_table(
            [
                (i.name, [(o.label, role.points[i.id][o.id]) for o in i.options])
                for i in case.issues
            ],
            role.reservation_value,
        )
    if role.constraints:
        st.markdown("**Constraints**")
        for c in role.constraints:
            st.markdown(f"- {md(c.description)}")


def offer_html(case: Case, offer: Offer, role_id: str, title: str = "Formal offer") -> str:
    result = score_offer(case, role_id, offer)
    rows = [(i.name, label) for i in case.issues if (label := offer.label(i))]
    if result.points is None:
        note = "Custom terms · not point-scored" if case.is_scored else ""
    else:
        note = f"{result.points:g} points to you"
    if not offer.is_complete(case):
        note = (note + " · " if note else "") + "partial"
    return style.offer_card(title, rows, note)


def describe_offer(case: Case, offer: Offer, role_id: str) -> str:
    result = score_offer(case, role_id, offer)
    worth = "not point-scored" if result.points is None else f"worth **{result.points:g}** to you"
    if not offer.is_complete(case):
        worth += " on the issues it covers (partial offer)"
    return f"{offer.describe(case)} — {worth}"


def render_turn(case: Case, session: Session, turn: Turn) -> None:
    is_user = turn.speaker == "user"
    name = "You" if is_user else case.role(session.counterpart_role_id).name
    extra = ""
    if turn.offer:
        extra += offer_html(case, turn.offer, session.user_role_id)
    if turn.accept:
        extra += style.event_html("Accepted the offer on the table", "good")
    if turn.walk_away:
        extra += style.event_html("Walked away", "bad")
    style.bubble(name, f"#{turn.index}", turn.text, mine=is_user, extra=extra)


def outcome_metrics(session: Session, case: Case) -> None:
    if case.uses_rubric and not case.is_scored:
        assessed = rubric_summary(session, case)["assessment_source"] is not None
        style.stats(
            [
                ("Result", SHORT_STATUS[session.status], "", ""),
                ("Your moves", str(session.user_turns), f"of {session.max_user_turns}", ""),
                ("Next steps recorded", str(len(session.commitments)), "", ""),
                (
                    "Skill assessment",
                    "Done" if assessed else "Not yet",
                    "by a person" if assessed and _human(session, case) else "",
                    "",
                ),
            ]
        )
        return
    o = outcome_summary(session, case)
    if o.surplus is None:
        note, tone = ("Custom terms", "neutral") if o.points is None else ("", "neutral")
    else:
        note = f"{o.surplus:+g} vs walking away"
        tone = "good" if o.surplus > 0 else "bad" if o.surplus < 0 else "neutral"
    share = None
    if o.points is not None:
        share = surplus_share(case, session.user_role_id, o.points)
    tiles = [
        ("Result", SHORT_STATUS[session.status], "", ""),
        ("Your points", "Not scored" if o.points is None else f"{o.points:g}", note, tone),
        (
            "Share of the possible gains",
            percent(share) if session.status == "agreed" else "0%",
            f"best possible: {o.best_possible:g} points",
            "neutral",
        ),
    ]
    if o.efficiency is not None:  # only meaningful for a scored deal
        tiles.append(
            ("Joint efficiency", percent(o.efficiency), "value both sides kept", "neutral")
        )
    style.stats(tiles)


def _human(session: Session, case: Case) -> bool:
    return rubric_summary(session, case)["assessment_source"] == "human"


# --------------------------------------------------------------------------- sidebar


def sidebar() -> None:
    style.inject()
    style.brand()
    with st.sidebar:
        current = active_scenario()
        if current:
            case, role_id = current
            style.scenario_card(
                case.title,
                case.role(role_id).name,
                TYPE_LABELS.get(case.negotiation_type, "") if case.uses_rubric else "",
            )
            if st.button("Switch scenario", icon=":material/swap_horiz:", width="stretch"):
                clear_active_scenario()
                st.rerun()
            st.session_state.setdefault("show_assistant", True)
            st.toggle(
                "Show assistant",
                key="show_assistant",
                help="A side panel that answers questions about your case and materials.",
            )
        with st.expander("Settings", icon=":material/settings:"):
            _settings()


def _settings() -> None:
    st.session_state.setdefault("backend", default_backend())
    st.radio(
        "AI connection",
        list(BACKENDS),
        format_func=BACKENDS.get,
        key="backend",
        help="Claude Code uses your logged-in Claude plan through the local `claude` CLI "
        "(personal use). The API key option bills an Anthropic API account. Offline uses "
        "a rule-based counterpart and template feedback.",
    )
    choice = st.session_state["backend"]
    if choice == "api":
        _api_key_input()
    if choice == "claude-code" and not config.claude_bin():
        st.warning("Claude Code isn't installed on this machine, so the app is running offline.")
    if online():
        where = "plan usage" if backend() == "claude-code" else "API usage"
        st.caption(f"Model `{config.model()}` · chat effort `{config.chat_effort()}`")
        st.caption(
            f"{where.capitalize()} this run: {_total_calls()} calls "
            f"(about ${_total_cost():.2f} at API prices)"
        )
    else:
        st.caption("Offline: a rule-based counterpart and template feedback.")
    st.divider()
    st.caption("Research options")
    st.toggle(
        "Facilitator mode",
        key="facilitator",
        help="Shows full case files, including confidential sheets. Keep off for participants.",
    )
    st.checkbox(
        "Enforce concession schedule in code",
        value=True,
        key="enforce_schedule",
        help="Off gives the prompt-only counterpart (for the T-017 comparison).",
    )


def _apply_key(widget_key: str) -> None:
    """on_change callback: validate the pasted key, use it for this app process, and clear
    the field (callbacks run before widgets render, so the field can be reset here)."""
    key = st.session_state.get(widget_key, "").strip()
    st.session_state[widget_key] = ""
    if not key:
        return
    problem = check_api_key(key)
    if problem:
        st.session_state["api_key_error"] = f"Key not saved: {problem}."
        return
    os.environ["ANTHROPIC_API_KEY"] = key
    st.session_state.pop("api_key_error", None)
    st.session_state["backend"] = "api"
    st.session_state["api_key_ok"] = True


def _api_key_input(where: str = "settings") -> None:
    """Enter, replace, or remove the API key. Kept in this process's environment only
    (never written to disk); a key from .env can be replaced the same way."""
    current = os.getenv("ANTHROPIC_API_KEY", "")
    widget_key = f"api_key_{where}"
    if current:
        st.caption(f"API key in use: …{current[-4:]}")
    st.text_input(
        "Replace API key" if current else "Anthropic API key",
        type="password",
        key=widget_key,
        placeholder="sk-ant-…",
        on_change=_apply_key,
        args=(widget_key,),
        help="Press Enter to apply. Checked against the API (free), kept in memory only. "
        "To make it permanent, put ANTHROPIC_API_KEY in .env.",
    )
    if error := st.session_state.get("api_key_error"):
        st.error(error)
    elif st.session_state.pop("api_key_ok", False):
        st.success("Key works and is now in use.")
    if current and st.button("Remove key", key=f"remove_key_{where}"):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        st.rerun()


# --------------------------------------------------------------------------- setup


def page_setup() -> None:
    style.page_header(
        "Practice your next negotiation",
        "Bring the materials for a negotiation you're preparing for. You'll get a preparation "
        "brief, AI counterparts to rehearse against, and feedback after every round.",
        kicker="Set up your scenario",
    )
    style.how_it_works(
        [
            (
                "Prepare",
                "Read a brief built from your own role sheet: your limits, "
                "priorities, and questions to ask.",
            ),
            (
                "Rehearse",
                "Negotiate in chat against an AI counterpart whose difficulty "
                "you can raise as you improve.",
            ),
            (
                "Get feedback",
                "After each round, see what worked, the moments that mattered, "
                "and what to practise next.",
            ),
        ]
    )
    st.space("medium")
    upload_col, saved_col = st.columns([3, 2], gap="medium")
    with upload_col, style.card("upload"):
        st.markdown("#### Upload your case materials")
        st.caption(
            "General instructions, your confidential role sheet, score tables. PDF, Word, "
            "text, or a ZIP of them."
        )
        if not online():
            style.callout(
                "Reading files needs Claude. Sign in to Claude Code on this machine, or paste "
                "an Anthropic API key below. Saved cases work offline.",
                "warn",
            )
            _api_key_input("setup")
        files = st.file_uploader(
            "Case materials",
            type=list(UPLOAD_TYPES),
            accept_multiple_files=True,
            label_visibility="collapsed",
            help="Scanned PDFs without a text layer can't be read.",
        )
        infer = st.checkbox(
            "If the other side's instructions aren't included, estimate them", value=True
        )
        if st.button(
            "Build scenario", type="primary", disabled=not files or not online(), width="stretch"
        ):
            _build_scenario(participant(), files, infer)
    with saved_col, style.card("saved"):
        st.markdown("#### Or use a saved case")
        st.caption("Cases you've uploaded before, plus the sample case.")
        lib = library()
        ids = sorted(lib, key=lambda c: lib[c][0].title.lower())
        if ids:
            chosen = st.selectbox(
                "Case", ids, format_func=lambda c: lib[c][0].title, label_visibility="collapsed"
            )
            if st.button("Use this case", width="stretch"):
                st.session_state["setup_case_id"] = chosen
        else:
            st.caption("No saved cases yet.")

    lib = library()
    case_id = st.session_state.get("setup_case_id")
    if case_id not in lib:
        return
    _confirm_scenario(lib[case_id][0])


def _confirm_scenario(case: Case) -> None:
    style.section("Confirm your scenario", "Check the case, choose your role, and start.")
    with style.card("confirm", accent=True):
        st.markdown(f"### {md(case.title)}")
        style.badges([(i.name, "neutral") for i in case.issues])
        brief = case.public_brief.strip()
        if len(brief) > 420:
            st.markdown(md(brief[:420].rsplit(" ", 1)[0] + "…"))
            with st.expander("Read the full background"):
                st.markdown(md(brief))
        else:
            st.markdown(md(brief))
        role_ids = [r.id for r in case.roles]
        provided = [r.id for r in case.roles if not r.inferred]
        left, right = st.columns(2, gap="medium")
        with left:
            role_id = st.radio(
                "Which role are you playing?",
                role_ids,
                index=role_ids.index(provided[0]) if len(provided) == 1 else 0,
                format_func=lambda r: case.role(r).name,
                key=f"setup_role_{case.id}",
            )
        with right:
            kind = st.selectbox(
                "Type of negotiation",
                list(TYPE_LABELS),
                index=list(TYPE_LABELS).index(case.negotiation_type),
                format_func=lambda key: TYPE_LABELS[key],
                key=f"type_{case.id}",
                help="Sets which skills feedback focuses on. Institutional cases (like the "
                "class simulations) are judged on skills, not point scores.",
            )
        if case.role(role_id).inferred:
            style.callout(
                "This role's instructions were estimated, not uploaded. Is this really your role?",
                "warn",
            )
        elif case.other_role(role_id).inferred:
            style.callout(
                "The other side's instructions weren't uploaded, so the AI counterpart plays an "
                "estimated version of them. Each rehearsal varies its style to cover the range "
                "of opponents you might meet."
            )
        if st.button("Start training", type="primary", icon=":material/arrow_forward:"):
            save_private_case(enable_rubric(case, kind))
            set_active_scenario(case.id, role_id)
            st.rerun()


def _build_scenario(p: Participant, files: list, infer: bool) -> None:
    documents, warnings = extract_documents((f.name, f.getvalue()) for f in files)
    for warning in warnings:
        st.warning(warning)
    if not documents:
        st.error("None of the files had readable text.")
        return
    with st.spinner(
        f"Reading {len(documents)} file(s) and building the scenario (about a minute)…"
    ):
        try:
            case = parse_documents(
                documents,
                llm("medium"),
                infer_missing=infer,
                source=f"Uploaded: {', '.join(documents)}.",
            )
        except Exception as e:  # noqa: BLE001 - surface parse/API errors to the user
            st.error(f"Couldn't build a scenario from these files: {md(e)}")
            return
    save_private_case(case)
    st.session_state["setup_case_id"] = case.id
    st.success(f"Built **{md(case.title)}** with {len(case.issues)} issues.")


# --------------------------------------------------------------------------- prepare

TRAINING_PLAN = [
    (2, "Warm-up", "Practise your opening and ask about the other side's interests."),
    (2, "Consolidate", "Apply the last report's advice in another moderate rehearsal."),
    (4, "Stretch", "Practise packaging trades against a firmer counterpart."),
    (4, "Repeat under pressure", "Hold your ground and check reciprocity before conceding."),
]
RUBRIC_PLAN = [
    (2, "Warm-up", "Explore aims and values."),
    (2, "Consolidate", "Use your feedback at the same difficulty."),
    (4, "Stretch", "Clarify interests and authority under pressure."),
    (4, "Follow through", "Develop options and credible next steps."),
]


def page_prepare() -> None:
    case, role_id = active_scenario()
    p = participant()
    style.page_header(
        "Prepare",
        f"{case.title} · You play the {case.role(role_id).name}",
        step=1,
    )
    store = SessionStore()
    key = prep_key(p.id, case.id, role_id)
    prep = store.load_artifact(key, "prep", Prep)
    if prep is None or (case.uses_rubric and prep.framework_version != case.framework_version):
        with st.spinner("Writing your preparation brief…"):
            prep = build_prep(case, role_id, llm() if online() else None)
            store.save_artifact(key, "prep", prep)

    plan, done = _plan_steps(p, case, role_id)
    next_index = min(done, len(plan) - 1)
    _next_up(p, case, role_id, plan, next_index)

    tab_names = ["Your brief", "Training plan"] + (["Skills"] if case.uses_rubric else [])
    tabs = st.tabs(tab_names)
    with tabs[0]:
        _render_prep(case, prep)
        if st.button("Rewrite brief", icon=":material/refresh:", type="tertiary"):
            with st.spinner("Writing your preparation brief…"):
                store.save_artifact(
                    key, "prep", build_prep(case, role_id, llm() if online() else None)
                )
            st.rerun()
    with tabs[1]:
        _training_plan(p, case, role_id, plan, done)
    if case.uses_rubric:
        with tabs[2]:
            _skills_list(case)


def _next_up(p: Participant, case: Case, role_id: str, plan, next_index: int) -> None:
    step = plan[next_index]
    title, _, why = step.rationale.partition(": ")
    with style.card("next", accent=True):
        left, right = st.columns([3, 1], vertical_alignment="center")
        with left:
            style.html(
                '<div class="nt-kicker">Up next in your training plan</div>'
                f'<div class="nt-row-title">{style.esc(title)} · '
                f"{style.esc(difficulty(step.tier))}</div>"
                f'<p class="nt-row-text">{style.esc(why)}</p>'
            )
        with right:
            if st.button("Start rehearsal", key="next_up", type="primary", width="stretch"):
                start_rehearsal(p, case, role_id, step, counterpart_opens=False)
                go("rehearse")


def _render_prep(case: Case, prep: Prep) -> None:
    n, b = prep.numbers, prep.brief
    style.section("The situation")
    style.lead(b.overview)
    if n is not None:
        style.stats(
            [
                ("Walk-away value", f"{n.walk_away:g}", "Don't accept less than this", "bad"),
                ("Ambitious target", f"{n.target:g}", "Aim for this", "good"),
                ("Best possible", f"{n.best_possible:g}", "If everything goes your way", ""),
            ]
        )
        style.section(
            "What matters most to you",
            "Issues ranked by how many of your points they move.",
        )
        style.priorities(
            [
                (pr.rank, pr.name, pr.best_option, pr.worst_option, pr.spread, pr.share)
                for pr in n.priorities
            ]
        )
    style.section("Your brief")
    style.card_grid(
        [
            style.list_card_html("Key facts", b.key_facts),
            style.list_card_html("Your interests", b.your_interests),
            style.list_card_html("The other side (hypotheses to test)", b.their_likely_interests),
            style.list_card_html("Questions to ask", b.questions_to_ask),
            style.list_card_html("Where to hold and where to give", b.tradeoffs),
            style.list_card_html("Pitfalls to avoid", b.pitfalls),
        ]
    )
    style.card_grid(
        [
            f'<div class="nt-card accent"><h3>Opening plan</h3>{style.paragraphs(b.opening_plan)}'
            "</div>",
            style.list_card_html("Checklist", b.checklist, checks=True),
        ]
    )
    with st.expander("Your confidential sheet", icon=":material/lock:"):
        render_sheet(case, prep.role_id, title="Your role")
    if b.source == "template":
        style.muted("Template brief: written offline or while the AI was unavailable.")


def _plan_steps(p: Participant, case: Case, role_id: str) -> tuple[list[ScenarioSpec], int]:
    """The five-session plan for this scenario and how many sessions are finished.

    Session k of the plan is the k-th finished rehearsal of this case and role, whatever
    difficulty it was played at; the last step adapts from the profile.
    """
    hist = history(p.id)
    spec = next_scenario(current_profile(p.id, hist), hist, [case.id])
    steps = [
        ScenarioSpec(
            tier=t,
            case_id=case.id,
            focus=spec.focus,
            focus_issue=spec.focus_issue,
            dial_overrides=spec.dial_overrides,
            rationale=f"{title}: {why}",
        )
        for t, title, why in (RUBRIC_PLAN if case.uses_rubric else TRAINING_PLAN)
    ]
    steps.append(spec.model_copy(update={"rationale": f"Recommended for you: {spec.rationale}"}))
    return steps, len(finished_rehearsals(p.id, case, role_id))


def _training_plan(
    p: Participant, case: Case, role_id: str, steps: list[ScenarioSpec], done: int
) -> None:
    next_index = min(done, len(steps) - 1)
    style.section(
        "Training plan",
        "Five rehearsals of this case against counterparts that get firmer. Check Feedback "
        "after each one; the last session adapts to what you need most.",
    )
    style.callout(focus_callout(steps[-1].focus), "accent", title="Practice focus")
    for n, step in enumerate(steps):
        title, _, why = step.rationale.partition(": ")
        state = "done" if n < done and n < len(steps) - 1 else "on" if n == next_index else ""
        with style.card(f"plan-{n}"):
            left, right = st.columns([5, 1], vertical_alignment="center")
            with left:
                tag = (
                    style.badge_html("Done", "good")
                    if state == "done"
                    else style.badge_html("Up next", "accent")
                    if state == "on"
                    else ""
                )
                style.numbered(
                    n + 1,
                    title,
                    why,
                    state=state,
                    extra=f'<div class="nt-badges">{style.badge_html(difficulty(step.tier))}'
                    f"{tag}</div>",
                )
            if right.button(
                "Start",
                key=f"plan_{n}",
                width="stretch",
                type="primary" if state == "on" else "secondary",
            ):
                start_rehearsal(p, case, role_id, step, counterpart_opens=False)
                go("rehearse")


def _skills_list(case: Case) -> None:
    style.section(
        "Skills you'll practise",
        "Feedback for this scenario looks for these skills in what you say. "
        + (
            "An instructor has reviewed this rubric."
            if case.rubric_reviewed
            else "This is the default rubric; instructor review is still pending."
        ),
    )
    style.card_grid(
        [
            f'<div class="nt-card"><h3>{style.esc(skill.label)}</h3>'
            f"<p>{style.esc(skill.description)}</p>"
            f'<p style="margin-top:.6rem"><b>Try:</b> {style.esc(skill.practice)}</p></div>'
            for skill in case_rubric(case)
        ]
    )


# --------------------------------------------------------------------------- rehearse


def _require_participant() -> Participant:
    return participant()


def _setup_rehearsal(p: Participant) -> None:
    case, role_id = active_scenario()
    hist = history(p.id)
    profile = current_profile(p.id, hist)
    spec = next_scenario(profile, hist, [case.id])
    preset: ScenarioSpec | None = st.session_state.get("preset")
    with style.card("start"):
        st.markdown("#### Start a rehearsal")
        st.caption(
            f"You'll negotiate {case.title} as the {case.role(role_id).name} against "
            f"{case.other_role(role_id).name}. Tip: the training plan on Prepare starts the "
            "next session in one click."
        )
        mode = st.segmented_control(
            "Counterpart",
            ["Recommended for me", "Choose the difficulty"],
            default="Recommended for me",
            key="setup_mode",
        )
        if mode == "Choose the difficulty":
            tier = st.select_slider(
                "Difficulty",
                options=list(TIERS),
                value=3,
                format_func=lambda t: f"{t} · {DIFFICULTY_NAMES[t]}",
            )
            chosen = ScenarioSpec(tier=tier, rationale=f"Chosen by you: difficulty {tier}.")
        else:
            chosen = preset or spec
            style.callout(chosen.rationale, "accent", title=difficulty(chosen.tier))
        opener = st.segmented_control(
            "Who speaks first?", ["I do", "They do"], default="I do", key="setup_opener"
        )
        if st.button("Start rehearsal", type="primary", icon=":material/play_arrow:"):
            start_rehearsal(p, case, role_id, chosen, counterpart_opens=opener == "They do")
            st.rerun()


def start_rehearsal(
    p: Participant, case: Case, role_id: str, spec: ScenarioSpec, *, counterpart_opens: bool
) -> Session:
    """Create and save a session against a freshly sampled counterpart for ``spec``."""
    seed = random.randrange(1_000_000)
    session = Session(
        participant_id=p.id,
        case_id=case.id,
        user_role_id=role_id,
        counterpart_role_id=case.other_role(role_id).id,
        counterpart_profile=counterpart_for(spec, random.Random(seed)),
        seed=seed,
        notes=spec.rationale,
    )
    st.session_state["session"] = session
    st.session_state["case"] = case
    st.session_state.pop("preset", None)
    st.session_state.pop("preset_role", None)
    SessionStore().save(session)
    if counterpart_opens or spec.focus == "error:3":
        _counterpart_reply(session, case)
    return session


def _counterpart_reply(session: Session, case: Case) -> None:
    with st.spinner(f"{case.role(session.counterpart_role_id).name} is responding…"):
        try:
            if (
                online()
                and session.counterpart_profile.focus == "rapport"
                and any(t.speaker == "user" and t.tags is None for t in session.turns)
            ):
                tag_session(session, case, llm("low"))
            reply = make_counterpart(session, case).respond(session)
            session.add_turn(reply, case)
        except LLMRefusal:
            st.error("The model declined to respond to that. Rephrase your message and retry.")
        except Exception as e:  # noqa: BLE001 - surface API errors without losing the session
            st.error(f"Counterpart error: {md(e)}. Use **Retry** below.")
    SessionStore().save(session)


def _user_move(session: Session, case: Case, turn: Turn) -> None:
    try:
        session.add_turn(turn, case)
    except ValueError as e:
        st.error(str(e))
        return
    SessionStore().save(session)
    if session.status == "active":
        _counterpart_reply(session, case)
    st.rerun()


def _composer(session: Session, case: Case) -> None:
    last = session.turns[-1] if session.turns else None
    if last is not None and last.speaker == "user":
        style.callout(
            "The counterpart hasn't replied yet. This usually means the AI call failed.", "warn"
        )
        if st.button("Retry", icon=":material/refresh:"):
            _counterpart_reply(session, case)
            st.rerun()
        return

    with st.form("move", clear_on_submit=True, border=True):
        text = st.text_area(
            "Your message",
            placeholder="Say what you'd say across the table…",
            key="move_text",
            height=110,
        )
        with st.expander("Make a formal offer", icon=":material/description:"):
            st.caption(
                "Pick a term for each issue you want to include, or type your own and press "
                "Enter. Leave the rest blank. Sent with your message as a formal offer."
            )
            if not online():
                st.caption(
                    "The offline counterpart only understands listed options; custom terms "
                    "need the AI counterpart."
                )
            cols = st.columns(2)
            picks = {}
            for n, issue in enumerate(case.issues):
                picks[issue.id] = cols[n % 2].selectbox(
                    issue.name,
                    [o.label for o in issue.options],
                    index=None,
                    placeholder="Leave open",
                    accept_new_options=True,
                    key=f"o_{issue.id}",
                )
        if st.form_submit_button("Send", type="primary", icon=":material/send:"):
            offer = Offer.from_labels(case, picks)
            if not (offer.terms or offer.custom_terms):
                offer = None
            if not text.strip() and offer is None:
                st.error("Write a message or include an offer.")
            else:
                _user_move(
                    session,
                    case,
                    Turn(index=len(session.turns), speaker="user", text=text.strip(), offer=offer),
                )

    theirs = session.latest_offer_from("counterpart")
    can_accept = theirs is not None and theirs.is_complete(case)
    a, b, c = st.columns([1.3, 1, 1], gap="small")
    with a:
        if st.button(
            "Accept their offer",
            icon=":material/check:",
            disabled=not can_accept,
            help=None if can_accept else "They haven't made a complete offer yet.",
            width="stretch",
        ):
            _user_move(
                session,
                case,
                Turn(index=len(session.turns), speaker="user", text="I accept.", accept=True),
            )
    with b, st.popover("Walk away", icon=":material/logout:", width="stretch"):
        st.markdown("End the negotiation without a deal? You'll get your walk-away value.")
        if st.button("Yes, walk away", type="primary", width="stretch"):
            _user_move(
                session,
                case,
                Turn(
                    index=len(session.turns),
                    speaker="user",
                    text="I'm going to walk away.",
                    walk_away=True,
                ),
            )
    with c, st.popover("More", icon=":material/more_horiz:", width="stretch"):
        st.caption("Stop without an outcome. The session won't count toward feedback.")
        if st.button("Abandon rehearsal", width="stretch"):
            session.status = "abandoned"
            SessionStore().save(session)
            st.session_state.pop("session", None)
            st.rerun()

    if case.uses_rubric:
        _commitments(session)


def _commitments(session: Session) -> None:
    with st.expander("Record next steps or conditional commitments", icon=":material/task_alt:"):
        st.caption(
            "Institutional negotiations often end with next steps rather than a final deal. "
            "Record what was agreed, who owns it, and what it depends on."
        )
        for c in session.commitments:
            style.html(
                f'<div class="nt-quote"><b>{style.esc(c.description)}</b><br>'
                f"{style.esc(COMMITMENT_STATUS.get(c.status, c.status))}"
                + (f" · {style.esc(c.responsible_party)}" if c.responsible_party else "")
                + "</div>"
            )
        with st.form("commitment"):
            description = st.text_area("Commitment or unresolved next step", height=80)
            left, right = st.columns(2)
            owner = left.text_input("Responsible party")
            deadline = right.text_input("Timing")
            approvals = left.text_input("Required approvals (comma separated)")
            contingency = right.text_input("If this cannot proceed")
            state = st.selectbox(
                "Commitment status",
                ["proposed", "agreed", "pending_approval", "unverified"],
                format_func=COMMITMENT_STATUS.get,
            )
            save = st.form_submit_button("Save next step")
        if save and description.strip():
            session.commitments.append(
                Commitment(
                    description=description,
                    responsible_party=owner,
                    deadline=deadline,
                    required_approvals=[x.strip() for x in approvals.split(",") if x.strip()],
                    contingency=contingency,
                    status=state,
                    source="participant record; delivery unverified",
                )
            )
            SessionStore().save(session)
            st.success("Next step recorded.")
        if st.button("Finish with recorded next steps", icon=":material/flag:"):
            session.status = "impasse"
            SessionStore().save(session)
            st.session_state["feedback_session"] = session.id
            go("feedback")


def page_rehearse() -> None:
    p = _require_participant()
    session: Session | None = st.session_state.get("session")
    case: Case | None = st.session_state.get("case")
    current, _ = active_scenario()
    if session is None or case is None or session.case_id != current.id:
        with st.container(key="page_narrow"):
            style.page_header(
                "Rehearse",
                "Negotiate as you would for real. Feedback comes after the session, never "
                "during it.",
                step=2,
            )
            _setup_rehearsal(p)
        return

    them = case.role(session.counterpart_role_id)
    tier = session.counterpart_profile.tier if session.counterpart_profile else None
    label, tone = STATUS[session.status]
    style.html(
        '<div class="nt-header" style="margin-bottom:.6rem">'
        f'<div class="nt-kicker">{style.steps_html(2)}</div>'
        f"<h1>{style.esc(case.title)}</h1>"
        f'<p class="nt-sub">You ({style.esc(case.role(session.user_role_id).name)}) and '
        f"{style.esc(them.name)}</p></div>"
    )
    style.badges([(label, tone), (difficulty(tier), "neutral")])
    left = session.max_user_turns - session.user_turns
    if session.status == "active":
        style.progress(
            f"{left} of {session.max_user_turns} moves left",
            left / max(1, session.max_user_turns),
        )

    chat, side = st.columns([1.7, 1], gap="large")
    with chat:
        if not session.turns:
            style.empty(
                "You speak first",
                "Introduce yourself, ask a question, or put an offer on the table.",
            )
        for turn in session.turns:
            render_turn(case, session, turn)
        if session.status == "active":
            _composer(session, case)
        else:
            _finished(session, case)
    with side:
        _side_panel(session, case)


def _side_panel(session: Session, case: Case) -> None:
    from negotrain.app import assistant_panel

    finished = session.status != "active"
    names = ["Offers", "Your sheet", "Notes", "Ask"]
    if finished:
        names.insert(2, "Their sheet")
    tabs = dict(zip(names, st.tabs(names), strict=True))
    with tabs["Offers"]:
        mine, theirs = session.latest_offer_from("user"), session.latest_offer_from("counterpart")
        style.html(
            offer_html(case, theirs, session.user_role_id, "Their latest offer")
            if theirs
            else style.empty_offer("They haven't made an offer yet.")
        )
        style.html(
            offer_html(case, mine, session.user_role_id, "Your latest offer")
            if mine
            else style.empty_offer("You haven't made an offer yet.")
        )
    with tabs["Your sheet"]:
        render_sheet(case, session.user_role_id, title="Your role")
    if finished:
        with tabs["Their sheet"]:
            render_sheet(case, session.counterpart_role_id, title="Their role")
    with tabs["Notes"]:
        prep = SessionStore().load_artifact(
            prep_key(session.participant_id, case.id, session.user_role_id), "prep", Prep
        )
        if prep is not None:
            style.html(style.list_card_html("Your checklist", prep.brief.checklist, checks=True))
        st.markdown("**Public information**")
        st.markdown(md(case.public_brief))
    with tabs["Ask"]:
        st.caption(
            "Ask about facts in your materials. During a rehearsal it won't suggest moves; "
            "coaching comes afterwards."
        )
        assistant_panel.render("Rehearse")


def _finished(session: Session, case: Case) -> None:
    st.space("small")
    with style.card("result", accent=True):
        if session.status == "agreed" and session.agreement:
            st.markdown("#### Deal reached")
            style.html(offer_html(case, session.agreement, session.user_role_id, "Final agreement"))
        elif case.uses_rubric:
            st.markdown("#### Session finished")
            st.caption("Review your skills and recorded next steps in the feedback.")
        else:
            st.markdown("#### No deal this time")
            st.caption("Your feedback shows what might have changed the outcome.")
        outcome_metrics(session, case)
        a, b = st.columns(2)
        if a.button("See my feedback", type="primary", width="stretch", icon=":material/insights:"):
            st.session_state["feedback_session"] = session.id
            go("feedback")
        if b.button("Practise again", width="stretch", icon=":material/replay:"):
            st.session_state.pop("session", None)
            st.rerun()


# --------------------------------------------------------------------------- feedback


def page_feedback() -> None:
    style.page_header(
        "Feedback",
        "How the rehearsal went, the moments that mattered, and what to practise next.",
        step=3,
    )
    p = _require_participant()
    store = SessionStore()
    lib = library()
    done = [
        s
        for s in reversed(store.for_participant(p.id))
        if s.kind == "rehearsal" and s.status in ("agreed", "impasse") and s.case_id in lib
    ]
    if not done:
        style.empty(
            "No finished rehearsals yet",
            "Finish a rehearsal (reach a deal, walk away, or record next steps) and your "
            "feedback appears here.",
        )
        return
    wanted = st.session_state.get("feedback_session")
    ids = [s.id for s in done]
    by_id = {s.id: s for s in done}
    sid = st.selectbox(
        "Rehearsal",
        ids,
        index=ids.index(wanted) if wanted in ids else 0,
        format_func=lambda i: f"{session_label(by_id[i])} · {lib[by_id[i].case_id][0].title}",
    )
    session = by_id[sid]
    st.session_state["assistant_feedback_session"] = sid
    case = lib[session.case_id][0]
    outcome_metrics(session, case)
    if case.uses_rubric:
        from negotrain.app.rubric_views import render_feedback

        render_feedback(session, case, store)
        return

    debrief = store.load_artifact(session.id, "feedback", Debrief)
    if debrief and debrief.counterfactuals and debrief.counterfactuals.reward != "surplus_share":
        style.callout("This debrief is from an older version. Generate it again.", "warn")
        debrief = None
    cap, k, n, use_llm = _feedback_settings(session, debrief)
    if debrief is None:
        style.empty(
            "Your debrief isn't written yet",
            "We replay the key moments of your rehearsal with different moves to see what "
            "would have changed, then write a coaching report.",
        )
    if st.button(
        "Generate feedback" if debrief is None else "Regenerate feedback",
        type="primary" if debrief is None else "secondary",
        icon=":material/auto_awesome:" if debrief is None else ":material/refresh:",
    ):
        debrief = _generate_debrief(session, case, store, cap, k, n, use_llm)

    if debrief is None:
        return
    tabs = st.tabs(["Coaching", "What-if replays", "Transcript", "Both sheets", "Data"])
    with tabs[0]:
        _render_report(debrief.report)
        _rate(debrief, session, store)
    with tabs[1]:
        _render_counterfactuals(debrief.counterfactuals, session, case)
    with tabs[2]:
        for turn in session.turns:
            render_turn(case, session, turn)
    with tabs[3]:
        a, b = st.columns(2, gap="large")
        with a:
            render_sheet(case, session.user_role_id, title="Your role")
        with b:
            render_sheet(case, session.counterpart_role_id, title="Their role")
        o = outcome_summary(session, case)
        style.callout(
            f"Best joint deal among the listed options: {o.max_joint_deal} "
            f"({o.max_joint:g} points for both sides together).",
            title="For reference",
        )
    with tabs[4]:
        f = extract_features(session, case)
        st.dataframe([{"feature": k, "value": v} for k, v in f.items()], hide_index=True)
        if session.counterpart_profile:
            st.caption(
                "Counterpart dials: "
                + ", ".join(f"{d}={getattr(session.counterpart_profile, d):.2f}" for d in DIALS)
            )
        if debrief.counterfactuals:
            st.caption(
                f"Feedback cost: {debrief.llm_calls} AI calls (about ${debrief.est_cost:.2f}); "
                f"replays took {debrief.counterfactuals.seconds:.0f}s."
            )


def _feedback_settings(session: Session, debrief: Debrief | None) -> tuple[int, int, int, bool]:
    if session.has_custom_terms:
        style.callout(
            "This rehearsal used custom terms. You'll get written coaching, but no what-if "
            "replays: custom terms have no defined point score."
        )
        return 3, 2, 4, False
    with st.expander("Feedback settings", icon=":material/tune:", expanded=False):
        on_plan = backend() == "claude-code"
        sim_choice = st.radio(
            "Replay alternatives against",
            [
                "Fast rule-based simulator (free)",
                "The same AI counterpart (slower, uses " + ("your plan)" if on_plan else "API)"),
            ],
            # On a plan, ~30 rollout calls eat into rate limits: opt in, don't default.
            index=0,
            disabled=not online(),
        )
        use_llm = online() and sim_choice.startswith("The same")
        c = st.columns(3)
        cap = c[0].number_input("Moments to analyse", 1, 5, 3)
        k = c[1].number_input("Alternatives each", 1, 4, 2)
        n = c[2].number_input("Replays per batch", 4, 5, 4)
        if use_llm:
            calls = estimate_calls(int(cap), int(k), int(n), session.max_user_turns) + 1
            if on_plan:
                st.caption(f"Up to about {calls} Claude Code calls; typically 2–5 minutes.")
            else:
                st.caption(
                    f"Up to about {calls} API calls (about ${calls * EST_COST_PER_CALL:.2f}); "
                    "typically 1–3 minutes."
                )
    return int(cap), int(k), int(n), use_llm


def _generate_debrief(
    session: Session, case: Case, store: SessionStore, cap: int, k: int, n: int, use_llm: bool
) -> Debrief:
    with st.spinner(
        "Writing your debrief…"
        if session.has_custom_terms
        else "Replaying key moments and writing your debrief…"
    ):
        calls_before = _total_calls()
        cost_before = _total_cost()
        if online():
            tag_session(session, case, llm("low"))
            store.save(session)
        counterfactuals = analyze_session(
            session,
            case,
            counterpart_factory(session, case, use_llm=use_llm, effort="low"),
            opponent="llm" if use_llm else "rule-based",
            cap=cap,
            k=k,
            n=n,
            max_workers=3 if backend() == "claude-code" else 8,
        )
        report = build_report(session, case, counterfactuals, llm() if online() else None)
        debrief = Debrief(
            counterfactuals=counterfactuals,
            report=report,
            llm_calls=_total_calls() - calls_before,
            est_cost=_total_cost() - cost_before,
        )
        store.save_artifact(session.id, "feedback", debrief)
    return debrief


def _rate(debrief: Debrief, session: Session, store: SessionStore) -> None:
    style.section("Was this feedback useful?", "Your rating helps us improve the coach.")
    rating = st.feedback("stars", key=f"rate_{session.id}")
    if rating is not None and rating + 1 != debrief.usefulness:
        debrief.usefulness = rating + 1
        store.save_artifact(session.id, "feedback", debrief)
        st.toast("Thanks for the rating.")
    elif debrief.usefulness and rating is None:
        style.muted(f"You rated this {debrief.usefulness} out of 5.")


def _total_calls() -> int:
    if not online():
        return 0
    kind, fp = backend(), _key_fingerprint()
    return sum(_llm(kind, e, fp).usage.calls for e in ("low", "medium", "high"))


def _total_cost() -> float:
    if not online():
        return 0.0
    kind, fp = backend(), _key_fingerprint()
    return sum(_llm(kind, e, fp).usage.cost() for e in ("low", "medium", "high"))


def _render_report(report: CoachingReport) -> None:
    style.lead(report.headline)
    style.card_grid(
        [
            style.list_card_html("What went well", report.strengths),
            style.list_card_html("What to work on", report.improvements),
        ]
    )
    if report.moments:
        style.section("Moments that mattered")
        for n, m in enumerate(report.moments, start=1):
            with style.card(f"moment-{n}"):
                happened = m.what_happened
                if happened.lower().startswith(m.title.lower()):
                    happened = ""  # template reports repeat the title; don't say it twice
                style.numbered(
                    n,
                    m.title,
                    happened,
                    extra=f'<div class="nt-badges">{style.badge_html(f"Turn {m.turn_index}")}'
                    "</div>",
                )
                style.html(
                    '<div style="margin-left:2.75rem">'
                    f'<div class="nt-callout accent"><b class="t">Next time</b>'
                    f"{style.esc(m.what_to_try)}</div>"
                    + (style.details_html("Why we think so", m.evidence) if m.evidence else "")
                    + "</div>"
                )
    style.callout(report.next_focus, "good", title="Focus for your next rehearsal")
    if report.source == "template":
        style.muted("Template feedback: written offline or while the AI was unavailable.")


def _render_counterfactuals(
    report: CounterfactualReport | None, session: Session, case: Case
) -> None:
    if report is not None and report.skipped_reason:
        style.callout(report.skipped_reason)
        return
    if report is None or not report.estimates:
        style.empty(
            "Nothing to replay",
            "There were no offers, acceptances, or walk-aways to try alternatives for.",
        )
        return
    opponent = "the same AI counterpart" if report.opponent == "llm" else "a rule-based simulator"
    style.callout(
        f"At each key moment we swapped your move for an alternative and played the rest of the "
        f"negotiation {report.n_rollouts} times against {opponent}. Outcomes are the share of "
        "the possible gains you'd have captured (0% = your walk-away, 100% = the best deal they "
        "could accept). Small samples, so treat these as rough guides.",
        title="How to read this",
    )
    for e in report.estimates:
        turn = session.turns[e.turn_index]
        with style.card(f"cf-{e.turn_index}"):
            delta = e.delta
            tag = ""
            if delta is not None:
                tone = "good" if delta > 0.005 else "bad" if delta < -0.005 else "neutral"
                tag = style.badge_html(f"Alternative: {delta * 100:+.0f} points of gains", tone)
            style.numbered(
                e.turn_index,
                e.description[:1].upper() + e.description[1:],
                f"You said: “{turn.text}”" if turn.text else "",
                extra=f'<div class="nt-badges">{tag}</div>' if tag else "",
            )
            rows = []
            for v in [e.actual, e.best_alternative]:
                if v is None:
                    continue
                a = v.action
                what = (
                    a.offer.describe(case)
                    if a.offer
                    else "Accept"
                    if a.accept
                    else "Walk away"
                    if a.walk_away
                    else f"“{a.text}”"
                )
                rows.append(
                    [
                        a.label + (" (uses hindsight)" if a.hindsight else ""),
                        what,
                        percent(v.mean),
                        f"{v.agreements} of {len(v.outcomes)}",
                    ]
                )
            style.table(["Option", "Move", "Average outcome", "Deals"], rows, numeric={2, 3})
            notes = []
            if e.delta_interval:
                lo, hi = e.delta_interval
                notes.append(
                    f"Plausible range for the difference: {lo * 100:+.0f} to {hi * 100:+.0f} points"
                )
            errors = sum(v.errors for v in e.values)
            if errors:
                notes.append(f"{errors} replay(s) failed and were skipped")
            if notes:
                style.muted(" · ".join(notes))


# --------------------------------------------------------------------------- progress


def page_profile() -> None:
    style.page_header(
        "Progress",
        "What you do well, what to work on, and what to practise next.",
    )
    p = _require_participant()
    hist = history(p.id)
    prof = current_profile(p.id, hist)
    current, _ = active_scenario()
    spec = next_scenario(prof, hist, [current.id])
    _recommended(spec)
    if prof.skills is not None:
        from negotrain.app.rubric_views import render_profile

        render_profile(prof, hist)
    else:
        _legacy_profile(prof)
    _history(hist)


def _recommended(spec: ScenarioSpec) -> None:
    lib = library()
    case_title = lib[spec.case_id][0].title if spec.case_id in lib else "Any case"
    with style.card("recommended", accent=True):
        left, right = st.columns([2.6, 1], vertical_alignment="center")
        with left:
            style.html(
                '<div class="nt-kicker">Recommended next rehearsal</div>'
                f'<div class="nt-row-title">{style.esc(case_title)} · '
                f"{style.esc(difficulty(spec.tier))}</div>"
                f'<p class="nt-row-text">{style.esc(spec.rationale)}</p>'
            )
        with right:
            if st.button(
                "Start rehearsal", key="recommended_start", type="primary", width="stretch"
            ):
                st.session_state["preset"] = spec
                st.session_state.pop("session", None)
                go("rehearse")


def _legacy_profile(prof) -> None:
    sessions = f"{prof.n_sessions} finished session{'s' if prof.n_sessions != 1 else ''}"
    habits, skills, unseen = [], [], []
    for key, posterior in prof.belief.components.items():
        chances = posterior.opportunities
        if not chances:
            unseen.append(prof.labels[key])
            continue
        lo, hi = posterior.interval()
        meta = (
            f"Based on {chances:g} chance{'s' if chances != 1 else ''} · likely between "
            f"{lo:.0%} and {hi:.0%}"
        )
        error = key.startswith("error:")
        item = style.meter(
            prof.labels[key],
            posterior.mean,
            lo,
            hi,
            meta,
            tone="warn" if error else "good",
            value_text=f"{posterior.mean:.0%} of the time",
        )
        (habits if error else skills).append((posterior.mean, item))
    style.section(
        "Habits to watch",
        "How often each mistake happens when you have the chance to make it. Lower is better. "
        f"From {sessions}; older sessions count for less.",
    )
    if habits:
        style.meters([m for _, m in sorted(habits, key=lambda x: -x[0])])
    else:
        style.empty("Nothing measured yet", "Finish a rehearsal to see your habits.")
    style.section(
        "Skills you're building",
        "How often you use a key fact of the case or build rapport when the moment arises. "
        "Higher is better.",
    )
    ranked = [m for _, m in sorted(skills, key=lambda x: x[0])]
    if ranked:
        style.meters(ranked[:6])
    else:
        style.empty(
            "No evidence yet",
            "These are measured from annotated messages, which needs the AI connection.",
        )
    if len(ranked) > 6:
        with st.expander(f"{len(ranked) - 6} more case facts and skills"):
            style.meters(ranked[6:])
    if unseen:
        with st.expander(f"Not seen yet ({len(unseen)})"):
            st.caption("No chance to show these has come up in your sessions so far.")
            for label in unseen:
                st.markdown(f"- {md(label)}")
    if prof.untagged_user_turns:
        style.muted(
            f"{prof.untagged_user_turns} of your messages haven't been annotated yet, so they "
            "aren't counted in the facts and rapport estimates."
        )
    with st.expander("Detailed estimates", icon=":material/table:"):
        rows = []
        for key, posterior in prof.belief.components.items():
            lo, hi = posterior.interval()
            rows.append(
                {
                    "Component": prof.labels[key],
                    "Probability": round(posterior.mean, 3),
                    "95% credible interval": f"{lo:.2f}–{hi:.2f}",
                    "Opportunities": posterior.opportunities,
                    "Meaning": "error rate" if key.startswith("error:") else "success rate",
                }
            )
        st.dataframe(rows, hide_index=True, width="stretch")


def _history(hist: list[tuple[Session, Case]]) -> None:
    if not hist:
        return
    style.section("History", "Every rehearsal and real negotiation you've logged.")
    rows = []
    for s, c in reversed(hist):
        if s.status == "active":
            continue  # unfinished or abandoned mid-way: nothing to report
        f = extract_features(s, c)
        rows.append(
            {
                "When": f"{s.created_at:%b %d, %H:%M}",
                "Type": "Real" if s.kind == "real" else "Rehearsal",
                "Case": c.title,
                "Difficulty": str(s.counterpart_profile.tier) if s.counterpart_profile else "—",
                "Result": STATUS[s.status][0],
                "Points": "—" if f["points"] is None else f"{f['points']:g}",
                "Share of gains": percent(f["surplus_share"]),
            }
        )
    st.dataframe(rows, hide_index=True, width="stretch")


# --------------------------------------------------------------------------- real negotiation


def page_real() -> None:
    style.page_header(
        "Real negotiation",
        "After the real thing (for example, the class simulation), log how it went. We compare "
        "it with your rehearsals of the same case to see what practice got right and wrong.",
    )
    p = _require_participant()
    case, role_id = active_scenario()
    style.badges([(case.title, "accent"), (f"You: {case.role(role_id).name}", "neutral")])
    with st.form("real", border=True):
        st.markdown("#### Outcome")
        status = st.radio(
            "Outcome",
            ["agreed", "impasse"],
            horizontal=True,
            format_func=lambda s: "We reached a deal" if s == "agreed" else "No deal",
            label_visibility="collapsed",
        )
        st.markdown("#### Agreed terms")
        st.caption("If there was a deal: choose a listed option or type the terms you agreed to.")
        picks = {}
        cols = st.columns(2)
        for n, issue in enumerate(case.issues):
            picks[issue.id] = cols[n % 2].selectbox(
                issue.name,
                [o.label for o in issue.options],
                index=None,
                placeholder="Choose or type the agreed term",
                key=f"real_{issue.id}",
                accept_new_options=True,
            )
        st.markdown("#### How did the other side behave?")
        observed = {}
        cols = st.columns(2)
        for n, (d, q) in enumerate(DIAL_QUESTIONS.items()):
            choice = cols[n % 2].select_slider(
                q, options=list(RATING_SCALE), value="Somewhat", key=f"real_{d}"
            )
            observed[d] = RATING_SCALE[choice]
        notes = st.text_area("Notes or transcript (optional; please leave out names)")
        if st.form_submit_button("Save real outcome", type="primary"):
            agreement = None
            if status == "agreed":
                agreement = Offer.from_labels(case, picks)
                if not agreement.is_complete(case):
                    st.error("Enter the agreed terms for every issue before saving a deal.")
                    return
            SessionStore().save(
                Session(
                    participant_id=p.id,
                    case_id=case.id,
                    user_role_id=role_id,
                    counterpart_role_id=case.other_role(role_id).id,
                    kind="real",
                    status=status,
                    agreement=agreement,
                    notes=notes,
                    observed_counterpart=observed,
                )
            )
            st.success("Saved.")

    _sim2real(p, case, role_id)


def _sim2real(p: Participant, case: Case, role_id: str) -> None:
    sessions = [
        s
        for s in SessionStore().for_participant(p.id)
        if s.case_id == case.id and s.user_role_id == role_id and s.status in ("agreed", "impasse")
    ]
    rehearsals = [s for s in sessions if s.kind == "rehearsal"]
    reals = [s for s in sessions if s.kind == "real"]
    if not reals:
        return
    st.subheader("Rehearsal vs real")
    real = reals[-1]
    real_pts = outcome_summary(real, case).points
    rows = [
        {
            "Session": f"Rehearsal · {s.created_at:%b %d, %H:%M}",
            "Difficulty": str(s.counterpart_profile.tier) if s.counterpart_profile else "—",
            "Result": STATUS[s.status][0],
            "Your points": outcome_summary(s, case).points,
        }
        for s in rehearsals
    ]
    rows.append(
        {
            "Session": "Real negotiation",
            "Difficulty": "—",
            "Result": STATUS[real.status][0],
            "Your points": real_pts,
        }
    )
    st.dataframe(rows, hide_index=True, width="stretch")
    if not rehearsals:
        style.muted("No rehearsals of this case and role yet to compare against.")
        return
    scored = [r["Your points"] for r in rows[:-1] if r["Your points"] is not None]
    if real_pts is not None and scored:
        mean_pts = sum(scored) / len(scored)
        share = surplus_share(case, role_id, real_pts) - surplus_share(case, role_id, mean_pts)
        style.stats(
            [
                ("Real outcome", f"{real_pts:g} points", "", ""),
                ("Rehearsal average", f"{mean_pts:.0f} points", "", ""),
                (
                    "Difference",
                    f"{real_pts - mean_pts:+.0f} points",
                    f"{share:+.0%} of your range",
                    "good" if real_pts >= mean_pts else "bad",
                ),
            ]
        )
    if real_pts is None or len(scored) != len(rehearsals):
        style.muted(
            "Agreements with custom terms have no point score and are left out of the numbers."
        )
    profiles: list[CounterpartProfile] = [
        s.counterpart_profile for s in rehearsals if s.counterpart_profile
    ]
    if profiles and real.observed_counterpart:
        style.section(
            "The other side: rehearsal vs real",
            "Large gaps show where rehearsal didn't match reality, for example a real "
            "counterpart that gave far less ground than the AI one.",
        )
        st.dataframe(
            [
                {
                    "Behaviour": DIAL_QUESTIONS[d],
                    "AI counterpart (average)": round(
                        sum(getattr(pr, d) for pr in profiles) / len(profiles), 2
                    ),
                    "Real counterpart (your rating)": real.observed_counterpart.get(d),
                }
                for d in DIALS
            ],
            hide_index=True,
            width="stretch",
        )


# --------------------------------------------------------------------------- case library


def page_cases() -> None:
    style.page_header(
        "Cases",
        "Every scenario available for rehearsal. Cases you import stay private to this machine.",
    )
    lib = library()
    facilitator = st.session_state.get("facilitator", False)
    for cid, (case, path) in sorted(lib.items(), key=lambda kv: kv[1][0].title.lower()):
        private = Path(path).parent.name == "private"
        with style.card(f"case-{cid}"):
            tags = (
                [(TYPE_LABELS.get(case.negotiation_type, ""), "accent")] if case.uses_rubric else []
            )
            tags.append(("Private" if private else "Sample", "neutral"))
            tags += [(f"{len(case.issues)} issues", "neutral")]
            st.markdown(f"#### {md(case.title)}")
            style.badges(tags)
            brief = case.public_brief.strip()
            st.markdown(md(brief[:260].rsplit(" ", 1)[0] + "…" if len(brief) > 260 else brief))
            st.caption(
                "Roles: "
                + ", ".join(r.name + (" (estimated)" if r.inferred else "") for r in case.roles)
            )
            with st.expander("Issues and options"):
                for issue in case.issues:
                    st.markdown(
                        md(f"- **{issue.name}**: " + ", ".join(o.label for o in issue.options))
                    )
                if case.source:
                    st.caption(md(case.source))
                if facilitator:
                    st.json(case.model_dump(), expanded=False)

    style.section(
        "Add a case",
        "Imported cases are saved privately. Check role visibility, constraints, and any "
        "scoring tables before using a case in a study.",
    )
    paste, upload = st.tabs(["Paste case text (uses Claude)", "Upload JSON"])
    with paste:
        if not online():
            style.callout("Parsing needs Claude: choose Claude Code or an API key in Settings.")
        with st.form("parse"):
            public = st.text_area("Public / general information", height=150)
            c1, c2 = st.columns(2)
            name1 = c1.text_input("Role 1 name", "Buyer")
            sheet1 = c1.text_area("Role 1 confidential sheet", height=200)
            name2 = c2.text_input("Role 2 name", "Seller")
            sheet2 = c2.text_area(
                "Role 2 confidential sheet (leave empty if you don't have it)", height=200
            )
            infer = st.checkbox("Estimate the missing sheet if only one is given", value=True)
            submitted = st.form_submit_button("Parse case", type="primary", disabled=not online())
        if submitted:
            roles = {name1: sheet1} | ({name2: sheet2} if sheet2.strip() else {})
            if not public.strip() or not sheet1.strip():
                st.error("Need the public information and at least one confidential sheet.")
            else:
                with st.spinner("Parsing (this can take a minute)…"):
                    try:
                        parsed = parse_case(
                            public,
                            roles,
                            llm("medium"),
                            infer_missing=infer,
                            source="Imported via the app.",
                        )
                        st.session_state["parsed_case"] = parsed
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Parsing failed: {md(e)}")
        parsed: Case | None = st.session_state.get("parsed_case")
        if parsed is not None:
            st.success(f"Parsed **{md(parsed.title)}** with {len(parsed.issues)} issues.")
            for issue in parsed.issues:
                st.markdown(md(f"- **{issue.name}**: " + ", ".join(o.label for o in issue.options)))
            st.caption(md(parsed.source))
            show = st.checkbox(
                "Show full JSON for review (reveals both confidential sheets, including any "
                "estimated one: spoils the rehearsal for that role)"
            )
            text = parsed.model_dump_json(indent=2)
            edited = st.text_area("Case JSON", text, height=400) if show else text
            if st.button("Save case"):
                try:
                    case = Case.model_validate_json(edited)
                    path = save_private_case(case)
                    st.session_state.pop("parsed_case", None)
                    st.success(f"Saved to {path}. It's now available in Rehearse.")
                except ValueError as e:
                    st.error(f"Invalid case: {e}")
    with upload:
        file = st.file_uploader("Case JSON", type="json")
        if file is not None and st.button("Validate and save"):
            try:
                case = Case.model_validate_json(file.getvalue())
                st.success(f"Saved to {save_private_case(case)}.")
            except ValueError as e:
                st.error(f"Invalid case: {e}")
