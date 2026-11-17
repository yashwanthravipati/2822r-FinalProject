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
  185 offline tests pass. Earlier code/numeric results pushed on ckpt3; final summary commit
  ef550f9 remains local because automatic review blocked publication. User edits preserved.
  Current goal API cost $121.775492; checkpoint-3 ledgers total $172.072873, no unresolved
  calls, original separate $100 caps intact. Research result ready for review, while the
  substantive reliable-improvement objective remains unmet. Status awaits user acceptance.
- 2026-11-17: User explicitly raised both cumulative caps to $110. Audited the change without
  releasing charges. Preregistered one arithmetic teach-back plus full-reports candidate,
  48 new development episodes and gated 63-episode Cedar follow-up. Related prior generic
  application/correction failure remains acknowledged. Case and implementation frozen before
  outcomes; detailed costs, exact source histories and advance rule in improvement log.

- 2026-11-17: Teach-back completed and failed the advance rule: −0.046354 versus reports,
  CI [-0.077444,-0.010173], n=8, 48 new episodes/96 reused controls. Cedar untouched.
  Cost $6.867630; cumulative checkpoint-3 $178.940503 under separate $110 caps, no
  unresolved requests. Extended docs/report.tex at user's request with every completed
  comparison, limitations and reconciled costs; PDF compiles. 187 offline tests pass.
  Reliable outcome superiority remains unestablished; report/results ready for review.

- 2026-11-17: Subsequent audit found missing LLM weakness definitions, a constraint-blind
  joint-efficiency reference, and malformed-case acceptance. Repaired all three; 195
  offline tests pass. Old results prominently corrected, old core preserved at 4613bb2.
  Fresh six-profile comprehension check passed 6/6; four fresh integration episodes
  completed, all R=0.230769 before/after, zero schedule violations. No efficacy claim.
  Audit smoke cost $0.483545, combined checkpoint-3 total $179.424048. Main-path audit
  and limits recorded in logs/ckpt3-system-audit.md; larger behavioral calibration remains.
- 2026-11-17: Before further paid calls, preregistered a 48-episode behavioral screen:
  two existing public development cases, six target weaknesses, .1/.9 target settings,
  two matched controller seeds. Other errors .3, awareness/rapport .5, no coaching or
  trait updates; target-focused rule-based exposure with no learner practice callout.
  Primary diagnostic is high-minus-low fraction of episodes exhibiting the target error;
  also report opportunity coverage and conditional rates (undefined with zero opportunities).
  Four pairs/error cannot establish calibration; all six positive directions are required
  to advance this screening stage. Sim4 and unused Cedar excluded. Source/cases/runner
  frozen in persona-calibration-v1/protocol.json before outcomes. Estimated 400 Sonnet calls
  x (6,000 input tokens at $2/M + 350 output at $10/M) = $6.20 before cache savings;
  actual lengths vary. Three workers, existing cumulative development cap $110 preserved
  ($17.658087 headroom), under the user's latest $150 development/evaluation authorization.
- 2026-11-17: Completed all 48 calibration episodes, independently verified. Primary
  high-low episode-incidence increased only for error:2; the six-control gate failed.
  Error:4 had zero opportunities, not a measurable zero error probability. All sessions
  agreed with zero below-walk-away, schedule or missing-tag failures. $1.968971/351 calls;
  audit plus smoke $2.452516, cumulative checkpoint-3 $181.393019. Source frozen at
  e8e0820; later validation-only fix closes extra point-table entries and blank IDs.
  All five public cases and 579 offer scores remain identical; 206 offline tests pass.
  Report extended with the failed behavioral screen; no coaching superiority claim.
- 2026-11-17: Preregistered persona-probes-v1 after the failed full-session screen.
  Compare unchanged definitions with one experimental concrete enactment instruction;
  six authored decision contexts, two levels, four independent API draws: 96 responses
  plus 16 issue-annotation calls. Other weakness settings zero to isolate controls.
  Each context has independently checked positive/negative legal action witnesses.
  Primary event incidence is per controlled decision; secondary detector rates retain
  missing opportunities. Gate for advancing: all six targets have >=3/4 high events
  and <=1/4 low events. This is diagnostic development, not coaching or human evidence.
  No Sim4/Cedar use; production actor unchanged. Expected 112 calls x (5,000 input at
  $2/M + 500 output at $10/M) = $1.68 before caching; three workers, current $15.689116
  development headroom and $110 cumulative cap retained, within the latest $150 approval.
- 2026-11-17: v1 completed 96 probes /112 requests for $0.283143. Definitions passed
  zero per-target gates; concrete enactment passed only error:2. Manual review of all
  16 issue-neglect responses confirmed explicit mentions, agreeing with the tagger.
  Found a diagnostic conflict: dominated offers can necessarily also be first concessions,
  so setting all non-target errors to zero can contradict the target. Retain v1; no
  promotion. Freeze v2 with all non-target frequencies omitted (unspecified), an explicit
  scope statement, otherwise identical contexts, levels, repeats and gates. Fresh 96
  responses +16 annotations; same $1.68 pre-cache estimate and existing ledger cap.
  A regression test demonstrates the overlapping detectors and verifies the v2 payload.
- 2026-11-17: v2 completed 96 probes /112 calls, $0.277633; definitions pass error:1
  only, concrete enactment passes none. High anchoring and low acceptance appear in 2/4
  concrete probes but miss the unchanged >=3/4 gate. Preregister v3: same isolated
  contexts and actor, adding a private categorical intent plus one-sentence observable
  effect before the formal move. Score actual actions, never self-reported intent.
  No forced actions, no probability updates, no coaching. Fresh 48 responses plus eight
  annotations, expected 56 x (5,000 input at $2/M + 500 output at $10/M) = $0.84 before
  caching. Same gate, three workers, existing cumulative development cap retained.
- 2026-11-17: v3 completed 48 probes/56 calls for $0.181308; error:1 and error:2 pass
  (0/4 low versus 4/4 high), other four miss the gate. User explicitly requested immediate
  evals. Freeze corrected-transfer-v1: four fixed learners, two per concession weakness,
  frequency .9 with non-target traits unspecified, concrete enactment plus private intent.
  Five Sim3 sessions at tiers 2,2,4,4,4 with ordinary post-session LLM reports, then paired
  Sim4 no-feedback versus five-report assessment at tier 3. Rule-based counterpart keeps
  formal economics fixed and limits latency. Twenty practice plus eight test episodes;
  no trait updates, Sim4 practice, Sim4 feedback or post-test tuning. Memories frozen
  before testing. Primary paired R difference with uncertainty, n=4; this is exploratory,
  not validation of all six controls or humans. Sim4 remains historically revisited.
  Estimate 260 Sonnet calls x (6,000 input at $2/M + 500 output at $10/M) plus 20 Opus
  debriefs x (12,000 input at $4/M +1,500 output at $20/M) = $5.98 before caching.
  Existing separate $110 ledgers retained: practice on dev, assessment on final; two
  practice workers and three assessment workers fit conservative request reservations.
