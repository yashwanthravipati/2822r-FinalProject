# 0009: Few-interaction strategy memory and held-out transfer

- Status: proposed for team review; implementation/evaluation authorized by user
- Date: 2026-11-17
- Context: user requests stronger LLM learning within a few interactions, Sim4 held out,
  checkpoint-3 logs and regular pushes, and separate $100 development/final API caps.

## Decision

Keep the fixed economic controller, original persona parameters, and deterministic
surplus score. Change the representation and uptake of post-session teaching: conditional
strategy memory, with reflection-only and short application/correction variants. Compare
with accumulated debriefs at identical no-focus tiers (2,2,4,4,4). A generic strategy card
is a zero-shot reference. No model weights or persona probabilities are updated.

Train on Sim3 only. Freeze code, case projections, method configuration, and completed
memories before evaluating Sim4; baseline and post probes are isolated copies and never
feed back into training. Report paired user-level intervals, all failed requests, token
caching, API spending, and extra interaction/compute costs. Sim4 represents one held-out
scenario with inferred utility assumptions, not a population of independent cases.

## Rationale and limits

The previous uncertainty bonus tuned to zero, targeted-practice gains over untargeted
coaching were inconclusive, and error reduction did not align with scripted return.
Better teaching and consolidation are therefore a more direct next hypothesis than a
more elaborate focus-selection rule. GEPA, Reflexion, Self-Refine, and ACE motivate the
mechanism; none establishes its negotiation or human-transfer benefit. References and
formalism are in `logs/ckpt3-method-design.md`.

The application variant adds one learner interaction per rehearsal. Its effect is a
combined teaching intervention; it does not isolate reflection quality at equal compute.
The findings concern LLM agents with external memory, not durable human learning. Original
licensed materials and raw trajectories remain private. An automatic approval review
requires explicit authorization before role-appropriate Sim3/Sim4 content is sent to the
Anthropic API; code development and synthetic smoke testing proceed independently.
