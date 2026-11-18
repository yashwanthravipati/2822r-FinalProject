"""Headless smoke tests of the Streamlit app in offline mode (rule-based counterpart)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from negotrain.cases import load_case
from negotrain.feedback import Debrief
from negotrain.sessions import SessionStore

MAIN = Path(__file__).resolve().parents[1] / "src" / "negotrain" / "app" / "main.py"
CASE = Path(__file__).resolve().parents[1] / "data" / "cases" / "cloudline_hiring.json"
TEXT_ELEMENTS = ("markdown", "caption", "info", "success", "error", "warning", "text", "json")


def page_script(name: str) -> None:
    from negotrain.app import views

    views.sidebar()
    getattr(views, name)()


def page(name: str) -> AppTest:
    return AppTest.from_function(page_script, args=(name,), default_timeout=30).run()


def visible_text(at: AppTest) -> str:
    return " ".join(str(e.value) for kind in TEXT_ELEMENTS for e in at.get(kind))


def button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    import shutil

    cases = tmp_path / "cases"
    cases.mkdir(exist_ok=True)
    shutil.copy(CASE, cases)
    monkeypatch.setenv("NEGOTRAIN_CASES_DIR", str(cases))
    monkeypatch.setenv("NEGOTRAIN_OFFLINE", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("NEGOTRAIN_SESSIONS_DIR", str(tmp_path / "sessions"))


@pytest.fixture
def scenario():
    """An active scenario: the candidate role in the committed sample case."""
    from negotrain.app.views import ActiveScenario

    SessionStore().save_artifact(
        "current", "state", ActiveScenario(case_id="cloudline_hiring", role_id="candidate")
    )


def test_app_opens_on_upload_and_unlocks_after_choosing_a_scenario():
    at = AppTest.from_file(str(MAIN), default_timeout=30).run()
    assert not at.exception
    assert "Practice your next negotiation" in visible_text(at)
    assert not [b for b in at.button if b.label == "Switch scenario"]  # nothing unlocked yet

    button(at, "Use this case").click().run()
    button(at, "Start training").click().run()
    assert not at.exception
    # Now on Prepare (the default page once a scenario is active), with the brief written.
    text = visible_text(at)
    assert "Prepare" in text and "Checklist" in text
    assert load_case(CASE).role("recruiter").confidential_brief not in text

    button(at, "Switch scenario").click().run()
    assert "Practice your next negotiation" in visible_text(at)


def test_rehearsal_flow_hides_counterpart_sheet_until_the_end(scenario):
    case = load_case(CASE)
    secret = case.role("recruiter").confidential_brief
    at = page("page_rehearse")
    assert not at.exception
    button(at, "Start rehearsal").click().run()
    assert not at.exception
    at.text_area(key="move_text").input("Hi! What matters most to you?")
    for issue_id, label in [
        ("salary", "$150,000"),
        ("bonus", "$20,000"),
        ("remote", "4 days remote"),
        ("start", "In 4 weeks"),
        ("vacation", "25 days"),
    ]:
        at.selectbox(key=f"o_{issue_id}").select(label)
    button(at, "Send").click().run()
    assert not at.exception
    session = at.session_state["session"]
    assert [t.speaker for t in session.turns] == ["user", "counterpart"]
    assert session.turns[1].offer is not None
    assert secret not in visible_text(at)

    button(at, "Accept their offer").click().run()
    assert not at.exception
    assert at.session_state["session"].status == "agreed"
    assert SessionStore().load(session.id).status == "agreed"
    assert secret in visible_text(at)  # revealed in the debrief


def test_feedback_profile_real_and_cases_pages(scenario):
    at = page("page_rehearse")
    button(at, "Start rehearsal").click().run()
    button(at, "Yes, walk away").click().run()
    assert at.session_state["session"].status == "impasse"

    fb = page("page_feedback")
    assert not fb.exception
    button(fb, "Generate feedback").click().run()
    assert not fb.exception
    sid = at.session_state["session"].id
    assert (Path(SessionStore().root) / "feedback" / f"{sid}.json").exists()

    for name in ("page_profile", "page_cases", "page_setup"):
        assert not page(name).exception, name

    real = page("page_real")
    next(r for r in real.radio if r.label == "Outcome").set_value("impasse")
    button(real, "Save real outcome").click().run()
    assert not real.exception
    assert any(s.kind == "real" for s in SessionStore().all())
    assert "Rehearsal vs real" in " ".join(str(h.value) for h in real.subheader)


def test_prepare_writes_brief_and_training_plan_starts_rehearsals(scenario):
    at = page("page_prepare")
    assert not at.exception
    text = visible_text(at)
    assert "Checklist" in text and "Training plan" in text
    case = load_case(CASE)
    assert case.role("recruiter").confidential_brief not in text
    button(at, "Start").click().run()  # first training step: warm-up, tier 2
    assert not at.exception
    session = at.session_state["session"]
    assert session.case_id == case.id and session.counterpart_profile.tier == 2


@pytest.mark.parametrize("bundled", [False, True], ids=["loose", "zip"])
def test_upload_builds_a_scenario(tmp_path, monkeypatch, bundled):
    import shutil

    from negotrain.app import views
    from negotrain.llm import ScriptedLLM
    from test_documents import make_zip
    from test_parser import parsed_from

    cases = tmp_path / "cases"
    cases.mkdir(exist_ok=True)
    shutil.copy(CASE, cases)
    monkeypatch.setenv("NEGOTRAIN_CASES_DIR", str(cases))
    uploaded = parsed_from(load_case(CASE)) | {"id": "uploaded_case", "title": "Uploaded"}
    uploaded["roles"][1]["inferred"] = True
    scripted = ScriptedLLM([uploaded])
    monkeypatch.setattr(views, "online", lambda: True)
    monkeypatch.setattr(views, "llm", lambda effort=None: scripted)
    monkeypatch.setattr(views, "_total_calls", lambda: 0)
    monkeypatch.setattr(views, "_total_cost", lambda: 0.0)

    at = page("page_setup")
    files = [
        ("general.txt", b"Public info about the hiring.", "text/plain"),
        ("candidate.md", b"My confidential sheet.", "text/markdown"),
        ("scan.pdf", b"not really a pdf", "application/pdf"),
    ]
    if bundled:
        files = [
            (
                "case.zip",
                make_zip([(f"case/{name}", data) for name, data, _ in files]),
                "application/zip",
            ),
            ("notes.txt", b"Extra instructions.", "text/plain"),
        ]
    at.file_uploader[0].set_value(files)
    at.run()
    button(at, "Build scenario").click().run()
    assert not at.exception
    assert (cases / "private" / "uploaded_case.json").exists()
    assert "general.txt" in scripted.calls[0][1][0]["content"]
    if bundled:
        prompt = scripted.calls[0][1][0]["content"]
        assert "case.zip/case/general.txt" in prompt
        assert "case.zip/case/candidate.md" in prompt
        assert "My confidential sheet." in prompt and "Extra instructions." in prompt
    assert any("scan.pdf" in str(w.value) for w in at.warning)  # unreadable file reported
    assert at.session_state["setup_case_id"] == "uploaded_case"
    # The uploaded sheet's role is preselected; the other side is marked as estimated.
    assert "estimated version" in visible_text(at)
    button(at, "Start training").click().run()
    assert views.active_scenario()[0].id == "uploaded_case"


def test_dollar_amounts_are_escaped_for_markdown():
    from negotrain.app.style import md

    assert md("$120,000 or $150,000") == "\\$120,000 or \\$150,000"


def submit_custom_terms(at, submit_label, values):
    """Send the browser's free-text widget payload; AppTest.select only supports old options."""
    button(at, submit_label).click()
    state = at._tree.get_widget_states()
    by_id = {w.id: w for w in state.widgets}
    for key, value in values.items():
        widget = at.selectbox(key=key)
        assert widget.proto.accept_new_options
        by_id[widget.id].string_value = value
    return at._run(state)


def test_custom_offer_can_be_sent_accepted_and_reviewed(scenario, monkeypatch):
    from negotrain.app import views
    from negotrain.counterpart import CounterpartAgent
    from negotrain.llm import ScriptedLLM
    from test_counterpart import move
    from test_custom_offers import CUSTOM

    scripted = ScriptedLLM([move(accept=True)])
    monkeypatch.setattr(
        views,
        "make_counterpart",
        lambda session, case: CounterpartAgent(
            case, session.counterpart_role_id, session.counterpart_profile, scripted
        ),
    )
    at = page("page_rehearse")
    button(at, "Start rehearsal").click().run()
    at.text_area(key="move_text").input("Could this arrangement work?")
    for key, label in {
        "salary": "$140,000",
        "bonus": "None",
        "start": "In 4 weeks",
        "vacation": "20 days",
    }.items():
        at.selectbox(key=f"o_{key}").select(label)
    submit_custom_terms(at, "Send", {"o_remote": CUSTOM})
    assert not at.exception
    session = at.session_state["session"]
    assert session.status == "agreed" and session.agreement.custom_terms == {"remote": CUSTOM}
    assert SessionStore().load(session.id).agreement == session.agreement
    assert CUSTOM in views.offer_html(load_case(CASE), session.agreement, "candidate")

    feedback = page("page_feedback")
    assert not feedback.exception
    button(feedback, "Generate feedback").click().run()
    assert not feedback.exception
    assert "no defined point score" in visible_text(feedback)
    assert not page("page_profile").exception


def test_real_negotiation_saves_custom_terms_without_numeric_comparison(scenario):
    from test_custom_offers import CUSTOM

    at = page("page_real")
    for key, label in {
        "salary": "$140,000",
        "bonus": "None",
        "start": "In 4 weeks",
        "vacation": "20 days",
    }.items():
        at.selectbox(key=f"real_{key}").select(label)
    submit_custom_terms(at, "Save real outcome", {"real_remote": CUSTOM})
    assert not at.exception
    saved = next(s for s in SessionStore().all() if s.kind == "real")
    assert saved.agreement.custom_terms == {"remote": CUSTOM}
    assert "Rehearsal vs real" in " ".join(str(h.value) for h in at.subheader)


def test_api_key_can_be_set_replaced_and_removed(monkeypatch):
    import os

    from negotrain.app import views

    good = {"sk-ant-good-1111", "sk-ant-good-2222"}
    monkeypatch.setattr(views, "check_api_key", lambda k: None if k in good else "rejected")

    at = page("page_setup")
    at.text_input(key="api_key_setup").input("sk-ant-good-1111").run()
    assert not at.exception
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-good-1111"
    assert "…1111" in visible_text(at)

    at.text_input(key="api_key_settings").input("sk-ant-bad").run()
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-good-1111"  # bad key not applied
    assert any("rejected" in str(e.value) for e in at.error)

    at.text_input(key="api_key_settings").input("sk-ant-good-2222").run()
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-good-2222"
    assert at.text_input(key="api_key_settings").value == ""  # field cleared after applying

    button(at, "Remove key").click().run()
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_default_backend_prefers_claude_code(monkeypatch):
    from negotrain.app.views import default_backend

    monkeypatch.delenv("NEGOTRAIN_OFFLINE")
    monkeypatch.setenv("NEGOTRAIN_CLAUDE_BIN", "/usr/local/bin/claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    assert default_backend() == "claude-code"  # preferred even when a key is present
    monkeypatch.setenv("NEGOTRAIN_BACKEND", "api")
    assert default_backend() == "api"
    monkeypatch.setenv("NEGOTRAIN_OFFLINE", "1")
    assert default_backend() == "offline"


def test_institutional_workflow_uses_scores_and_records_conditional_commitments(scenario):
    from negotrain.cases import save_private_case
    from negotrain.rubrics import enable_rubric

    case = enable_rubric(load_case(CASE), "institutional")
    save_private_case(case)
    prep = page("page_prepare")
    assert not prep.exception
    assert not any(m.label == "Walk-away value" for m in prep.metric)
    at = page("page_rehearse")
    button(at, "Start rehearsal").click().run()
    assert not at.exception
    at.text_area(key="move_text").input("What approvals do we need?")
    button(at, "Send").click().run()
    assert not at.exception
    assert "Offline practice" in visible_text(at)
    next(t for t in at.text_area if t.label == "Commitment or unresolved next step").input(
        "Seek board approval"
    )
    next(t for t in at.text_input if t.label == "Responsible party").input("Agency")
    next(t for t in at.selectbox if t.label == "Commitment status").select("pending_approval")
    button(at, "Save next step").click().run()
    assert not at.exception
    button(at, "Finish with recorded next steps").click().run()
    session = at.session_state["session"]
    assert session.commitments[0].status == "pending_approval"
    assert SessionStore().load(session.id).commitments[0].description == "Seek board approval"
    fb = page("page_feedback")
    assert not fb.exception
    assert button(fb, "Assess skills").disabled
    assert "needs a rubric assessment" in visible_text(fb)
    assert not page("page_profile").exception
    real = page("page_real")
    button(real, "Save real outcome").click().run()
    assert not real.exception


def test_rubric_assessment_button_updates_saved_profile_and_next_focus(scenario, monkeypatch):
    from negotrain.app import views
    from negotrain.cases import save_private_case
    from negotrain.counterpart.profiles import TIERS
    from negotrain.llm import ScriptedLLM
    from negotrain.rubrics import case_rubric, enable_rubric
    from negotrain.schemas import Session, Turn

    case = enable_rubric(load_case(CASE), "institutional")
    save_private_case(case)
    session = Session(
        participant_id=views.participant().id,
        case_id=case.id,
        user_role_id="candidate",
        counterpart_role_id="recruiter",
        counterpart_profile=TIERS[2],
        status="impasse",
        turns=[Turn(index=0, speaker="user", text="What approvals do we need?")],
    )
    SessionStore().save(session)
    scripted = ScriptedLLM(
        [
            {
                "observations": [
                    dict(
                        skill_id=skill.id,
                        start_turn=0,
                        response_turn=0,
                        opportunity="present",
                        score=0.25 if skill.id == "skill:leverage" else 0.9,
                        evidence=[dict(turn_index=0, quote=session.turns[0].text)],
                        rationale="Synthetic integration-test annotation.",
                        suggestion="Connect your contribution to a request.",
                    )
                    for skill in case_rubric(case)
                ]
            }
        ]
    )
    monkeypatch.setattr(views, "online", lambda: True)
    monkeypatch.setattr(views, "llm", lambda *args, **kwargs: scripted)
    fb = page("page_feedback")
    button(fb, "Assess skills").click().run()
    assert not fb.exception
    saved = SessionStore().load(session.id)
    assert len(scripted.calls) == 1
    assert len(saved.assessment.observations) == 6
    assert SessionStore().load_artifact(session.id, "feedback", Debrief) is not None
    prof = page("page_profile")
    assert not prof.exception
    assert "1 assessed session" in visible_text(prof)
    rows = prof.dataframe[0].value
    leverage = rows[rows["Skill"].str.contains("leverage", case=False)].iloc[0]
    assert leverage["Estimated effectiveness"] == pytest.approx(1.25 / 3)
    button(prof, "Start rehearsal").click().run()
    assert not prof.exception
    assert prof.session_state["preset"].focus == "skill:leverage"
    assert prof.session_state["preset"].tier == 2


def test_training_plan_advances_after_a_finished_rehearsal(scenario):
    from negotrain.app import views
    from negotrain.counterpart.profiles import TIERS
    from negotrain.schemas import Session

    at = page("page_prepare")
    assert "Warm-up" in visible_text(at)  # first step is up next
    SessionStore().save(
        Session(
            participant_id=views.participant().id,
            case_id="cloudline_hiring",
            user_role_id="candidate",
            counterpart_role_id="recruiter",
            counterpart_profile=TIERS[2],
            status="agreed",
        )
    )
    at = page("page_prepare")
    assert not at.exception
    next_up = next(m.value for m in at.markdown if "Up next in your training plan" in m.value)
    assert "Consolidate" in next_up and "Warm-up" not in next_up
    assert "Done" in visible_text(at)


def test_profile_does_not_show_estimates_without_evidence(scenario):
    at = page("page_profile")
    assert not at.exception
    assert any(e.label.startswith("Not seen yet") for e in at.expander)
    assert "50% of the time" not in visible_text(at)  # a flat prior is not a measurement


def test_rehearsal_layout_reveals_their_sheet_only_after_the_session(scenario):
    case = load_case(CASE)
    at = page("page_rehearse")
    button(at, "Start rehearsal").click().run()
    tabs = [t.label for t in at.tabs]
    assert "Their sheet" not in tabs and "Your sheet" in tabs
    button(at, "Yes, walk away").click().run()
    assert at.session_state["session"].status == "impasse"
    assert "Their sheet" in [t.label for t in at.tabs]
    assert case.role("recruiter").confidential_brief in visible_text(at)


def test_html_helpers_escape_markup_but_keep_quotes_readable():
    from negotrain.app import style

    assert style.esc('<b>it\'s "fine"</b>') == '&lt;b&gt;it\'s "fine"&lt;/b&gt;'
    assert style.paragraphs("One\n\nTwo <i>") == "<p>One</p><p>Two &lt;i&gt;</p>"
    card = style.offer_card("Their offer", [("Salary", "<$150k>")], "500 points to you")
    assert "&lt;$150k&gt;" in card and "500 points to you" in card


def test_feedback_shows_the_report_right_after_generating(scenario):
    at = page("page_rehearse")
    button(at, "Start rehearsal").click().run()
    button(at, "Yes, walk away").click().run()
    fb = page("page_feedback")
    assert "Your debrief isn't written yet" in visible_text(fb)
    button(fb, "Generate feedback").click().run()
    assert not fb.exception
    assert "Your debrief isn't written yet" not in visible_text(fb)  # no stale empty state
    assert not [b for b in fb.button if b.label == "Generate feedback"]
    assert "Regenerate feedback" in [b.label for b in fb.button]


def test_feedback_lists_only_rehearsals_of_the_current_scenario(scenario):
    from negotrain.app import views
    from negotrain.counterpart.profiles import TIERS
    from negotrain.schemas import Session

    def finished(role, other):
        s = Session(
            participant_id=views.participant().id,
            case_id="cloudline_hiring",
            user_role_id=role,
            counterpart_role_id=other,
            counterpart_profile=TIERS[2],
            status="impasse",
        )
        SessionStore().save(s)
        return s

    mine = finished("candidate", "recruiter")
    other_role = finished("recruiter", "candidate")
    fb = page("page_feedback")
    options = fb.selectbox[0].options
    assert len(options) == 1 and "Difficulty 2" in options[0]
    assert fb.session_state["assistant_feedback_session"] == mine.id != other_role.id


def test_long_option_labels_get_full_width_dropdowns():
    from negotrain.app.views import issue_columns

    case = load_case(CASE)
    assert issue_columns(case) == 2  # short labels such as "$150,000"
    case.issues[0].options[0].label = "RC-B nominations passed via GR; RC-A conducts its own review"
    assert issue_columns(case) == 1


def test_inline_sub_bullets_become_nested_lists():
    from negotrain.app import style

    head, subs = style.split_item("Issues by stake: - Selection: 30 points. - Data: 15.")
    assert head == "Issues by stake:" and subs == ["Selection: 30 points.", "Data: 15."]
    assert style.split_item("Hold firm on RC-A's role - it matters.") == (
        "Hold firm on RC-A's role - it matters.",
        [],
    )
    assert "<ul><li>Selection: 30 points.</li>" in style.list_card_html(
        "Key facts", ["Issues by stake: - Selection: 30 points. - Data: 15."]
    )


def test_choosing_a_difficulty_keeps_the_suggested_focus(scenario):
    at = page("page_rehearse")
    at.select_slider(key="setup_tier").set_value(4).run()
    button(at, "Start rehearsal").click().run()
    assert not at.exception
    profile = at.session_state["session"].counterpart_profile
    assert profile.tier == 4 and profile.focus is not None


def test_customize_opens_rehearsal_setup_without_starting(scenario):
    at = page("page_prepare")
    button(at, "Customize").click().run()
    assert not at.exception
    assert at.session_state["preset"].tier == 2  # the warm-up step, ready to adjust
    assert "session" not in at.session_state
    assert not SessionStore().all()
