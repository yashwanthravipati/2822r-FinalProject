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
