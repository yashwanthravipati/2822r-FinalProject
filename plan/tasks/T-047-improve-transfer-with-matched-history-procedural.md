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
- [ ] Establish prospective superiority over both ordinary reports and generic advice
  with the corrected learner, retaining the unresolved calibration limits explicitly.

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
- 2026-11-17: Corrected transfer eval completed: 20 practice +8 Sim4 test episodes,
  all independently verified. Mean R .784375 with five reports vs .375 without,
  paired gain +.409375; all four positive, bootstrap CI [.15,.66875], exact sign-flip
  p=.125. Two profiles/four replicates are exploratory. Target errors were absent in
  both test arms, so the result does not prove weakness remediation or six-control
  calibration. All 28 agreed, zero below-walk-away, schedule or annotation failures.
  Cost $2.439023/217 requests; total since audit approval $5.633623. Cumulative dev
  $96.924150, final $87.649976, no unresolved calls. Report and cost summary updated;
  218 offline tests pass. Broad reliable-improvement objective still requires confirmation.
- 2026-11-17: Preregister corrected-confirmation-v1 after the positive Sim4 pilot:
  eight new simulation replicates (four per unchanged concession profile), five fresh
  Sim3 practices each, then paired no-feedback/five-report tests on previously unused
  Cedar as owner, tier 3. Same actor, reports, controller, models, effort and fixed traits.
  Forty practice +16 assessment episodes, no outcome-dependent stopping or case tuning.
  Primary confirmation rule: paired mean >0 and two-sided exact sign-flip p <= .05,
  with complete independently verified outcomes. Two-profile/six-control limits remain.
  Cedar file matches its original eff48d0a... manifest hash; no Cedar case_id appears
  in any stored checkpoint-3 session. New controller seeds are disjoint from the pilot.
  Estimate 400 Sonnet x (6,000 input at $2/M +500 output at $10/M) plus 40 Opus x
  (12,000 input at $4/M +1,500 output at $20/M) = $9.92 before cache savings. Based
  on the pilot, expected actual cost is about $4.88. Existing $110 caps preserved;
  dev headroom $13.075850, final $22.350024. Two practice /three test workers; gateway
  reservations may serialize Opus calls. Within the latest $150 audit/eval authorization.
- 2026-11-17: Financial allocation amendment during confirmation practice, before Cedar
  assessment: raised only the development cumulative cap from $110 to $115 under the
  user's newer $150 joint development/evaluation allowance. Full-context reservations
  had serialized calls despite low actual cost. Final remains $110; no charges or request
  records reset. Relative to pre-audit $178.940503, the combined $225 ceilings permit at
  most $46.059497 new spending, conservatively within $150. The ledger's authorized-limit
  audit and corrected-confirmation-v1/budget_allocation.json preserve the change and
  before/after balances. Scientific protocol, cohort and models remain unchanged.
- 2026-11-17: Completed and independently verified all 40 practice and 16 Cedar
  assessments. Mean R .433510638 with reports vs .236702128 without, paired gain
  +.196808511, bootstrap CI [.095744681,.305851064], exact two-sided sign-flip
  p=.03125: prespecified confirmation passes. Six positive pairs, two ties. All 56
  agreed; no below-walk-away, schedule or annotation failures. Target errors did not
  improve (3/16 opportunities control, 4/18 coached); full-session calibration and
  six-control/human claims remain unproven. Cedar is now used, not a future untouched
  holdout. This confirms ordinary reports vs no feedback in this simulator, not
  personalized refinement vs ordinary reports, so the broader task remains open.
  Cost $4.465473/392 calls; since audit approval $10.099096. Cumulative dev
  $100.725421, final $88.314178; no unresolved calls. Report and cost summary updated.
  Full offline suite passed 220 tests before assessment; focused inference/cost tests
  passed 4/4 afterward, with lint/format and task checks clean.
- 2026-11-17: Preregister corrected-adaptive-memory-v1 to address the actual strong
  baseline comparison. Reuse only the eight corrected learners' five Sim3 practices
  from corrected-confirmation-v1; no Cedar or Sim4 test data enters coaching or
  selection. Generate one short own-visible, evidence-cited plan per learner; retain
  all five reports. Three arms: reports, reports+generic advice, reports+personal plan.
  Eight replicates x two development cases (Harbor/Maple) x three arms =48 episodes.
  Choose each user's highest mean arm, requiring >=.03 over reports, with conservative
  ties (reports, generic, personalized). Freeze selection before 48 validation episodes
  on Cloudline/Beacon. Evaluate all three arms even if not selected; no stopping based
  on outcomes. Aggregate the two cases within each user before paired inference.
  Advance only if selected memory beats BOTH reports and generic with positive means
  and exact two-sided sign-flip p<=.05 for each. These are known development cases,
  not fresh final holdouts; two-profile calibration limits remain. Sonnet learner,
  Opus plan writer, low effort, fixed traits and rule-based economic controller.
  Estimate $10 including eight plans and 96 negotiations; development ledger has
  $14.274579 headroom under $115, final cap $110 unchanged, latest $150 joint new-work
  allowance retained. No new practice/API history regeneration. Tests cover own-sheet
  isolation, citation integrity, exact five-report retention and conservative selection.
- 2026-11-17: Before validation, audited all eight frozen generated plans: 171--199
  rendered words rather than requested 100--160, and one contains explicit training
  issue references. Recorded in plan_quality.json; do not claim strictly portable or
  length-matched output. Retain the actual frozen outputs without outcome-driven edits.
  Financial amendment: development cumulative ceiling $115->$125 under the latest
  $150 joint allowance, final stays $110. The $235 combined ceilings permit at most
  $56.059497 after the pre-audit known $178.940503. This maintains three conservative
  full-context reservations without altering charges, protocol or expected actual cost;
  budget_allocation.json and the ledger limit-change table preserve the decision.
- 2026-11-17: All 48 development outcomes complete; selection frozen at 4dd8b15 before
  validation results: four personalized, three generic, one reports. During validation,
  the inference audit exposed a design-power limit: generic selections create three
  exact zero differences, leaving at most five nonzero pairs against generic and a
  minimum attainable two-sided exact p=.0625. Thus the fixed p<=.05 advance gate is
  unattainable for this realized selection. Record selection_inference_limits.json,
  add a regression check, retain all fixed validation outcomes and the original gate.
  No post-outcome sample extension, one-sided substitution or success redefinition.
  Any later confirmation must plan a larger independent cohort for structural zeros;
  a larger sample alone cannot fix a weak or negative effect.
- 2026-11-17: All 96 outcomes independently verified. Validation means: reports
  .412259615, generic .479567308, personal plan .539663462, selected .530048077.
  Primary selected-minus-reports +.117788462, CI [.051682692,.194711538], p=.015625;
  selected-minus-generic +.050480769, CI [-.040865385,.179086538], p=.625. Joint
  advance gate FAILS; do not claim superiority over both controls or promote a fresh
  final test under this gate. Secondary all-personalized comparisons: +.127403846
  versus reports, exact p=.0546875; +.060096154 versus generic, p=.421875. Preserve
  distinction from the primary selector. Validation target counts: reports 6/42,
  generic 6/34, personal 0/24, selected 4/33; descriptive/endogenous opportunities.
  All 96 agreed; one development reports-only below-walk-away outcome retained;
  no validation below-walk-away, schedule violations or missing tags. Cost
  $8.675957/955 requests; since latest audit authorization $18.775053. Cumulative
  checkpoint-3 dev $109.401378 +final $88.314178, zero unresolved calls. 224 offline
  tests pass, lint/format/task checks clean. Report includes full positive and negative
  comparisons and planning defects. Reliable superiority over both strong controls
  remains unestablished; retain the broader goal rather than redefine success.
- 2026-11-17: New residual-advice development design, not promotion of the failed
  selector. Trace inspection showed both gains and losses from replacing generic
  advice with personal plans, including premature closure and wrong own-value arithmetic.
  Retain generic advice and every original report, adding one 45--95-word conditional
  lesson derived only from abstract own-value traces of the five Sim3 practices.
  Enforce the word bound, no digits/past issue labels, and actual own-turn citations;
  bounded regeneration on invalid output, with all attempts retained. No deterministic
  policy override, hidden utilities, test-case coaching or manual trait learning.
  Expand from eight to sixteen distinct practice histories (eight per concession
  profile) by adding forty Sim3 sessions at the unchanged 2,2,4,4,4 tiers. New users
  8--15 use fresh seeds and traits indexed modulo eight. Existing histories remain
  exact; no old test outcomes enter the per-user coach payload.
  Four fixed arms: reports; reports+generic; generic+own residual lesson; generic+
  another learner's lesson (fixed cross-profile permutation). No per-user arm selection.
  Development on Harbor/Maple: 16 x2 cases x4 arms =128 fresh negotiations. Aggregate
  cases within history before inference. Primary advance gate remains positive means
  and two-sided exact sign-flip p<=.05 against BOTH reports and generic; shuffled-note
  specificity is a separately reported control, not proof by assumption. Do not alter
  the gate or stop by intermediate outcomes. Freeze new original Pine/Willow cases
  before development; any final follow-up requires passing this new gate and its
  independently verified complete cohort. Sim4/Cedar remain excluded from tuning.
  Estimated development cost $18 including 40 new practices, 16 bounded lesson builds,
  and 128 assessments. Within latest $150 joint allowance; allocate cumulative dev
  ceiling $140 and retain final $110 for conservative reservations. Combined $250
  ceilings minus pre-audit $178.940503 permit at most $71.059497 new spending, below
  $150; preserve all prior ledger charges and limits audit history.
- 2026-11-17: User reiterated urgency: "What are you doing?! Have you riun the final
  evals yet?" Prioritize closure with an unconditional final audit of the existing
  personal-plan method. Do NOT run the proposed residual-advice development search;
  its unexecuted candidate code was removed. Finish only the already-running forty
  practices to supply eight additional histories, then preserve the eight old plans
  exactly and generate eight new plans with unchanged dd19a8d build_plan logic.
  Reallocate the never-scored Pine/Willow files to final-personal-audit-v1, recording
  the amendment before any outcomes and retaining the original case hashes/manifest.
  This is a new unconditional audit, not a claim that the earlier failed gate passed.
  Fixed sixteen histories x two cases x reports/generic/personalized =96 final
  negotiations, matched controller seeds, randomized arm order, no final feedback,
  tuning, outcome-dependent stopping or per-user selection. Average cases within each
  history; require positive means and exact two-sided sign-flip p<=.05 versus BOTH
  controls. Report all outcomes even on failure. Eight reused histories/eight new,
  two prompt profiles, synthetic assumed utilities and incomplete calibration remain
  limitations. Estimated additional preparation+final cost $10, within existing caps
  and the latest $150 authorization. No further development experiments are launched.
