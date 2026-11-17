# Few-interaction strategy refinement: design before experiments

## Research basis and prior judgment

- [GEPA](https://arxiv.org/html/2507.19457v2) uses execution feedback to propose prompt
  mutations and selects candidates using measured performance. We adopt evidence-grounded
  mutation and independent evaluation, but avoid claiming to reproduce its full Pareto search.
- [Reflexion](https://arxiv.org/abs/2303.11366) motivates persistent verbal memory between
  trials without weight updates. Our learner retains a small strategy card across cases.
- [Self-Refine](https://arxiv.org/abs/2303.17651) motivates a critique/revision loop. An LLM's
  endorsement alone is not evidence of improved negotiation return.
- [ACE](https://arxiv.org/abs/2510.04618) motivates preserving useful lessons during
  incremental updates rather than repeatedly compressing everything into vague advice.

Prior judgment: targeted conditional rules, a concrete worked correction, and asking the
learner to apply the lesson should be more useful within five rehearsals than accumulating
long debriefs or optimizing a noisy error-count surrogate. Keep the mechanism simple,
measure terminal negotiation returns, and avoid a costly population search per learner.

## Proposed method

Keep persona, model, economic controller, and training length fixed. Maintain at most five
conditional strategy rules, each with an observable trigger, action, exception, and source
turn reference. After each rehearsal, the coach proposes a revision grounded in the
transcript and deterministic own-utility evidence. Existing useful rules are retained;
case names, exact packages, hidden utilities, and initial persona probabilities are not
valid transferable rules. The learner attempts one short application of the proposed
lesson; the coach uses that response to clarify the final card. This is an application
check, not an additional full negotiation or a claim of GEPA candidate-search superiority.

Use five rehearsals at tiers (2,2,4,4,4). Hold targeting constant at no focus for the primary
comparison: the previous adaptive targeting effect was inconclusive. This isolates how
feedback is represented and internalized. Development may test a simpler reflection-only
variant and generic advice. Final conditions and counts will be frozen after smoke tests,
before reading any held-out outcomes.

Notation: h_t is observed training history; m_t is bounded strategy memory. The coach
proposes p_t = Reflect(h_t,m_t); the learner produces a short application z_t; the coach
updates m_(t+1) = Revise(p_t,z_t,h_t). No model weights or planted persona parameters are
changed. Primary outcome is E_u[G_sim4(u,m_5)-G_sim4(u,empty)], compared with the same gain
under accumulated reports. G is mean normalized terminal surplus at tiers (1,3,5).
Use paired persona bootstrap intervals, with all model randomness acknowledged.

## Data separation and accounting

Sim3 is the training/development case. Sim4 documents are read only to construct and audit
its measurement model, never to write learner rules or select methods. Freeze its role
visibility, point assumptions, and source hashes before evaluation. Sim4 is one scenario,
not 31 independent cases. Baseline and post-training probes use isolated actor copies and
provide no new coaching; their transcripts never enter training or rule refinement.
Freeze trained memories before invoking held-out probes. In-domain Sim3 assessment is
secondary because debriefs can reveal its hidden economics.

All API calls use the shared gateway. New development and final ledgers each have a $100
cap; previous charges remain untouched. Preliminary cost planning uses the prior observed
$65.34 / 280 episodes = ~$0.23/episode as a conservative planning proxy (that numerator
includes pilot/recovery and is not a pure per-episode price). A roughly 300-episode final
study plus short memory updates is planned below $100; choose the final sample count from
smoke costs before observing any Sim4 scores. No claim about power is made from this budget.

## Scope of conclusions

We test LLM behavior with external memory, not durable weight learning or human skill.
Sim4 utilities are inferred experimental assumptions. Report generic-advice and memory
comparisons, token costs, agreement, failures, and the limits of a single held-out case.
If reflection fails, report that directly rather than tune on the held-out case.

## Implemented comparison and reproducibility

The initial implementation compares three equally long training branches per persona:
accumulated reports, reflection-only cards, and reflection plus one short learner
application/correction per rehearsal. Difficulty and focus are fixed across branches.
The application arm has extra teaching interactions and API compute; its contrast with
reflection measures that combined intervention, not a compute-matched causal effect.
A generic strategy card is assessed as a zero-shot reference on the held-out case; it is
not described as a trained control. Persona draws, method-order randomization, case/source
hashes, and cache settings are persisted. LLM sampling itself is not seedable.

Reproduction (commands involving class data require the pending explicit external-payload
approval; no Sim4 outcome has been inspected):

```bash
# Synthetic smoke; no class materials are sent.
.venv/bin/python scripts/ckpt3_evaluate.py train \
  --root results/ckpt3/synthetic-smoke --budget dev --users 1 --rounds 2 \
  --workers 1 --seed 28221118 --training-case data/cases/cloudline_hiring.json \
  --training-role candidate

# Sim4 was constructed and audited locally; reuse the private frozen projection.
# See results/ckpt3/heldout-case/manifest.json for hashes and numerical checks.
# scripts/prepare_sim4.py is an optional API-assisted constructor for a new version,
# not needed for the frozen case and not authorized to transmit class content yet.

# Proposed final run: finalize user count from smoke costs before invoking.
.venv/bin/python scripts/ckpt3_evaluate.py train \
  --root results/ckpt3/final-v1 --budget final --users 8 --rounds 5 --workers 4
.venv/bin/python scripts/ckpt3_evaluate.py assess \
  --root results/ckpt3/final-v1 --budget final --users 8 --rounds 5 --workers 4
.venv/bin/python scripts/analyze_ckpt3.py --root results/ckpt3/final-v1 --budget final
```

At eight personas this design has 24 shared Sim3 baseline probes, 120 training episodes,
72 Sim3 post probes, 24 shared Sim4 baselines, 72 Sim4 post probes, and 24 generic-card
Sim4 probes: 336 episodes. There are 40 reflection-only updates and 40 three-call
application updates. Sim4 cannot be used by `--budget dev`; training memories and the
protocol must match their freeze hashes before assessment begins. Completed learning
steps reject changed inputs on resume. Counterfactual reports retain the original
scripted-rollout limitations in the accumulated-report control.

## Additional transfer literature and interpretation

[Loewenstein, Thompson and Gentner (1999)](https://www.kellogg.northwestern.edu/academics-research/research/detail/1999/analogical-encoding-facilitates-knowledge-transfer-in-negotiation/)
and [Gentner, Loewenstein and Thompson (2003)](https://www.kellogg.northwestern.edu/academics-research/research/detail/2003/learning-and-transfer-a-general-role-for-analogical-encoding)
provide negotiation-specific evidence that comparing structurally related examples can
help people abstract a strategy and use it in a new negotiation. These human findings
motivate a short analogy/application exercise; they do not establish that our LLM memory
method has the same effect. The initial smoke uses a question about the observed mistake.
Before final evaluation, a fresh fictional application context would make transfer of the
principle a more direct teaching target without touching Sim4.

The report-versus-memory comparison is a package comparison: the old report uses scripted
counterfactual estimates while the new coach uses observed dialogue and deterministic
own-utility evidence. A benefit cannot be attributed solely to compression. Reflection
versus application/correction is the more focused ablation, though it adds interactions
and compute. These distinctions should remain explicit in the write-up.

## Revised method and frozen measurement model

The v2 coach abstracts domain nouns into issue value, constraints and alternatives, and
keeps basic feasibility/walk-away/whole-package discipline while personalizing other rules.
The application arm asks the learner to map the same principle to a separate fictional
everyday negotiation. Its answer includes the shared principle, not just a repeated rule.
This change follows the logged analogy literature and the v1 artifact's cash-specific
triggers. It uses no held-out outcomes.

Sim4 is now an analyst-built, locally frozen conditional-plan model; source documents
were not sent for parsing. Its full briefs and original text remain private. The public
manifest and numeric-only surrogate are in `results/ckpt3/heldout-case/`. The private case
hash is `2d339ecf290bdf6d868f85f220295195b58356a9657820fb51afd7bfc70f8c9e`.
Final live evaluation still needs explicit approval for sending role-appropriate briefs
to the Anthropic API. The frozen point assumptions must not be revised after observing
method performance.
