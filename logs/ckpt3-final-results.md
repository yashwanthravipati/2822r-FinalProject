# Checkpoint 3: final simulated-learning and transfer results

**Post-study correction:** the LLM learner received six numeric error tendencies under
opaque IDs without their behavioral definitions. Thus the intended named-weakness
personas were not correctly specified. The scores below describe the implemented
prompt/memory conditions, not a validated test of those intended learners. Corrected
persona prompts require behavioral calibration and new controls; these outcomes cannot
serve as runs of that corrected simulator. See the prominent correction in
`docs/report.tex`. This defect is separate from the already reported uncertainty and
absence of human evidence.

## Main finding

Compact reflection produced a positive held-out Sim4 gain after five Sim3 rehearsals:
**+0.08333**, versus **+0.07500** for accumulated reports. The paired difference is
**+0.00833**, with a pointwise persona-bootstrap 95% interval **[-0.05522, 0.06616]**.
This small study does **not** establish that reflective cards outperform reports, nor
does it establish equivalence. Their practical attraction is much shorter retained
context: about 1,508 characters versus 16,508 for five reports. The additional learner
application/correction exercise did not demonstrate a benefit.

This is evidence about contextual adaptation of simulated LLM negotiators. It is not
evidence of human learning, model-weight learning, or durable skill without the memory.

## Design and what changed since the existing report

The original report compared adaptive, greedy, random and absent rehearsal targeting on
the same Sim3 case. This checkpoint holds focus at none and difficulty at (2,2,4,4,4),
and changes the post-session feedback/memory update. Eight fixed new personas each
receive all three five-rehearsal training conditions in randomized order:

- **Reports:** retain the existing counterfactual debriefs.
- **Reflection:** update at most five conditional rules with triggers, actions and
  exceptions, grounded in own-visible training evidence.
- **Application/correction:** propose the same card, ask the learner to apply the
  principle to a short fictional analogy, then revise the card using its answer.

A fixed generic card is also assessed on Sim4 without training. It is a zero-shot
reference, not a trained control. Each assessment averages tiers (1,3,5), uses a fresh
actor with its fixed persona and frozen memory, and supplies no new coaching. Sim4 was
constructed and frozen before final training; no held-out score was used for method
selection or utility revision. The study contains 216 Sim3 and 120 Sim4 episodes.

The method is GEPA-inspired evidence-grounded reflection, not GEPA's full candidate
population/Pareto search. The [method design](ckpt3-method-design.md) records the
GEPA, Reflexion, Self-Refine, ACE and negotiation-analogy literature, formalism and
prespecified protocol. Initial synthetic development did not favor the new methods;
those negative results remain in the chronological log and public artifacts.

## Primary outcome: transfer to Sim4

The shared baseline mean G is **0.49635**. G is normalized terminal surplus averaged
over three tiers, using the frozen experimental point tables and walk-away values.

| Condition | Final mean G | Mean gain | Pointwise bootstrap 95% interval for gain |
|---|---:|---:|---|
| Reports | 0.57135 | +0.07500 | [0.02083, 0.13073] |
| Reflection | 0.57969 | +0.08333 | [0.01719, 0.13126] |
| Application/correction | 0.51458 | +0.01823 | [-0.07708, 0.09479] |
| Generic advice, no training | 0.51042 | +0.01406 | [-0.05208, 0.06928] |

| Paired gain contrast | Mean difference | Pointwise bootstrap 95% interval |
|---|---:|---|
| Reflection minus reports | +0.00833 | [-0.05522, 0.06616] |
| Application minus reports | -0.05677 | [-0.12500, 0.01198] |
| Application minus reflection | -0.06510 | [-0.16042, 0.01354] |
| Application minus generic advice | +0.00417 | [-0.04063, 0.05522] |

All eight personas are retained, including negative outcomes. For example, the largest
application-arm decline was -0.28333 from a high baseline; it was not removed as an
outlier. A negative gain means worse than that persona's baseline, not necessarily a
deal below its walk-away value. All 120 held-out episodes agreed, with zero such
below-walk-away agreements and zero counterpart schedule violations.

## Secondary outcome: assessment on the training case

The shared Sim3 baseline mean G is **0.40057**.

| Condition | Final mean G | Mean gain | Pointwise bootstrap 95% interval for gain |
|---|---:|---:|---|
| Reports | 0.44886 | +0.04830 | [0.03314, 0.06345] |
| Reflection | 0.39773 | -0.00284 | [-0.02559, 0.02557] |
| Application/correction | 0.40625 | +0.00568 | [-0.02746, 0.03506] |

Reports outperformed reflection by 0.05114 and application by 0.04261 in the paired
point estimates; both corresponding pointwise intervals exclude zero. The old debriefs
retain case-specific information and scripted counterfactuals, while the new cards are
abstract and use own-visible evidence. This is a comparison of feedback packages, so
the difference cannot be attributed solely to compression. All 216 Sim3 episodes agreed,
with no below-walk-away agreements or counterpart schedule violations.

## Context size, cost and caching

| Retained memory | Mean characters | Mean whitespace-separated words |
|---|---:|---:|
| Five reports | 16,507.6 | 2,369.9 |
| Reflection card | 1,507.6 | 251.3 |
| Application/correction card | 1,527.0 | 255.4 |
| Generic card | 1,293 | 193 |

The learned cards use about 91% fewer characters than reports. These are context-size
measurements, not provider token counts or per-method cost estimates. The application
arm also uses two additional short calls per rehearsal. Its contrast is not compute-
or interaction-matched. In this LLM implementation, the application answer affects the
coach's card revision; later actors retain the card, not a weight update or an internalized
memory of solving the analogy. That limits the analogy to human learning mechanisms.

| API budget | Recorded cost | Authorized cap | Remaining |
|---|---:|---:|---:|
| New development, both synthetic studies | $9.163600 | $100 | $90.836400 |
| Final Sim3 training | $23.137476 | Part of final cap | — |
| Final Sim4 assessment | $17.996305 | Part of final cap | — |
| Final study total | **$41.133781** | $100 | $58.866219 |
| All new checkpoint-3 work | **$50.297381** | $200 combined | $149.702619 |

Final study: 3,712 completed API requests, zero failed/uncertain requests, 24,556,645
input tokens, of which 19,899,580 (**81.04%**) were cache reads. Cache-hit requests were
3,689/3,712 (**99.38%**). Five-minute prefix caching was used; output samples were not
memoized. The same token volume without caching is estimated at **$89.890158**, versus
$41.133781 recorded, giving **$48.756377 estimated savings (54.24%)**. This is an
accounting counterfactual, not a randomized comparison of cache implementations.
Ledger costs include per-request micro-dollar rounding and are usage-based estimates,
not an independently checked provider invoice.

The earlier study ledger remains separate: $65.342720 recorded, plus $68.092160 in
conservative bounds for nine unresolved historical requests. Those bounds are not
confirmed spend and were not released to enlarge either new budget.

## Interpretation and next research decision

Keep the existing reports as the established same-case baseline. Simple reflective cards
are a promising compact transfer option, but this result does not justify claiming they
are better than reports. The extra application/correction loop adds work without a
demonstrated return here, so it should remain an experimental ablation rather than become
the default. A further study could retain a short worked example alongside the conditional
rules and test whether that improves execution of the strategy; it would need a new
held-out case set because Sim4 outcomes have now been examined. No such change was made
to this final study after observing its results.

The sample has eight simulated personas and one held-out scenario, not 31 independent
cases. Intervals use 2,000 persona-level bootstrap resamples and are pointwise, without
multiplicity adjustment. LLM sampling is unseeded, and no repeated independent model
trials per persona/method/tier were added. Persona tendencies are not validated human
error probabilities. Sim4 utilities, reservation values and additive scoring are analyst
assumptions; their uncertainty is not included in the intervals. The projection admits
480 mutually acceptable packages out of 729 and may make agreement too easy. Its score
measures a fictional conditional operational plan, not realized access or human welfare.

## Verification and reproduction

The independent verifier enumerated all feasible packages to obtain score denominators,
recomputed all 336 episode outcomes, checked 24 training and 32 held-out paired rows,
and verified all 24 frozen memories and the case/source/protocol hashes. All checks pass.
The repository's 165 offline tests pass; one live test is deselected. Lint, format and
task checks pass. Raw case text, transcripts, generated cards and credentials remain
untracked. Existing user edits to `docs/report.tex` and `.gitignore` are preserved.

- Source SHA-256: `29f4133d304f7063f637ac0a83a4d1f13462fdbab152484c420e0950a8d37393`.
- Protocol SHA-256: `eac51a9313558fcee012eaf86af89239084876f9da6c0111efd19025b237f5f8`.
- Results: `results/ckpt3/final-v1/`, with held-out tables under `heldout/`.
- Independent audit: `verification_all.json`; accounting/diagnostics: `audit.json`.
- Figure: `learning_gains.png` and `learning_gains.svg`, showing all paired personas.

Offline commands, from the repository root with the private frozen cases available:

```bash
.venv/bin/python scripts/verify_ckpt3.py --root results/ckpt3/final-v1
.venv/bin/python scripts/analyze_ckpt3.py --root results/ckpt3/final-v1 --budget final
.venv/bin/python scripts/plot_ckpt3.py --root results/ckpt3/final-v1
```

The frozen paid-run commands and exact seeds are in `logs/ckpt3-method-design.md`.
Use a new output directory for a deliberate repeat; do not overwrite these frozen results.
