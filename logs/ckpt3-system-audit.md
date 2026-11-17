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

## Follow-up behavioral screen and validation closure

Completed a preregistered 48-episode screen after the timed initial audit: six targets,
two levels (.1/.9), two public development cases and two matched controller seeds.
Other errors .3; awareness/rapport .5; no feedback, trait updates or learner callout.
The tier-3 rule-based controller received target focus without coaching the learner.
Sim4 and Cedar were excluded. Four pairs per target and unseeded API sampling make
this descriptive screening, not a precision calibration study.

| Target | Low episodes with error / 4 | High / 4 | Low occurrences/opportunities | High |
|---|---:|---:|---:|---:|
| Conceding first | 4 | 4 | 4/14 | 5/14 |
| Unreciprocated concession | 3 | 4 | 5/14 | 7/16 |
| Anchoring | 0 | 0 | 0/4 | 0/4 |
| Accepting low | 0 | 0 | undefined (0 opportunities) | undefined (0 opportunities) |
| Ignoring an issue | 0 | 0 | 0/22 | 0/22 |
| Dominated offer | 2 | 2 | 4/27 | 3/27 |

The primary episode-incidence gate failed: only one control increased. Conditional
rates are secondary and opportunities are endogenous; zero opportunities are missing
evidence, not successful avoidance. This does not validate the six-dimensional
simulator. Do not resume efficacy claims based on presumed planted frequencies.

All 48 sessions agreed, zero below-walk-away outcomes, missing annotations or schedule
violations. Independent enumeration and transcript replay pass. Cost $1.968971,
351 requests; cache reads 86.5048% of input tokens. Both audit evaluations together:
411 requests, $2.452516. Cumulative checkpoint-3 $181.393019: development $94.310884,
final $87.082135; no unresolved requests, existing $110 caps unchanged. Updated cost
aggregation now includes both audit receipts without adding cumulative snapshots.

A further reproduced input defect allowed extra unlisted point entries at case load
and in standalone scoring. Session validation already rejected such offers. The fix
requires exact point-table coverage and nonblank IDs, and the scorer independently
checks listed options. Eight additional regression cases cover this; the complete
suite now passes 206 tests. The fix was developed separately while the live cohort
used the frozen core, then applied after its verification. All five public case
serializations and 579 recorded offer scores are unchanged across this validation
fix (`validation_reference.json` / `validation_recheck.json`). Live-core revision:
`e8e0820`; current strict calibration verification must use that historical core.

## Controlled diagnostics and corrected Sim4 evaluation

Three further diagnostics tested explicit enactment and private behavioral intent on
authored one-decision contexts. Each had checked legal positive/negative witnesses.
V1 (96 responses) exposed a design conflict: non-target zero settings can prohibit a
target error that necessarily overlaps another detector. V2 (96 responses) omitted
non-target frequencies. V3 (48 responses) additionally required a private intent and
one-sentence effect, kept outside the public move. All scored actual actions, not
self-reports. No variant passed all six controls. V3 passed the two concession
controls: 0/4 low and 4/4 high events for each. Total diagnostic cost $0.742084,
280 calls including annotations. Production actor behavior was not silently replaced.

After the user's explicit request to run evals immediately, a separate exploratory
two-profile comparison was frozen before Sim4 assessment (commit `3ebd2f4`). This does
not satisfy the original six-control gate. Four fixed learners, two per concession
profile, completed five Sim3 practices with LLM reports at tiers 2,2,4,4,4. The actor
used the tested concrete instructions/private intent with target .9, other tendencies
unspecified, and no trait updates. The economic counterpart was rule-based, with
templated dialogue. All 20 reports were LLM-generated and frozen before testing.
Sim4 had no practice, feedback or tuning in this run; historical reuse remains disclosed.

| Replicate | No feedback R | Five reports R | Difference |
|---|---:|---:|---:|
| Conceding first 1 | .6000 | .7500 | +.1500 |
| Conceding first 2 | .6000 | .7500 | +.1500 |
| Unreciprocated 1 | .0625 | .7500 | +.6875 |
| Unreciprocated 2 | .2375 | .8875 | +.6500 |
| Mean | .3750 | .784375 | +.409375 |

Bootstrap interval [.1500,.66875]; exact two-sided sign-flip p=.125. This is a positive
exploratory score result, not strong general efficacy evidence. The designated target
errors were absent from both Sim4 arms, and occurred only twice across practice, so
the study does not establish remediation of those weaknesses or full-session persona
calibration. All 28 episodes agreed with zero below-walk-away outcomes, schedule
violations or missing tags. Independent enumeration, replay and memory/source checks
pass in `corrected-transfer-v1/verification.json`.

This evaluation cost $2.439023 /217 calls. Total since audit approval: $5.633623.
Checkpoint-3 totals: development $96.924150, final $87.649976, combined $184.574126;
no unresolved requests in either ledger, both $110 cumulative caps unchanged.
The cost summary includes all new receipts and keeps historical uncertainty separate.
All 218 offline tests pass; the expanded report includes every diagnostic and result.

## Prospective Cedar confirmation

Protocol and implementation were frozen at `80e7bb7` before Cedar assessment. Its
original case-file hash matched and no prior Cedar outcomes were recorded. Eight
fresh replicates of the same two profiles completed 40 Sim3 practices, then 16 paired
Cedar assessments with no feedback versus five frozen ordinary reports. No test
feedback, tuning, trait updates or outcome-dependent stopping occurred. Method
invariance checks preserve the pilot actor and training implementation.

Mean R was **0.433510638 with reports versus 0.236702128 without**, paired gain
**0.196808511**; six positive pairs, two ties. The bootstrap 95% interval is
[0.095744681, 0.305851064]; exact two-sided sign-flip p=0.03125. This passes the
prospectively fixed positive-mean/p<=.05 criterion. It supports ordinary reports over
no feedback in this fixed two-profile simulator on one fresh case, not personalized
refinement over ordinary reports, human transfer, or six-control calibration.

Target errors did not improve: 3 events/16 opportunities without feedback versus
4/18 with reports; training had 15/80. Opportunities are endogenous, and these rates
do not validate the nominal .9 trait. Cedar is now assessed and cannot be reused as
an untouched confirmation case. All 56 episodes agreed, zero below-walk-away,
schedule or missing-annotation failures. Independent enumeration, replay and frozen
memory/source verification pass in `corrected-confirmation-v1/verification.json`.

Cost: $4.465473 across 392 calls (practice $3.801271; assessment $0.664202).
Since the latest audit authorization: $10.099096 of the authorized $150. Checkpoint-3
cumulative known costs: dev $100.725421, final $88.314178; no unresolved calls.
During practice, dev's cumulative cap rose from $110 to $115 under that newer joint
authorization to accommodate conservative reservations; final remains $110. All old
ledger entries were preserved, with the change recorded in `budget_allocation.json`.
Separate historical uncertain charges remain reserved upper bounds, not known costs.
The full offline suite passed 220 tests before assessment; the four focused inference
and cost tests also pass after cost aggregation was extended to include this run.

## Corrected personalization and selection against strong controls

`corrected-adaptive-memory-v1` reused only the eight corrected Sim3 histories, never
Sim4 or Cedar assessment data. Protocol/code were frozen at `dd19a8d`: reports,
reports plus generic advice, and reports plus an own-history personal plan. All five
reports remain exact; bundling prevents the five-entry actor limit from dropping one.
Own-sheet isolation and cited-user-turn existence are tested. These checks do not
certify the semantic correctness of every generated coaching statement.

Completed 48 development negotiations on Harbor/Maple, then 48 validation negotiations
on Cloudline/Beacon. The selection rule required a >=.03 two-case mean gain over
reports; ties prefer simpler memories. Choices were frozen at `4dd8b15` before
validation results: four personal, three generic, one reports. Cases are known
development cases, not untouched final holdouts. All eight remain stochastic replicates
of two profiles, with full-session trait calibration unresolved.

| Validation arm | Mean R |
|---|---:|
| Reports | .412259615 |
| Reports + generic | .479567308 |
| Reports + personal plan | .539663462 |
| Selected per user | .530048077 |

Primary selected-minus-reports +.117788462, CI [.051682692,.194711538], exact p=.015625.
Selected-minus-generic +.050480769, CI [-.040865385,.179086538], p=.625. **Joint advance
gate fails.** The personal-plan-only comparisons are secondary: +.127403846 vs reports
(p=.0546875) and +.060096154 vs generic (p=.421875). Do not substitute the best observed
arm for the primary criterion. Validation target counts: reports 6/42 opportunities,
generic 6/34, personal 0/24, selected 4/33; these are descriptive with endogenous
opportunity counts, not validation of the nominal .9 tendency or a human mechanism.

Two further limitations were caught and retained in public audit artifacts: generated
plans exceed their requested 100–160 words (171–199) and one explicitly retains past
issue names; three generic selections also create structural zero contrasts, leaving
at most five informative pairs and minimum exact two-sided p=.0625 against generic.
The original cohort/gate was retained; no sample expansion or one-sided substitution.
A regression test now checks attainable inference limits. A larger cohort alone cannot
repair a weak or negative intervention, and this run does not authorize advancing the
candidate under its failed gate.

All 96 agreements, scores and schedules independently verified; one development
reports-only agreement below walk-away was retained, no such validation failures,
zero schedule violations/missing annotations. Cost $8.675957 across 955 requests;
$18.775053 since the audit authorization. Cumulative checkpoint-3 dev $109.401378,
final $88.314178, no unresolved requests. Dev ceiling allocated $115->$125 within
the newer $150 joint allowance; final remains $110, all ledger history preserved.
The complete suite passes 224 offline tests; report and reconciled costs include
all outcomes and limitations. Superiority over both strong controls remains open.
