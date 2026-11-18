# UI guide

How the Streamlit app looks and why, for anyone (or any agent) changing a page. The
redesign is T-048; the behaviour underneath is unchanged from T-014/T-045.

## Principles

- **Plain language first.** Users see "Difficulty 3 of 5 · Guarded realist", "share of the
  possible gains", "what-if replays". Research detail (rollout counts, intervals, raw
  features, dials, raw JSON) stays one click away in an expander or a "Data"/"Research" tab.
- **The user decides.** Suggestions are pre-selected, never imposed: the rehearsal setup
  shows difficulty and who speaks first, pre-set to the plan's suggestion, and Prepare's
  "Up next" card has a Customize button next to Start.
- **One primary action per screen.** Primary (green) buttons are for the next step: Start
  rehearsal, Send, Generate feedback, Save. Everything else is secondary or tertiary.
- **Readable prose.** Case text and briefs render through `st.markdown(style.md(...))` at
  16px with a ~760px measure. Long briefs are split into titled cards, not walls of text.
- **No decoration for its own sake.** No gradients, no emoji, one accent colour. Icons are
  Material Symbols (`:material/name:`) on buttons, tabs, expanders and the navigation.
- **Honest numbers.** Missing evidence is shown as missing ("Not seen yet", "Not
  assessed"), never as a flat prior or a zero.

## Tokens

The palette lives in two places that must agree: `.streamlit/config.toml` (Streamlit's own
widgets) and the CSS variables at the top of `src/negotrain/app/assets/style.css`.

| Token | Value | Use |
|---|---|---|
| background | `#FBFAF8` | page |
| surface | `#FFFFFF` | cards, inputs |
| subtle | `#F4F3EF` | sidebar, table headers, tracks |
| border | `#E6E4DE` | card and table rules |
| text / text-2 / text-3 | `#1C1B19` / `#55524C` / `#74706A` | body, secondary, captions (≥4.5:1 on white) |
| accent | `#1F5C4A` (tint `#EAF1ED`) | primary buttons, current step, your chat bubbles |
| good / warn / bad | `#2D6A47` / `#8A5300` / `#A3271F` | outcomes, constraint status, habits |

Type is Inter (400–700), base 15px (`baseFontSize`; Streamlit scales widgets from it), page
titles 1.6rem/650, section titles 1.08rem/650. The layout is deliberately dense: a 252px
sidebar and up to 1400px of content, so a laptop screen shows a whole step at once.

## Where things live

| File | What |
|---|---|
| `app/main.py` | Navigation (`PAGE_SPECS`: title, icon, URL, and the page name the assistant uses) and the layout rule below |
| `app/views.py` | Pages and app logic (backend, active scenario, rehearsal moves, debrief generation) |
| `app/rubric_views.py` | Skill feedback and skill profile for rubric (institutional/integrative) cases |
| `app/assistant_panel.py` | The assistant: a Streamlit fragment, so asking doesn't rerun the page |
| `app/style.py` | Page vocabulary: `page_header`, `section`, `lead`, `stats`, `callout`, `badges`, `card`, `card_grid`/`list_card_html`, `numbered`, `offer_card`, `points_table`, `bubble`, `meter`, `empty` |
| `app/assets/style.css` | All injected CSS (read once per process by `style.inject`) |

**Layout rule (main.py).** Prepare, Feedback, Progress and Real negotiation get a right-hand
assistant rail (users can hide it with "Show assistant" in the sidebar). Rehearse lays out
its own two columns (chat | Offers · Your sheet · Their sheet after the end · Notes · Ask),
so the assistant lives in its Ask tab there. Setup and Cases use a narrow reading column.

## Conventions

- Pass plain text to `style.*` helpers; they escape it. Use `style.md()` for anything going
  through `st.markdown`/`st.write`/`st.caption` (a pair of `$` would become LaTeX).
- Wrap native widgets that need a panel in `with style.card("unique-name"):` (adds
  `accent=True` for the one highlighted card on a page). Card keys must be unique per run.
- Keep the assistant's page names (`"Feedback"`, `"My profile"`, ...) in `PAGE_SPECS`; the
  assistant uses them to pick context. Display titles can change freely.
- Never render the counterpart's sheet before `session.status != "active"`; the "Their
  sheet" tab only exists after the session ends (tested in `tests/test_app.py`).
- **Dropdowns.** Streamlit's dropdown menu is exactly as wide as its box and its rows have a
  fixed height, so long options get cut off in narrow columns. Keep dropdowns with long
  option text full width (`views.issue_columns` decides for issue pickers), prefer a radio
  list for a handful of long choices (saved cases on setup), and keep option labels short
  (the Feedback picker shows date, difficulty and result only). `style.css` lets options
  wrap to two lines as a safety net, not a licence for half-width boxes.
- Model-written brief items sometimes pack a list into one string ("Stakes: - A. - B.");
  `style.list_card_html` splits those into nested bullets, and `style.is_long` switches the
  brief to one column when items are long.
- After editing `style.css`, restart the server (it is cached per process); after editing
  Python files, Streamlit's "run on save" or a restart picks them up.

## Checking a change

`pytest tests/test_app.py tests/test_assistant_panel.py` covers flows, labels and
information hiding. For looks, run the app offline against a scratch data folder
(`NEGOTRAIN_OFFLINE=1 NEGOTRAIN_CASES_DIR=... NEGOTRAIN_SESSIONS_DIR=...`) and check each
page at desktop width and at ~390px; nothing should scroll sideways.
