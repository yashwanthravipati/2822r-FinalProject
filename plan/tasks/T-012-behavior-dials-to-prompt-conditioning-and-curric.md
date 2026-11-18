---
id: T-012
title: Behavior dials to prompt conditioning, and curriculum tiers
status: todo
milestone: M1
workstream: counterpart
owner: unassigned
depends_on: []
---

## Goal
Each dial produces a distinct, recognizable behavior, and the five tiers form a sensible difficulty ladder.

## Context
profiles.py has tier presets, sample_profile() (domain randomization), and a first describe() that bands each dial into one instruction.

## Acceptance criteria
- [ ] Richer per-dial instructions, with examples for anchoring, disclosure, and bluffing
- [ ] Tier definitions agreed by the team
- [ ] Dials documented in docs/architecture.md

## Log

- 2026-11-18: Added six contextual focus instructions and conversational opportunities for rubric cases. Counterpart prompts project own-role sources, preserve authority, and omit invented numeric economics. Offline institutional counterpart is explicitly a placeholder. Scripted tests verify prompt isolation; empirical steering adherence remains pending.
