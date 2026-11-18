"""Visual layer: design tokens, injected CSS, and small HTML components.

Colors, fonts, and radii for Streamlit's own widgets live in .streamlit/config.toml. This
module styles everything the theme can't reach and provides the page vocabulary (headers,
sections, stat rows, callouts, offer cards, chat bubbles, skill meters). The look is calm
and editorial: warm off-white surfaces, near-black text, one deep-green accent, and no
decorative gradients or emoji, so long case material stays readable.

Every dynamic string is HTML-escaped here, so callers pass plain text. For prose rendered
through st.markdown, use ``md`` instead: a pair of "$" would otherwise render as LaTeX.
"""

from __future__ import annotations

import re
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"

# Tones shared by badges, callouts, stats and meters.
TONES = ("neutral", "accent", "good", "warn", "bad")


def md(text: object) -> str:
    """Escape text for st.markdown/st.write: a pair of "$" would otherwise render as LaTeX
    (case materials and chat are full of dollar amounts)."""
    return str(text).replace("$", "\\$")


def esc(text: object) -> str:
    """HTML-escape text content. Quotes stay literal: they are never placed in attributes,
    and keeping them readable means rendered text matches the source (tests rely on it)."""
    return escape(str(text), quote=False)


def paragraphs(text: str) -> str:
    """Plain text to escaped <p> blocks, keeping the author's paragraph breaks."""
    blocks = [b.strip() for b in str(text).replace("\r\n", "\n").split("\n\n") if b.strip()]
    return "".join("<p>" + esc(b).replace("\n", "<br>") + "</p>" for b in blocks)


@lru_cache(maxsize=1)
def _css() -> str:
    return "<style>\n" + (ASSETS / "style.css").read_text(encoding="utf-8") + "</style>"


def inject() -> None:
    st.markdown(_css(), unsafe_allow_html=True)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def _tone(tone: str) -> str:
    return tone if tone in TONES else "neutral"


# --------------------------------------------------------------------------- page structure


def steps_html(current: int) -> str:
    """The practice loop as three small pills; ``current`` is 1, 2 or 3 (0 for none)."""
    names = ("Prepare", "Rehearse", "Feedback")
    parts = [
        f'<span class="{"on" if n == current else ""}">{n} · {name}</span>'
        for n, name in enumerate(names, start=1)
    ]
    return '<span class="nt-steps">' + "<i></i>".join(parts) + "</span>"


def page_header(title: str, subtitle: str = "", *, kicker: str = "", step: int = 0) -> None:
    top = ""
    if kicker or step:
        top = (
            '<div class="nt-kicker">'
            + (steps_html(step) if step else "")
            + (esc(kicker) if kicker else "")
            + "</div>"
        )
    sub = f'<p class="nt-sub">{esc(subtitle)}</p>' if subtitle else ""
    html(f'<div class="nt-header">{top}<h1>{esc(title)}</h1>{sub}</div>')


def section(title: str, subtitle: str = "") -> None:
    sub = f"<p>{esc(subtitle)}</p>" if subtitle else ""
    html(f'<div class="nt-section"><h2>{esc(title)}</h2>{sub}</div>')


def lead(text: str) -> None:
    html(f'<div class="nt-lead">{esc(text)}</div>')


def muted(text: str) -> None:
    html(f'<p class="nt-muted">{esc(text)}</p>')


def card(name: str, *, accent: bool = False, border: bool = False):
    """A white panel around native widgets. ``name`` must be unique on the page."""
    return st.container(key=f"card-{'accent-' if accent else ''}{name}", border=border)


# --------------------------------------------------------------------------- small pieces


def badge_html(text: str, tone: str = "neutral", *, dot: bool = False) -> str:
    d = '<span class="nt-dot"></span>' if dot else ""
    return f'<span class="nt-badge {_tone(tone)}">{d}{esc(text)}</span>'


def badges(items: list[tuple[str, str]]) -> None:
    """Inline pills: (text, tone)."""
    html('<div class="nt-badges">' + "".join(badge_html(t, tone) for t, tone in items) + "</div>")


def callout(text: str, tone: str = "neutral", *, title: str = "") -> None:
    t = f'<b class="t">{esc(title)}</b>' if title else ""
    html(f'<div class="nt-callout {_tone(tone)}">{t}{esc(text)}</div>')


def stats(items: list[tuple[str, str, str, str]]) -> None:
    """Stat tiles: (label, value, note, tone of the note)."""
    cells = "".join(
        f'<div class="nt-stat"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div>'
        + (f'<div class="n {_tone(tone)}">{esc(note)}</div>' if note else "")
        + "</div>"
        for label, value, note, tone in items
    )
    html(f'<div class="nt-stats">{cells}</div>')


# " - " between words marks an inline sub-list in model-written items ("Stakes: - A. - B.").
_INLINE_BULLET = re.compile(r"\s+-\s+(?=\S)")


def split_item(item: str) -> tuple[str, list[str]]:
    """Split "Heading: - first - second" into ("Heading:", ["first", "second"]).

    Briefs written by the model sometimes pack a whole list into one string; showing it
    as nested bullets is far easier to read. A single spaced dash is treated as prose.
    """
    parts = [p.strip() for p in _INLINE_BULLET.split(str(item)) if p.strip()]
    if len(parts) < 3 and not (len(parts) == 2 and parts[0].endswith(":")):
        return str(item), []
    return parts[0], parts[1:]


def _li(item: str) -> str:
    head, subs = split_item(item)
    if not subs:
        return f"<li>{esc(head)}</li>"
    return f"<li>{esc(head)}<ul>" + "".join(f"<li>{esc(s)}</li>" for s in subs) + "</ul></li>"


def list_card_html(title: str, items: list[str], *, checks: bool = False, tone: str = "") -> str:
    if items:
        body = (
            f'<ul class="{"nt-checks" if checks else ""}">'
            + "".join(_li(i) for i in items)
            + "</ul>"
        )
    else:
        body = '<p class="nt-muted">Nothing noted.</p>'
    return f'<div class="nt-card {esc(tone)}"><h3>{esc(title)}</h3>{body}</div>'


def is_long(lists: list[list[str]], limit: int = 110) -> bool:
    """True when list items are long enough that side-by-side cards would be cramped."""
    items = [str(i) for group in lists for i in group]
    return bool(items) and sum(len(i) for i in items) / len(items) > limit


def card_grid(cards_html: list[str], *, single: bool = False) -> None:
    html(f'<div class="nt-grid{" one" if single else ""}">' + "".join(cards_html) + "</div>")


def text_card(title: str, text: str, *, tone: str = "") -> None:
    html(f'<div class="nt-card {esc(tone)}"><h3>{esc(title)}</h3>{paragraphs(text)}</div>')


def empty(title: str, text: str = "") -> None:
    html(f'<div class="nt-empty"><b>{esc(title)}</b><span>{esc(text)}</span></div>')


def how_it_works(items: list[tuple[str, str]]) -> None:
    html(
        '<div class="nt-howto">'
        + "".join(
            f'<div><div class="nt-num">{n}</div>'
            f"<div><b>{esc(t)}</b><span>{esc(d)}</span></div></div>"
            for n, (t, d) in enumerate(items, start=1)
        )
        + "</div>"
    )


def numbered(n: int | str, title: str, text: str = "", *, state: str = "", extra: str = "") -> None:
    """A row with a number disc; state is '', 'on' (current) or 'done'."""
    body = f'<p class="nt-row-text">{esc(text)}</p>' if text else ""
    disc = "✓" if state == "done" else esc(n)
    html(
        f'<div class="nt-row"><div class="nt-num {esc(state)}">{disc}</div><div>'
        f'<div class="nt-row-title">{esc(title)}</div>{extra}{body}</div></div>'
    )


def progress(label: str, fraction: float) -> None:
    pct = max(0.0, min(1.0, fraction)) * 100
    html(
        f'<div class="nt-progress"><span>{esc(label)}</span>'
        f'<div class="nt-track"><div style="width:{pct:.0f}%"></div></div></div>'
    )


def details_html(summary: str, body: str) -> str:
    return (
        f'<details class="nt-more"><summary>{esc(summary)}</summary>'
        f"<div>{esc(body)}</div></details>"
    )


# --------------------------------------------------------------------------- domain pieces


def priorities(rows: list[tuple[int, str, str, str, float, float]]) -> None:
    """Issue priorities: (rank, issue, best option, worst option, points at stake, share)."""
    out = []
    for rank, name, best, worst, spread, share in rows:
        out.append(
            f'<div class="nt-prio"><div class="r">{rank}</div><div class="name">{esc(name)}</div>'
            f'<div class="bar">{spread:g} pts at stake<div class="nt-track">'
            f'<div style="width:{max(0.0, min(1.0, share)) * 100:.0f}%"></div></div></div>'
            f'<div class="det">Best for you: {esc(best)} · Worst: {esc(worst)}</div></div>'
        )
    html('<div class="nt-card">' + "".join(out) + "</div>")


def offer_card(
    title: str, rows: list[tuple[str, str]], note: str = "", *, accent: bool = False
) -> str:
    """HTML for a structured offer: a header line and one row per issue."""
    body = "".join(f"<tr><td>{esc(issue)}</td><td>{esc(term)}</td></tr>" for issue, term in rows)
    w = f'<span class="w">{esc(note)}</span>' if note else ""
    return (
        f'<div class="nt-offer {"accent" if accent else ""}"><div class="nt-offer-head">'
        f"<span>{esc(title)}</span>{w}</div><table>{body}</table></div>"
    )


def empty_offer(text: str) -> str:
    return f'<div class="nt-offer empty">{esc(text)}</div>'


def points_table(rows: list[tuple[str, list[tuple[str, float]]]], walk_away: float) -> None:
    """A role's point table: every option of every issue, best option highlighted."""
    body = []
    for name, options in rows:
        top = max((pts for _, pts in options), default=0)
        for n, (label, pts) in enumerate(options):
            issue = f'<td class="issue">{esc(name)}</td>' if n == 0 else "<td></td>"
            best = ' class="best"' if pts == top else ""
            body.append(f'<tr{best}>{issue}<td>{esc(label)}</td><td class="num">{pts:g}</td></tr>')
    html(
        '<div class="nt-pts"><table class="nt-table"><thead><tr><th>Issue</th><th>Option</th>'
        '<th style="text-align:right">Points</th></tr></thead><tbody>'
        + "".join(body)
        + "</tbody></table></div>"
    )
    badges([(f"Walk-away (no deal): {walk_away:g} points", "warn")])


def table(headers: list[str], rows: list[list[str]], numeric: set[int] | None = None) -> None:
    """A light read-only table for short lists (use st.dataframe for data people sort)."""
    numeric = numeric or set()
    head = "".join(
        f'<th style="text-align:{"right" if i in numeric else "left"}">{esc(h)}</th>'
        for i, h in enumerate(headers)
    )
    body = "".join(
        "<tr>"
        + "".join(
            f'<td class="{"num" if i in numeric else ""}">{esc(c)}</td>' for i, c in enumerate(r)
        )
        + "</tr>"
        for r in rows
    )
    html(f'<table class="nt-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>')


def bubble(name: str, meta: str, text: str, *, mine: bool, extra: str = "") -> None:
    """One chat message. ``extra`` is trusted HTML built by this module (offer, events)."""
    say = f'<div class="nt-say">{paragraphs(text)}</div>' if text else ""
    html(
        f'<div class="nt-msg {"me" if mine else ""}"><div class="nt-bubble">'
        f'<div class="nt-who">{esc(name)}<span>{esc(meta)}</span></div>{say}{extra}</div></div>'
    )


def event_html(text: str, tone: str) -> str:
    return f'<div class="nt-event {_tone(tone)}">{esc(text)}</div>'


def meter(
    label: str,
    value: float | None,
    lo: float,
    hi: float,
    meta: str,
    *,
    tone: str = "accent",
    value_text: str = "",
) -> str:
    """A 0-1 estimate with its uncertainty band, as HTML (stack several in one card)."""
    if value is None:
        bar = ""
        shown = value_text or "Not enough evidence"
    else:
        lo_p, hi_p = max(0.0, lo) * 100, min(1.0, hi) * 100
        bar = (
            f'<div class="band" style="left:{lo_p:.1f}%;width:{max(0.0, hi_p - lo_p):.1f}%"></div>'
            f'<div class="pt" style="left:{max(0.0, min(1.0, value)) * 100:.1f}%"></div>'
        )
        shown = value_text or f"{value:.0%}"
    return (
        f'<div class="nt-meter {_tone(tone)}"><div class="top">'
        f'<span class="lbl">{esc(label)}</span>'
        f'<span class="val">{esc(shown)}</span></div><div class="rail">{bar}</div>'
        f'<div class="meta">{esc(meta)}</div></div>'
    )


def meters(items: list[str]) -> None:
    html('<div class="nt-card">' + "".join(items) + "</div>")


# --------------------------------------------------------------------------- chrome


def brand() -> None:
    """Logo at the top of the sidebar (above the page navigation)."""
    st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "icon.svg"))


def scenario_card(title: str, role: str, kind: str = "") -> None:
    k = f'<div class="r">{esc(kind)}</div>' if kind else ""
    html(
        f'<div class="nt-scenario"><div class="k">Current scenario</div>'
        f'<div class="t">{esc(title)}</div><div class="r">You play: {esc(role)}</div>{k}</div>'
    )
