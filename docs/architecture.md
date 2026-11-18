# Architecture

The application reuses upload → prepare → rehearse → feedback → profile → real-outcome.
Report Section 1 and decision 0009 define the current rubric framework. The earlier
point-based implementation and experiments remain available for reproducibility; their
contracts are documented below under “Legacy bargaining path”.

## Current rubric framework

`Case.framework_version="rubric-v1"` selects the current path. `negotiation_type` selects
distributive, integrative, or institutional teaching priorities. New document imports use
this path. Choosing “Start training” on a saved case enables it; legacy case files and
sessions still load. `scripts/migrate_rubric.py` creates a separate private practice case
when retaining the original case id is important for reproducing experiments.

`rubrics.py` supplies the six shared skills, with profile-specific default priorities and
editable applicability, importance, anchors, preparation guidance, and steering instructions.
Defaults are explicitly unreviewed. `Case.rubric` is public instructional material;
confidential examples belong in `RoleSheet.skill_notes`. `role_context` projects only the
selected role, visible source documents, public issues, and rubric. The parser must not
put private facts in shared issues, the public brief, or outcome criteria.

Institutional cases disable numeric scoring. Other cases can retain it only with supplied
point tables and reservation values. Role sheets allow missing numeric values; scoring
returns null, never a fabricated zero, for unscored cases. Constraints retain provenance,
uncertainty, and approval dependencies. Known option restrictions are checked in code;
narrative constraints and outcome criteria are marked for review rather than automatically
certified. `Session.commitments` records partial agreements, required approvals, timing,
owners and contingencies. Participant-recorded commitments do not verify delivery. The
existing `impasse` status means no full formal agreement and can coexist with next steps.

## Assessment and Beta beliefs

`profiling/skills.py` assesses each learner response using only its transcript prefix and
role-visible information, at most one model call per learner turn. `SkillObservation`
contains a skill id, opportunity window, present/absent/uncertain opportunity label,
continuous effectiveness score in [0,1] or null, exact evidence quotations, rationale,
practice suggestion, and subskill tags. Zero means missed; one means effective. Scores
between them are partial effectiveness, not annotation confidence or a third category.
Unassessable, absent and uncertain opportunities do not receive scores.

Validation rejects unknown/duplicate skills, future evidence, unsupported quotations,
wrong response turns, and stale case/role/transcript hashes. Formal actions have canonical
visible evidence text even when the message is empty. A model batch covers every applicable
skill at the requested response. Assessments are saved atomically only after every batch
validates. Human annotations use the same contract and can be imported/exported on Feedback.
Overlapping windows within a skill are counted once (earliest assessable observation);
different skills may refer to the same response.

`BetaBelief.update(v,n,lambda)` retains the prior and discounts old evidence, adding total
score v to alpha and n-v to beta. Fractional evidence is an approximation, not an exact
continuous-data conjugate likelihood. Effectiveness is alpha/(alpha+beta). Profiles keep
case, role and difficulty separate; they do not infer learning from a shift to easier
practice or claim cross-case transfer. Missing annotations add no success/failure evidence.
The UI shows opportunity counts, effectiveness and model intervals, whose empirical
calibration remains untested. No Dirichlet model or discrete three-level state is used.

## Coaching and steering

`curriculum.next_scenario` uses the relevant Beta skill beliefs, rubric importance and
uncertainty to choose an applicable focus. Difficulty stays fixed unless the user chooses
a different tier or a planned stretch session; no agreement does not automatically imply
weak performance. Fixed-difficulty comparisons avoid conflating difficulty with learning.

The AI counterpart receives its own role and focus instructions. It can converse without
being forced to emit a numerical counteroffer. Difficulty adjusts how much probing is
needed while preserving facts and authority. The six focus instructions exercise rapport,
interests/authority, evidence, leverage, options, and commitments; there are no automatic
concessions for rapport keywords. Specified numeric constraints still apply to scored cases.
Offline institutional rehearsals are a clearly labeled placeholder, not a realistic actor
or an assessor. AI behavior control and factual fidelity still require empirical testing.

Rubric feedback presents validated observations, evidence and suggestions. Skill scores,
mechanical constraint checks and recorded outcomes remain separate. It never substitutes
old concession flags or numeric counterfactual gains. Cached point-based debriefs are not
used for the new rubric view. The assistant retains its factual-only restriction during
active rehearsal. Inferred point tables are excluded from unscored role prompts.

## Component evaluation

`rubric_evaluation.py` compares predictions with validated human reference annotations:
opportunity and thresholded-weakness precision/recall, continuous-score MAE, and coverage.
Missing predictions are abstentions, not zero scores. Conversation ids cannot cross dataset
splits. `steering_responses` generates counterpart turns for unchanged dialogue prefixes;
it does not simulate learner improvement. Human steering annotations measure opportunity
creation, case adherence and unintended changes; separate human feedback ratings measure
correctness, relevance, actionability and grounding.

Run `python scripts/evaluate_rubric.py INPUT.json --output OUTPUT.json` to compute metrics
without API calls. The input may contain `diagnosis` (ReferenceExample), `steering`
(SteeringRating), and `feedback` (FeedbackRating) lists. ReferenceExample includes a case,
session, human reference assessment and optional prediction. Keep cases/transcripts and
annotation files in private data folders. Empty datasets return missing metrics, never a
validation claim. Reference quality, annotator agreement, confidence calibration, steering
quality and human learning remain unmeasured until real annotation/study data are collected.

## Legacy bargaining path

The following describes the pre-rubric implementation used by the historical experiments.
It does not define the new institutional assessment path. `docs/new-spec.md` is retained as
its historical specification; `evaluation.Experiment` requires a scored legacy case.

## Case, visibility, and reward

`schemas.Case` contains public issues/options, two private role sheets, and optionally
role-projected source documents. `cases/parser.py` reads PDF, Word, text, and ZIP uploads;
missing counterpart sheets are labeled inferred. Private uploads, originals, transcripts,
and participant records stay in gitignored directories. `data/cases/sim3/` is likewise
ignored because it contains the supplied class materials.

Scoring is deterministic. `cases/offers.feasible_best_points` computes the exact maximum
user utility among packages satisfying the counterpart walk-away and hard constraints,
using an additive Pareto frontier. `surplus_share` computes R without clipping negative
values; a nonpositive denominator is explicitly unsupported. `simulation.episode_score`
returns zero for no deal and null for an unscored custom agreement. Standing offers have
no terminal value. Partial offers cannot establish numeric detector opportunities.

The counterpart LLM sees public material, its own sheet, and visible dialogue. The prep
and assistant see the user's own sheet and role-authorized sources. Both sheets may be
used in post-session feedback; alternatives that use private information are labeled
hindsight. During an active rehearsal the assistant is restricted to factual clarification;
move suggestions and counterfactual coaching are available before/after rehearsal.

## Counterpart and session

`counterpart/profiles.py` defines five fixed tiers with independent opening, concession
rate, and floor fractions of P_C_max-W_C. `aspiration.py` computes the current minimum
from the transcript and seed, with extra deadline pressure. The session ends after at
most 20 user moves and their counterpart responses, or earlier at acceptance/walk-away.
The UI displays remaining user moves. Tier 5 recommendations require two strong tier-4
sessions; participants may still explicitly select a tier.

`RuleBasedCounterpart` chooses formal actions in code. In the default hybrid path,
`CounterpartAgent` uses the same formal policy and asks Claude only for the corresponding
in-character text. Its model cannot replace an offer or acceptance. The prompt-only
comparison and sessions involving custom terms retain qualitative LLM action generation,
with validation/retries. Custom terms have no numeric score or schedule guarantee.

Focus labels act through the single `FOCUS_DIALS` table and explicit hooks: delayed first
concession; seeded withholding of reciprocity; extreme opening; early low-surplus offer
held for two turns; a fixed least-preferred issue option; two early packages; disclosure
when asked; and a doubled concession step after rapport-tagged moves. A package hook
that is incompatible with the economic constraints falls back to an ordinary feasible
move and records `Turn.hook_applied=False`, rather than violating a walk-away value.

Shared additive fields are `Turn.tags` (with annotation provenance), `Turn.hook_applied`,
`Session.seed`, `Session.max_user_turns`, and counterpart `focus`, `focus_issue`, and
`concession_floor`. Existing sessions load with defaults. Formal moves permit at most
one offer/accept/walk-away, validated before transcript mutation.

## Observations, belief, and planning

`profiling/observations.py` implements the six specified opportunity/occurrence detectors.
Case-scoped fact rubrics use public issues and the user's own sheet, without exposing the
other sheet. `profiling/tagging.py` sends a fixed rubric to the LLM and validates all tags
before applying the batch. Missing tags are missing data; they do not count as failed
rapport or awareness. An unvaried issue is counted as ignored only with complete message
annotation. The app annotates a finished session before feedback, and annotates ongoing
user text only when the rapport hook needs it. No coaching is generated by the tagger.

`profiling/belief.py` maintains Beta distributions, discounting evidence once per session
while preserving the prior by default. `discount_prior=True` preserves the original proposal's alternative recursion for sensitivity analysis. Exact credible intervals use SciPy.
`profile.py` rebuilds beliefs from persisted transcripts and estimates personal error
costs from fresh-batch counterfactual deltas, falling back to population costs. Before
calibration, fallback cost/opportunity values are unit priors, not measured estimates.

The planner chooses maximum w*o_bar*(mean+kappa*sd), using 1-mean for facts and rapport.
Greedy, seeded random, and no-focus alternatives use the same interface. The app displays
probabilities, credible intervals, and opportunity counts, and includes a focus callout
in preparation. All five preparation-plan steps carry the current focus; the final
step also adapts tier. The old six heuristic skill scores are removed. Behavioral summary
features remain available for descriptive outcome and sim-to-real comparisons.

## Counterfactual feedback

`feedback/critical.py` identifies every formal user action and detector firing, then
orders moments by the selected focus. Optional caps are explicit. `rollouts.py` restores
the full prefix, setting, tags, deadline, and counterpart seed. The rollout user is a
scripted policy with prefix-derived concession pace and seeded ±2.5% aspiration noise.
It never fits its behavior on future transcript turns. Every rollout continues to an
actual terminal outcome against the selected counterpart, without a substitute tail.

One M-rollout batch (default M=4) selects a candidate, and a disjoint M-rollout batch
scores the selected and actual actions. Common random numbers pair those fresh runs.
Delta and its paired bootstrap interval use only the fresh scores; negative deltas are
retained. Failed rollouts fail the estimate instead of silently biasing its sample.
Small-M intervals are exploratory. Reports persist seeds, policy, reward units, hindsight
labels, and actual outcomes. Older raw-point reports require regeneration before reuse.

`coaching.py` leads with focus-related observed moments and supplies the exact counts
and credit estimates to the LLM. Template feedback uses the same observations. Numeric
feedback refuses active sessions and skips custom-term sessions. `SessionStore` saves
transcripts and debrief artifacts; the profile feeds saved personal credit back to UCB.

## Evaluation and budget

The API gateway remains `negotrain.llm`; offline tests inject `ScriptedLLM`.
`budget.py` reserves a conservative full-context/output cost in a shared SQLite ledger
before each request. Successful usage settles the charge; uncertain failures retain the
reserve. SDK retries and automatic model fallback are disabled. Structured responses settle usage
before JSON validation; a known truncation permits one separately reserved retry. The persistent cap is
$200 for this user-authorized evaluation across processes and restarts. New ledgers
default to $150; an explicit audited cap change preserves all existing reservations.
Ordinary reopening preserves the persisted cap. The ledger and all credentials stay out of git.

`scripts/evaluate.py` runs independent calibration, development, and test populations.
Exact Binomial-oracle results test the mathematical model; grounded transcript results
measure realized detector rates and held-out no-focus competence G. These are separate
experiments: policy propensities are not asserted to equal conditional error rates.
LLM personas receive role-projected case materials, pre-session focus callouts, and prior
post-session feedback; their states are not manually improved by the synthetic Learn map.
Independent users may run concurrently; requests wait for active budget reservations to
settle when that can free enough capacity, while unknown charges stay reserved. Static
role/persona prompts have explicit cache breakpoints. Each user can be recovered separately
without resampling, and failure tracebacks remain private. Per-turn checkpoints make interrupted episodes
resumable, and user-level paired bootstrap intervals preserve sampling dependence.

`results/calibration/` holds population costs and tuned lambda/kappa, matched by full case
hash and role before the app loads them. Calibration from another upload is never reused.
Before calibration, the app retains explicitly uncalibrated unit priors. Private raw
transcripts stay in ignored `results/**/raw/`; public outputs contain numeric metrics only.
Human transfer, human-like concession curves, and teammate tagging agreement require human
data and must not be asserted from simulations. See the sim3 results for measured limits.
