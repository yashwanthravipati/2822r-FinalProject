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
- [x] Independently verify complete outcomes, paired uncertainty, cost, and failure rates.
- [x] Report all results, including negative comparisons, and practical limitations.

## Log
- 2026-11-17: Started under the user's continuing autonomous improvement authorization.
  Existing cumulative $100 development and $100 final caps remain in force. No reset.
- 2026-11-17: Completed v1 plus two ablations, 336 unique new assessment episodes; controls
  were reused with immutable hashes. Development $56.244189 cumulative. Mixed transfer
  outcomes; froze workbook-versus-reports confirmation on seven new personas/two fresh cases.
- 2026-11-17: First prospective workbook comparison essentially tied reports. Subsequent
  terminal-credit memory and exact own-value worksheet failed their development gates.
  An equal-session varied curriculum passed its preliminary mean-based gate but yielded
  only +0.004579 over reports on unused Beacon, 95% interval [-0.043956,+0.043956], n=7.
  All planned outcomes retained and independently audited; no reliable superiority claim.
  One development truncation recovered with the unchanged protocol; no final failures.
  185 offline tests pass. Code/numeric results pushed on ckpt3; user report edits preserved.
  Current goal API cost $121.775492; checkpoint-3 ledgers total $172.072873, no unresolved
  calls, original separate $100 caps intact. Research result ready for review, while the
  substantive reliable-improvement objective remains unmet. Status awaits user acceptance.
