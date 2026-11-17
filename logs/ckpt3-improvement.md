# Matched-history coaching improvement

## Prospective design, 2026-11-17

The completed T-046 study did not establish reflective-card superiority. Sim3 transcripts
show examples of accepting a lower-value formal package after a persuasive explanation,
even when a card advised checking whole-package value. This motivates explicit decision
procedures and worked arithmetic, not a claim that they will improve outcomes.

All conditions now receive the SAME five report-guided practice histories. Afterwards,
compare full reports, sequential reflection reconstructed from those histories, a new
consolidated workbook, and the fixed procedure alone. The workbook includes portable
personal plans, at most three conditional rules, and two historical own-utility examples
with arithmetic calculated in code. Prior offers are comparison points, not guaranteed
available alternatives. Current-case values must be recomputed. Coaching remains
post-session; actor model, persona, private-information boundaries and economics stay fixed.

This isolates memory construction more clearly than separately evolving practice branches.
The procedure-only condition measures generic instruction effects. A victory for that
condition would not establish personalized learning. Neither intervention updates weights.

For user u, let D_u contain the five common completed rehearsal histories and debriefs.
Construct M_u = {reports(D_u), reflection(D_u), workbook(D_u), fixed_procedure}.
The bounded personalized search is m*_u = argmax_m mean_tier G(u, hiring, m), using the
prespecified tie order. Transfer compares G(u, target, m*_u) against each fixed memory
condition on target cases not used in that selection. The selector uses twelve validation
negotiations per persona (four candidates × three tiers), in addition to five rehearsals;
it is therefore not a five-interaction intervention or an equal-evaluation-compute control.
The selection case baseline is measured for comparison but does not affect the argmax.
This is optimization of retained context, not actor weights or hidden persona parameters.

The approach draws on [GEPA](https://arxiv.org/html/2507.19457v2)'s separation of reflective
proposal and measured validation, and [negotiation feedback work](https://arxiv.org/abs/2305.10142)
using critique and retained history. It does not implement GEPA's full population search.
[MERIT](https://arxiv.org/html/2602.10467v1) also motivates utility-grounded feedback;
results in these papers are not evidence that this implementation works. The withdrawn
2505.22998 paper is not used as evidence.

## Data separation and selection

Initial development reuses the completed report histories for personas 0–3 (seed 28221117)
and assesses Cloudline hiring and Sim4. Personas 4–7 are reserved for a separate development
validation comparison. All methods use the same baseline and counterpart seeds; all users,
including failures and negative gains, remain included. Candidate selection is by the mean
normalized outcome across development cases within each persona, with paired uncertainty
and agreement failures reported. If revision is needed, record it before another run.

Sim4 is explicitly revisited. Two original, hand-authored synthetic cases (Harbor Analytics
and Maple Festival) were frozen before any follow-up experiment; see
`results/ckpt3/improvement-design/fresh_cases_manifest.json`. Their utilities are assumptions,
not external benchmark labels. Do not revise them based on measured candidate outcomes.
The development runner rejects manifests marked fresh_test.

Prospective final design: six new personas (seed 28221129), five common report-guided
rehearsals, all four memory conditions, and three assessment cases. The primary outcome
averages the TWO fresh-case gains within each persona, then compares paired personas;
Sim4 is secondary. Do not treat user-case pairs as independent users. Freeze the selected
intervention, instructions and final configuration before fresh outcomes. The final design
may be reduced for a documented budget forecast before test outcomes, never after seeing
an unfavorable result. Preserve the earlier study and its source commit 374cb63.

## API forecast and authorization

Starting cumulative ledgers: development $9.163600/100; final $41.133781/100.
Remaining: $90.836400 development and $58.866219 final. The user's prior explicit budget,
commit/push and fictional-case API authorization persists. No new allowance is created.

Initial preparation: 24 coach calls, roughly 0.2–0.5M input and 0.03–0.06M output tokens,
approximately $1–3 with cached inputs. Initial assessment: 120 episodes, approximately
1,200–1,600 requests, 8–12M total input and 0.4–0.7M output tokens. At 80% cached reads,
effective input cost is approximately $0.5–1/M plus cache writes, and blended output
approximately $15/M: forecast $15–25 plus preparation. Separate validation is similar.
Final 336 episodes plus 36 memory-construction calls: forecast $45–52 additional final
cost, subject to actual measured development usage. Rates and assumptions are estimates;
the shared gateway records provider tokens and enforces the existing cumulative caps.
No retries or uncertain reservations are silently discarded.

## Validation and reproducibility

Offline tests cover own-only evidence, acceptance arithmetic, immutable memories/personas,
paired cohort alignment, and no assessment feedback. Protocols fingerprint source, cases,
historical inputs, instructions and frozen memories. New files change the source fingerprint;
the earlier final study remains reproducible at its historical commit, not with a falsely
claimed matching current-source fingerprint. Raw histories and coaching remain ignored.

## Execution log

- Initial preparation completed: 24 coach calls, $1.491108 usage ($1.491117 ledger delta),
  no unresolved requests. Development ledger now $10.654717. Workbooks contain roughly
  5,000 characters versus 16,300 for reports and 1,500 for reflection. These are character
  counts, not token-cost claims.
- Code and frozen case design committed as 518f121; independent verifier as 762e0d5.
  Six new offline tests pass (171 total after adding the analysis test).
- Started the unchanged v1 candidate on validation personas 4–7 before inspecting complete
  development results. This is a separate cohort check, not adaptive candidate selection
  on validation outcomes. Both cohorts retain all four conditions and both known cases.
  Their already recorded combined forecast is approximately $32–56 additional development
  cost including preparation, within the existing cumulative cap; at most eight workers
  across the two processes. No fresh test outcomes are accessed.
- Prespecified an additional per-persona prompt-selection policy before any new Sim4
  assessment: choose the memory with highest three-tier mean G on hiring, with ties
  favoring reports, then reflection, workbook, fixed procedure. Evaluate that choice on
  Sim4 only, never on the selection case as evidence of transfer. This reuses the same
  four candidate assessments and adds no API calls. `scripts/select_consolidation.py`
  reads only selection-case outcomes and hashes them and frozen memories. All candidates
  are evaluated regardless of selection, so generating the selection file after a target
  run does not affect the fixed rule; no target score enters selection. This tests bounded
  per-user prompt refinement more directly than assuming one representation suits everyone.
- First complete development case (hiring, personas 0–3): workbook gain +0.025641,
  reports +0.008013, reflection -0.036859, fixed procedure +0.003205. Workbook minus reports
  +0.017628, paired pointwise bootstrap interval [0.003205, 0.032051], n=4; exploratory,
  not a population claim. All 60 episodes agreed. Four agreements were below the learner's
  walk-away: baseline 1, reports 1, procedure-only 2, reflection/workbook 0. No counterpart
  schedule violations. Independent enumeration verifies the outcome table. Assessment cost
  $5.611818 usage for 818 calls, versus $12.968222 at the same volume without caching.
  Selection on hiring chose workbook for users 0/2, reflection for 1, and reports for 3;
  their Sim4 assessment began only after this mapping was written.
- Separate hiring validation (personas 4–7), unchanged candidate: workbook gain +0.078526,
  reports +0.044872, reflection approximately zero, fixed procedure +0.041667. Workbook
  minus reports +0.033654, interval [-0.006410, 0.075321], n=4. Of 60 episodes, 59 agreed;
  the one impasse was in reports. Five below-walk-away agreements: reflection 3, reports 1,
  procedure-only 1; workbook and baseline 0. No schedule violations. Assessment usage
  cost $5.451397 for 796 calls. The prespecified selector chooses reports for user 4,
  procedure-only for 5, workbook for 6/7. This mapping was materialized after Sim4 began,
  using only completed hiring outcomes and the rule committed before any Sim4 results.
- Development Sim4 user 0 / reflection / tier 5 received one provider refusal
  (`reasoning_extraction`) from the counterpart-dialogue call after eight saved turns.
  The gateway settled the response cost and preserved the checkpoint. Permit one explicit
  resume at the identical prompt/state; no persona, seed, memory, model, or completed score
  is replaced. Preserve the original error artifact and retry cost. A recurrent refusal
  is reported as an unresolved execution failure rather than silently dropping the user.
- Both v1 cohorts finished, 240 assessment episodes. The one refusal resumed successfully
  with seven additional calls ($0.104813); no uncertain requests remain. Incremental v1
  cost $34.175610; cumulative development $43.339210, final unchanged $41.133781.
  Sim4 workbook gains differ by cohort: -0.004167 (0–3) and +0.078125 (4–7).
  Reports: +0.067708 and +0.057292. Personalized selection: -0.025000 and +0.087500.
  Pooled exploratory Sim4 gains: reports +0.062500, workbook +0.036979, procedure +0.043229,
  reflection -0.006771, selected +0.031250. No demonstrated transfer improvement over reports.
  All outcome tables, errors, hashes, costs and paired plots are preserved.

## v2 development ablations, specified before new calls

Test two focused changes: remove the workbook's historical examples (retain identical
personalized plans/procedure), and retain all five original reports while adding the fixed
decision procedure. This asks whether compression or historical examples hurt transfer.
Neither changes actor/persona/economics, and neither requires another coaching call.

Reuse the exact completed baseline/reports/workbook/procedure episodes and frozen memories
from v1, with file hashes and source provenance; never rerun a control to obtain a favorable
sample. Run only the two new arms on the same known cases and counterpart seeds. First
personas 0–3, then the separate 4–7 cohort if worth validating; these are development
ablations, not fresh test outcomes. Additional calls: roughly 650–800 for 48 new episodes
per cohort, approximately 4–5M total input (mostly cached) and 0.3–0.4M output, forecast
$6–10 per cohort at the measured blended rates. At most $12–20 across both, within the
remaining $56.660790 development allowance. The final budget and fresh cases stay untouched.

- Both unchanged v2 candidates were started concurrently on the two cohorts, before any
  new-arm outcomes, with eight total workers. Preparation made zero API calls and preserved
  96 exact control episodes per cohort. First complete hiring results are mixed:
  reports-plus-procedure gain +0.032051 (0–3), +0.009615 (4–7); workbook-without-examples
  +0.020833 and +0.030449. Existing reports gains remain +0.008013 and +0.044872.
  The two new hiring arms cost $4.760785 in provider-usage estimates across both cohorts.
  Sim4 outcomes are still pending. No candidate is selected from hiring alone.
- v2 completed with 96 new episodes and 192 reused controls, costing $12.904979 in ledger
  increments; no execution errors. Cumulative development is $56.244189, remaining
  $43.755811. Incremental spending for this improvement goal is $47.080589. Averaging the
  two development cases within each of eight personas gives gains: reports +0.044471,
  workbook +0.044531, procedure +0.032833, no-example workbook +0.023498,
  reports-plus-procedure +0.036979. The workbook's numerical lead over reports is essentially
  zero and does not establish improvement. The ablations did not improve the overall result.

## Frozen prospective confirmation, before any final calls

Select **workbook** as the primary candidate against **reports**. Rationale: repeated
positive hiring contrasts, similar aggregate development performance with substantially
shorter retained context, and stronger performance than the two ablated variants overall.
This is a hypothesis to test, not a claimed development victory. Fixed procedure and
workbook-without-examples are secondary controls. Drop the unsuccessful case-based prompt
selector from confirmation: its pooled Sim4 gain was lower than reports, despite a positive
second-cohort result. Preserve all those results rather than selecting that favorable cohort.

Use seven fresh personas, seed 28221129, five common report-guided Sim3 rehearsals, tiers
(2,2,4,4,4), and baseline/post assessment tiers (1,3,5). The primary endpoint is workbook
minus reports on the mean of the TWO fresh synthetic case scores within each persona.
Bootstrap personas (2,000 draws, seed 1); n=7, not 14 independent persona-case pairs.
Report gains, paired contrasts, failures and negative agreements for every condition.
Only this one contrast is primary; secondary intervals are pointwise/exploratory.

Budget-driven revision before test outcomes: focus confirmation on Harbor Analytics and
Maple Festival, omitting another Sim4 rerun because it has already been examined extensively
in development. This permits seven instead of the tentative six personas while protecting
completion within the remaining final allowance. Case JSONs and hashes remain exactly as
frozen before v1. See `confirmation_manifest.json`; the original tentative manifest remains
preserved. No case or user was selected based on confirmation outcomes: none exist yet.

Plan 77 training-case episodes (baseline + five practice + reports post per persona),
210 fresh-case episodes, and seven consolidation calls: 287 episodes total, roughly
3,600–4,400 API requests. Estimated 24–30M input at ~80% cache reads and 1.4–1.8M output,
forecast $30–48 additional final cost using measured rates and a conservative per-episode
upper forecast. Existing final ledger $41.133781/100; remaining $58.866219. Preserve enough
room for the gateway's conservative live reservations; never raise/reset the cap. A single
known refusal may be resumed once from the identical checkpoint with its cost recorded.

- Confirmation preparation completed: all 77 training-case episodes and seven consolidated
  memories. Independent audit verifies their terminal utilities, training curves, seeds,
  tiers, full cohort and memory hashes. Usage estimate $8.853005; ledger increment $8.853373
  for 748 calls. Final cumulative ledger $49.987154 after preparation, no unresolved calls.
  Fresh-case assessment began only after all memories were frozen; no primary outcomes
  have been inspected or used to alter the selected method.
- Offline development-history diagnostic: 13 of the 16 selected large-concession examples
  match a saved counterfactual estimate; eight have a positive estimated terminal gain
  from the alternative (and a positive lower interval bound). Other examples have zero,
  negative or absent estimates. Immediate loss of own offer value is not synonymous with
  a worse eventual deal. This suggests credit-based example selection as a future
  hypothesis, while recognizing that the rollout estimates themselves can be wrong.
  No confirmation memory or selection rule was changed. Numeric diagnostic saved in
  `results/ckpt3/improvement-design/example_credit_diagnostic.json`; no API calls were used.
- Harbor Analytics completed all 105 planned episodes. Independent audit checked their
  agreement economics, seeds, tiers and complete paired rows without inspecting treatment
  means. Provider-usage cost $12.421521; ledger increment $12.422135 for 1,498 calls.
  Same-token-volume uncached estimate $27.971128. Final ledger $62.409289 at phase end,
  no unresolved calls. Maple Festival then started under the identical frozen protocol;
  primary comparisons remain uninterpreted until both cases complete.
- Confirmation completed and independently verified all 287 episodes. Primary workbook
  minus reports = -0.000113921, 95% interval [-0.033283967, +0.029720608], n=7. No demonstrated
  improvement. Fixed procedure has the highest secondary point estimate, but its contrast
  with reports is also inconclusive. Full results and failures are in
  `logs/ckpt3-improvement-results.md`. Confirmation ledger increment $34.587048; total new
  improvement spending $81.667637. Remaining caps: development $43.755811, final $24.279171.
  The goal of better demonstrated transfer remains unmet; proceed to the credit-based
  example-selection hypothesis without overwriting or relabeling this confirmation.

## Credit-based follow-up, specified before new candidate calls

Change example selection to the existing disjoint-rollout estimate of terminal surplus
improvement, not the largest immediate concession. Prefer positive lower bounds, then
positive means; retain uncertainty and the distinction between modeled alternatives and
observed outcomes. Choose at most two different practice sessions. If evidence is weak,
the coach must preserve that uncertainty and avoid inventing a better action. Keep the
fixed procedure, own-visible history, original personas, models and five common reports
rehearsals. No assessment feedback enters coaching.

Develop the new credit memory on the same 0–3 and 4–7 cohorts, reusing exact v1 baseline,
reports and procedure controls with hashes. Only one new memory arm is run: 48 additional
assessment episodes plus eight coaching calls, forecast $8–12. Existing development cap
remains $100, with $43.755811 available at the start. Preserve complete cohort outcomes.

If development justifies a follow-up, assess the candidate on the newly frozen original
Beacon Museum case, SHA256 d4221d8bf6412a5fbd9439ddeabe91e4fa30090d94c28a30dc409bb510f19b1c.
It has 729 packages, 324 legal, 224 mutually acceptable; assumed feasible maxima 490/550.
It was authored AFTER the first confirmation and BEFORE credit-candidate experiments.
Use all seven existing confirmation personas and their unchanged common practice histories;
these are not new people, but the case and credit-memory outcomes are unseen. Compare
credit memory with reports and the fixed procedure, tiers 1/3/5, 84 episodes plus seven
coaching calls. Primary contrast: credit memory minus reports on this one case, paired
by persona. This is an additional prospective follow-up after a failed primary study,
not a replacement or independent replication of its personas. Any favorable result needs
broader replication; report the earlier failed primary result alongside it.

Forecast follow-up final cost $11–15, leaving room for conservative request reservations
within the remaining $24.279171 of the existing final cap. No new Sim3 training is charged
or claimed: the same saved five-rehearsal histories are reused. No final calls occur until
the candidate is frozen after development. The original two fresh cases are now known and
are not silently reused as untouched tests.

Before running this candidate, set the decision rule: proceed to the Beacon follow-up
only if credit memory's paired mean exceeds reports both in the pooled eight-person
development comparison (cases averaged within persona) and in the separate 4–7 cohort.
This is a candidate-screening rule, not a significance claim. Preserve all eight users,
both cases and the earlier methods regardless of this decision. Forecast roughly 700–900
requests for development, 4–6M input tokens with ~80% reads and 0.3–0.45M output; final
roughly 1,200–1,500 requests, 7–10M input and 0.5–0.65M output at the observed model mix.
The dollar forecasts above include margin over these approximate volumes.

- Credit implementation validated before paid calls: 180 offline tests pass, one live
  test deselected; lint/format and all 40 task files pass. Tests cover paired rollout
  completeness, uncertainty-aware selection, distinct sessions, information boundaries,
  feedback alignment, empty-evidence fallback and exact saved-plan resumption.

- Credit development completed: 48 new assessment episodes, 144 exact reused controls,
  eight coach calls; 675 API requests total. Pooled candidate-minus-reports mean
  -0.006089744, 95% interval [-0.038723458, +0.024702524], n=8. Separate validation
  mean -0.016786859, interval [-0.073637821, +0.045793269], n=4. The prespecified
  advancement rule failed. No final-budget calls were made and Beacon remains unused.
  All 192 assessed episodes verified; 190 agreements, two impasses, seven agreements
  below walk-away, zero schedule violations. These totals include reused controls.
  Exact ledger increment $7.427020, provider-usage estimate $7.426728; 4,310,734 input
  tokens, 266,115 output, 78.80% cached reads. Same-volume uncached estimate $15.889796.
  Development cumulative $63.671209, final $75.720829; no unresolved requests. Combined
  checkpoint-3 cost $139.392038, of which $89.094657 belongs to this improvement goal.

## Own-value worksheet candidate, specified before its calls

The credit candidate also accepted a known hiring package worth 2,500 own points against
a 3,500 walk-away. Longer advice did not ensure correct execution. Test a deterministic
current-case preparation worksheet alongside the unchanged five reports. Re-express the
own point table as concession costs from each issue's own best option, with the exact
identity U = sum(issue maxima) - sum(option losses), the current walk-away and allowable
total loss. Include own hard constraints and explain that the own upper bound is not a
promise of a mutually feasible deal. Do not use opponent utilities, feasible-best scoring,
assessment outcomes, or hidden schedules. Keep all formal actions chosen by the same
learner; this is a preparation aid, not an enforced policy or live coach.

This changes the hypothesis from compact memory selection to making reports easier to
apply through exact current-case arithmetic. A gain would establish an instruction/aid
effect for simulated learners, not personalized learning or human transfer. Full reports
remain personalized and unchanged; combine them into one memory entry to avoid truncation.
Generate a separate worksheet for each case using only that case's own-role information.

Use the same eight development personas and two known cases; reuse exact baseline,
reports and fixed-procedure controls. One new reports-with-worksheet arm requires 48 new
episodes, no coaching-generation calls, roughly 650–850 requests, 4–6M input (~80% reads)
and 0.25–0.4M output; forecast $7–11. Development remaining $36.328791, same $100 cap.
Freeze code before running. Advance only if the paired mean exceeds reports both pooled
and in users 4–7, using both cases within persona. This is a screening rule, not inference.
If advanced, the unused Beacon case, same seven confirmation personas, reports/procedure/
worksheet conditions and 84 total episodes remain the final follow-up plan, $11–15
forecast within the unchanged $24.279171 final allowance. Retain both earlier negative
candidates and the failed first prospective confirmation in all reporting.

- Worksheet implementation passes 183 offline tests, one live deselected. Exhaustive
  package checks verify the loss identity with negative point tables; changing the hidden
  opponent sheet cannot change the aid. Per-case projection exposes only the current
  worksheet and rejects modified cached projections. No actor or scoring source changed.

- Worksheet development completed: 48 new episodes, 144 exact reused controls, zero
  coaching-generation calls. Pooled worksheet-minus-reports -0.006770833, 95% interval
  [-0.031892528, +0.030232873], n=8. Validation -0.023277244, interval
  [-0.037900641, -0.008653846], n=4. Advancement rule failed; no final calls. Exact
  incremental ledger cost $7.083665 (704 calls), usage estimate $7.083354. Development
  cumulative $70.754874, remaining $29.245126; final unchanged $75.720829, remaining
  $24.279171. No unresolved charges. Checkpoint-3 total $146.475703; new improvement
  goal $96.178322. Full results, including failed outcomes, remain versioned.

## Varied-practice hypothesis, specified before its calls

Report-based coaching has held up better than compact reflection, selected examples or
the arithmetic aid. The remaining hypothesis changes the practice distribution rather
than the memory wording: five repetitions of one case may transfer poorly. Compare the
same five-session budget with a three-case curriculum. Reuse the first two exact Sim3
reports-guided sessions (tiers 2,2), then rehearse hiring, Sim4, hiring at tiers 4,4,4.
Carry the accumulated reports into each practice and preserve all five reports for the
assessment. The control is the existing five-Sim3 reports branch. This is a curriculum
comparison, NOT matched-five-history prompt refinement. Only the first two histories are
shared; no persona changes, weights, hidden sheets, or assessment feedback are used.

Development uses the original users 0–3 and 4–7, seed 28221117. Assess both groups on
Harbor Analytics, which was seen in the first confirmation and is now explicitly a
revisited development case. It is not one of the practice cases. These eight personas
have not previously been assessed on Harbor; run new baseline/reports/diverse-reports
episodes at tiers 1/3/5, 72 total, plus 24 new practice sessions and 24 ordinary debriefs.
This preserves session count while testing different practice content. It does not isolate
diversity from which cases, role changes, order or report lengths were used.

Forecast 1,100–1,500 requests, 8–10M input (~80% reads), 0.5–0.7M output, $12–18
development. Existing development allowance is $29.245126 with no cap increase/reset.
Freeze this single curriculum before outcomes. Advance only if diverse reports beat
reports in both the pooled eight-person mean and the separate users 4–7 mean. Keep all
cases/personas/failures; this screening rule does not establish significance.

If it advances, use the still-unused frozen Beacon Museum case and all seven existing
confirmation personas, seed 28221129. Reuse their two-session Sim3 prefixes; generate
21 new curriculum sessions/debriefs. Assess baseline, reports and diverse reports only,
63 new test episodes. Omit the procedure arm prospectively to preserve the existing
final-budget allowance. Total 84 new episodes, forecast $12–16, leaving at least ~$8
for conservative live reservations within the unchanged final $100 cap. A fresh case
does not make these seven personas fresh, and this follows multiple failed candidates.
Report the whole sequence regardless of the outcome. Beacon's case bytes remain frozen.

- Varied-practice implementation validated offline: 184 tests pass, one live deselected;
  all task files valid. The curriculum preserves the exact two-report prefix and five
  total reports, uses sequential accumulated feedback, and never modifies persona traits.
  Independent audits distinguish the original control histories from the shared prefix
  and new varied-practice sessions; transfer-case overlap is rejected before API calls.

- All 24 new varied-practice sessions and debriefs completed; independent audit verifies
  report identity/order, the exact two-session prefix, seeds, tiers, complete cohorts and
  numerical scores. All agreed above walk-away; zero schedule violations. Preparation
  uses 449 requests, usage estimate $5.376557 and ledger increment $5.376745. Development
  cumulative $76.131619, no unresolved charges. Both histories were frozen before Harbor
  assessment. Use two workers per cohort to reduce contention for conservative live
  reservations as the existing cap approaches; do not alter models, seeds or conditions.
