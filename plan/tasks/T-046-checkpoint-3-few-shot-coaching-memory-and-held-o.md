---
id: T-046
title: Checkpoint 3 few-shot coaching memory and held-out Sim4 evaluation
status: in-progress
milestone: M4
workstream: analysis  # cases | counterpart | feedback | profiling | app | study | analysis | infra
owner: codex
depends_on: []
---

## Goal
Build and evaluate personalized strategy memory over five rehearsals, then measure transfer
from Sim3 to the held-out Sim4 scenario under separate $100 development/final API caps.

## Context
`logs/ckpt3-method-design.md`, `logs/2026-11-17-ckpt3.md`, and the original
`docs/results/sim3_evaluation.md`. User authorized the new branch, budgets, and study scope.

## Acceptance criteria
- [x] Stable provider caching and accurate TTL accounting pass offline regressions.
- [x] Reflective memory and learner application check preserve persona and role visibility.
- [x] Disjoint training/assessment harness and source-visibility isolation pass offline tests.
- [x] Sim4 projection is prepared locally, audited and frozen before final training.
- [ ] Development smoke and final paired evaluation complete within each authorized budget.
- [ ] Numeric results, uncertainty, costs, limitations, and reproduction instructions are logged.
- [ ] Implementation and artifacts are committed and pushed to ckpt3.

## Log
- 2026-11-17: User authorized ckpt3 development and two separate $100 API caps; caching foundation pushed.

- 2026-11-17: Synthetic smoke completed: 18 episodes, $1.660015, 76.52% input cache reads. New methods did not beat reports for the one persona; no population conclusion. 165 offline tests pass. Class-material API transmission awaits explicit approval required by automatic review.

- 2026-11-17: Added analogical application and domain-neutral rules; full five-rehearsal synthetic development is running on two new personas. Sim4 locally frozen and all 729 numeric packages audited without API transmission. Final API content approval remains pending.
