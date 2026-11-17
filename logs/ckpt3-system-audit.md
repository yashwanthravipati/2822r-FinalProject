# Correctness audit, 2026-11-17

The requested ten-minute audit started at 21:31:54 UTC. This is a focused review of
the main system paths plus regression and live integration tests, not a certification
that every UI, deployment, input, or behavioral-calibration issue has been eliminated.

## Confirmed defects repaired

1. **Undefined LLM weakness IDs.** The prompt now supplies the name, behavioral
   definition and unchanged numeric frequency for each of the six weaknesses. The
   omitted codebook existed in historical learner implementations. Earlier LLM
   results do not validate the intended weakness-conditioned population. Existing
   tests checked privacy/feedback inclusion but missed this semantic contract.
2. **Illegal efficiency reference.** `max_joint_offer` ignored both sides' hard
   constraints while being used as the achievable reference in efficiency and
   debriefs. It now selects only legal options and rejects an impossible issue.
   An independent exhaustive enumeration test verifies the corrected maximum.
   The primary normalized-surplus denominator already respected these constraints;
   this finding does not imply that its previously recorded scores were miscomputed.
3. **Malformed case acceptance.** Case validation now rejects non-finite point or
   reservation values, duplicate issue/option/role IDs, empty issues/options, and
   constraints referencing nonexistent issues/options. Seven stored case fixtures
   load successfully under the corrected validation.

## Broader paths reviewed

| Path | Checks and limits |
|---|---|
| Learner and evaluation | Named definitions reach the actual learner system prompt; fixed trait values; synthetic `.learn()` is guarded out of LLM training. |
| Role isolation and assistant | Own-sheet projection, source-document role filters, case/role matching and post-session reveal boundaries reviewed; regression suite passes. |
| Counterpart and sessions | Schedule-floor enforcement, legal listed offers, one formal action, acceptance of complete standing offers and terminal transitions reviewed. |
| Scoring | Exact feasible normalized-surplus bound reviewed; joint-efficiency constraint defect repaired and tested. |
| Feedback | Prefix-only continuation fitting, disjoint selection/scoring seeds, terminal rollout scores, hindsight labeling and post-session feedback reviewed. Scripted continuations are still not validated models of the LLM learner. |
| Profiling and curriculum | Opportunity counts, missing annotations, prior-preserving discount, case-specific calibration and focus filters reviewed. Conditional behavior calibration remains unestablished. |
| Persistence and memory | Durable turns, frozen protocol/history checks, completed-stage reuse and five-report retention reviewed. Old experiments must use their old core revision. |
| API and caching | Role-projected cache prefixes, breakpoint limits, explicit retries, usage settlement and conservative ledger reservations reviewed; no budget reset. |

The full offline suite passes **195 tests**, including eight new regression cases.
No claim of calibrated error frequencies follows from these tests.

## Fresh corrected evaluation

Preregistered in `logs/ckpt3-improvement.md` before calls. Public hiring case, unchanged
Sonnet 5.5 learner / Opus 5.5 coach and counterpart, low effort, existing gateway and
development ledger. No historical control reuse. Old core is preserved at commit
`4613bb2` and in `/tmp/negotrain-pre-fix-4613bb2.tar`.

- Six different strongest-weakness profiles: **6/6 identified the right ID and explained
  its behavioral meaning correctly**. Meanings were manually inspected. This checks
  comprehension, not that the model enacts a specified frequency.
- Two fixed learners each completed baseline, post-session debrief and fresh reassessment:
  **four complete negotiations**, all agreed, zero below-walk-away outcomes and zero
  schedule violations. No trait/weight updates were made.
- Each baseline and reassessment scored **R = 0.230769**. No improvement was observed;
  two learners on one case cannot establish effectiveness or behavioral calibration.
- **60 requests; $0.483545 ledger cost** ($0.483520 usage receipts). Development total
  $92.341913; final remains $87.082135; combined $179.424048. Existing $110 caps were
  sufficient and were not raised. No requests remain unresolved in these two ledgers.

Independent enumeration verifies every new terminal score and the frozen corrected
core hash in `results/ckpt3/audit-corrected-smoke-v1/verification.json`. A post-run
line-wrap lint fix in the runner preserves its executable AST; both source hashes and
the AST hash are recorded. Raw dialogue and debriefs remain private.

Next scientific requirement: test high-versus-low named propensities against realized
opportunity-conditioned behavior with fresh controls before another coaching-efficacy
study. The old data cannot substitute for corrected baseline histories.
