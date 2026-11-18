"""NegoTrain: the participant-facing rehearsal app.

    streamlit run src/negotrain/app/main.py

Runs locally for one person. The first screen asks for the case files; the other pages
unlock once a scenario (case + role) is chosen. Set ANTHROPIC_API_KEY in .env (or paste it
on the first screen) for Claude; without one, or with NEGOTRAIN_OFFLINE=1, the app runs on
the rule-based counterpart.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="NegoTrain",
    page_icon=str(Path(__file__).parent / "assets" / "icon.svg"),
    layout="wide",
)

from negotrain.app import assistant_panel, views  # noqa: E402

# Page key -> (navigation title, material icon, url path, name the assistant uses for context).
# The assistant's names are stable identifiers in negotrain.assistant; titles can change freely.
PAGE_SPECS = {
    "prepare": ("Prepare", ":material/menu_book:", "", "Prepare"),
    "rehearse": ("Rehearse", ":material/forum:", "rehearse", "Rehearse"),
    "feedback": ("Feedback", ":material/insights:", "feedback", "Feedback"),
    "profile": ("Progress", ":material/trending_up:", "profile", "My profile"),
    "real": ("Real negotiation", ":material/handshake:", "real", "Real negotiation"),
    "cases": ("Cases", ":material/folder_open:", "cases", "Case library"),
}
# Pages that lay out their own side panel (or don't need the assistant).
NO_RAIL = {"rehearse", "cases"}

views.sidebar()
views.PAGES.clear()
if views.active_scenario() is None:
    # Nothing is unlocked until there is a scenario: the setup step is the whole app.
    views.PAGES["setup"] = st.Page(
        views.page_setup, title="Set up", icon=":material/upload_file:", default=True
    )
    current_page = st.navigation([views.PAGES["setup"]], position="hidden")
    current_key = "setup"
else:
    for key, (title, icon, path, _) in PAGE_SPECS.items():
        page_fn = getattr(views, f"page_{key}")
        if key == "prepare":
            views.PAGES[key] = st.Page(page_fn, title=title, icon=icon, default=True)
        else:
            views.PAGES[key] = st.Page(page_fn, title=title, icon=icon, url_path=path)
    pages = views.PAGES
    current_page = st.navigation(
        {
            "Practice": [pages["prepare"], pages["rehearse"], pages["feedback"]],
            "Results": [pages["profile"], pages["real"]],
            "Library": [pages["cases"]],
        }
    )
    current_key = next(k for k, p in pages.items() if p.title == current_page.title)

show_rail = (
    current_key in PAGE_SPECS
    and current_key not in NO_RAIL
    and st.session_state.get("show_assistant", True)
)
if show_rail:
    main_column, rail_column = st.columns([2.35, 1], gap="large")
    with main_column, st.container(key="main_page"):
        current_page.run()
    with rail_column, st.container(key="assistant_rail"):
        assistant_panel.render(PAGE_SPECS[current_key][3])
elif current_key == "rehearse":
    with st.container(key="main_page"):
        current_page.run()
else:
    with st.container(key="page_narrow"):
        current_page.run()
