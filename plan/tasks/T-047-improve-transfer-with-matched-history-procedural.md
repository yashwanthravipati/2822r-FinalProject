---
id: T-047
title: Improve transfer with matched-history procedural coaching
status: in-progress
milestone: M4
workstream: analysis  # cases | counterpart | feedback | profiling | app | study | analysis | infra
owner: codex
depends_on: []
---

## Goal
Improve simulated negotiation outcomes with an evidence-backed coaching memory, evaluated
against reports and generic instructions under identical practice histories.

## Context
T-046 found no clear transfer superiority and poorer same-case outcomes for compact cards.
See `logs/ckpt3-improvement.md` for the prospective design and cumulative budgets.
Sim4 has now been examined and is a revisited benchmark, not an untouched test set.

## Acceptance criteria
- [x] Implement matched-history consolidation and offline information-boundary tests.
- [x] Freeze fresh synthetic transfer cases before new development outcomes.
- [x] Compare candidates on development and a separate validation cohort.
- [x] Freeze the selected intervention before assessing fresh personas and cases.
- [ ] Independently verify complete outcomes, paired uncertainty, cost, and failure rates.
- [ ] Report all results, including negative comparisons, and practical limitations.

## Log
- 2026-11-17: Started under the user's continuing autonomous improvement authorization.
  Existing cumulative $100 development and $100 final caps remain in force. No reset.
- 2026-11-17: Completed v1 plus two ablations, 336 unique new assessment episodes; controls
  were reused with immutable hashes. Development $56.244189 cumulative. Mixed transfer
  outcomes; froze workbook-versus-reports confirmation on seven new personas/two fresh cases.
