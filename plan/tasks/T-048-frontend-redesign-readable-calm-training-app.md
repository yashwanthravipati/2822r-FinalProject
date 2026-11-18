---
id: T-048
title: Frontend redesign: readable, calm training app
status: review          # todo | in-progress | review | blocked | done
milestone: M1
workstream: app  # cases | counterpart | feedback | profiling | app | study | analysis | infra
owner: yash
depends_on: [T-014]
---

## Goal
Rebuild the Streamlit app's presentation so a participant can read and use it without
help: a calm, legible design system and plain-language pages, with research detail one
click away. Behaviour, data, and guardrails stay as they are.

## Context
Requested by Yash on 2026-11-17 ("not readable to a human"; inspiration: polished training
products such as Sana). Stays on Streamlit (decision 0001). Built on `main` after the rubric
work (decision 0009 on main). Guide for future UI work: `docs/ui.md`.

## Acceptance criteria
- [x] New design system: warm neutral palette, one accent, Inter, no gradients or emoji
  (`.streamlit/config.toml`, `app/assets/style.css`, `app/style.py`, new logo)
- [x] Every page rebuilt: setup, Prepare (brief + training plan + skills tabs, next-up card),
  Rehearse (wide chat, offer tables, side panel with Offers/Your sheet/Notes/Ask), Feedback
  (outcome tiles, coaching, moments, what-if replays), rubric feedback (skill meters with
  quoted evidence, commitments and constraints as cards), Progress, Real negotiation, Cases
- [x] Plain-language labels (difficulty names, share of the possible gains); research detail
  in expanders/tabs; missing evidence shown as missing, not as 50%
- [x] Information hiding preserved and tested (their sheet only after the session ends)
- [x] Offline tests updated and extended; ruff clean
- [x] Checked in a browser offline at desktop and phone width (legacy and institutional cases)
- [ ] Tried live with the API (counterpart, brief, assessment) after the redesign
- [ ] Team review (Mahdi, Vincent)

## Log
- 2026-11-17: Rebuilt the frontend on branch t-048-frontend-redesign (from main 8320197).
  Same app logic and session/artifact formats; presentation rewritten. Changes users will
  notice: setup explains the three steps; Prepare opens on an "Up next" card that starts the
  next plan session (plan progress = finished rehearsals of this case and role); the offer
  builder is a collapsible "Make a formal offer" section (an offer is attached when any issue
  is filled; the old "Attach a formal offer" checkbox is gone); walk away and abandon sit in
  confirm popovers; the rubric report is saved automatically (no "Generate feedback" button
  for rubric cases); Real negotiation no longer pre-fills the first option for every issue;
  ratings use five stars. Assistant: page names passed to it are unchanged, so its context
  logic is untouched; it is a hideable rail on Prepare/Feedback/Progress/Real and an "Ask"
  tab on Rehearse. Tests: 169 passed offline (`tests/test_claude_code.py` needs
  CLAUDE_TMPDIR/CLAUDE_CONFIG_DIR unset when run inside Claude Code; fails the same way on
  main there, unrelated). No API calls were made. Open: live check with the API; team review.
