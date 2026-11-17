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
