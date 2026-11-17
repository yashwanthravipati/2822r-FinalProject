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
- [x] Synthetic smoke and full five-rehearsal development complete within the development budget.
- [x] Final paired Sim3-to-Sim4 evaluation completes within the final budget.
- [x] Development results, costs, limitations, and reproduction instructions are logged.
- [x] Final results and uncertainty are logged after held-out assessment.
- [x] Implementation and completed development artifacts are committed and pushed to ckpt3.

## Log
- 2026-11-17: User authorized ckpt3 development and two separate $100 API caps; caching foundation pushed.

- 2026-11-17: Synthetic smoke completed: 18 episodes, $1.660015, 76.52% input cache reads. New methods did not beat reports for the one persona; no population conclusion. 165 offline tests pass. Class-material API transmission awaits explicit approval required by automatic review.

- 2026-11-17: Added analogical application and domain-neutral rules; full five-rehearsal synthetic development is running on two new personas. Sim4 locally frozen and all 729 numeric packages audited without API transmission. Final API content approval remains pending.

- 2026-11-17: V2 development completed: 54 episodes, $7.503585, 77.90% input cache reads. Mean gains: reports +0.09936, reflection +0.04167, application -0.04808 (n=2, no population inference). Cumulative development $9.163600; final allowance untouched. No API process remains active. Added per-run accounting and corrected future-run metadata. Final class-content approval still pending.

- 2026-11-17: Blocked audit confirmed the same unanswered external-payload approval across three consecutive goal turns. Remote ckpt3 matches completed development checkpoint 245ca8c; no evaluator process or held-out results exist. Remaining final evaluation requires explicit permission to send role-appropriate Sim3/Sim4 briefs to Anthropic. No additional spend; goal is incomplete.

- 2026-11-17: User explicitly approved case-content transmission and clarified the content is fictional. Resume the final eight-persona, five-rehearsal paired study under the separate $100 final cap; retain all three training methods and generic held-out reference. Case and method selection are frozen before held-out outcomes.

- 2026-11-17: Final study complete: all 336 episodes and 24 frozen memories independently verified; 3,712 completed API requests, $41.133781, zero unresolved charges. Held-out gains: reports +0.07500, reflection +0.08333, application +0.01823, generic +0.01406. Reflection-minus-reports +0.00833, pointwise 95% interval [-0.05522, 0.06616]; superiority is not established. Full results/limitations in logs/ckpt3-final-results.md. All execution criteria are satisfied; task-board closure awaits user acceptance or merge per repository policy.
