"""Fresh, bounded smoke evaluation of corrected learner semantics and coaching flow."""

from __future__ import annotations

import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic import BaseModel

from consolidation_ablate import source_hash
from negotrain.budget import SpendLedger
from negotrain.cases import load_case
from negotrain.evaluation import Experiment, write_json
from negotrain.learning import saved_parse
from negotrain.llm import ClaudeLLM
from negotrain.profiling.observations import ERRORS, observe
from negotrain.simulation import episode_score
from negotrain.virtual_users import LLMUser, VirtualTraits


class Comprehension(BaseModel):
    strongest_error_id: str
    behavioral_meaning: str


def main():
    root = Path("results/ckpt3/audit-corrected-smoke-v1")
    root.mkdir(parents=True, exist_ok=True)
    ledger = SpendLedger(".api-budget.sqlite3.ckpt3-dev")
    before = ledger.snapshot()
    learner = ClaudeLLM(model="claude-sonnet-5-5", effort="low", ledger=ledger)
    coach = ClaudeLLM(model="claude-opus-5-5", effort="low", ledger=ledger)
    case = load_case("data/cases/cloudline_hiring.json")
    config = {
        "source_sha256": source_hash(),
        "seed": 2822111702,
        "users": [0, 1],
        "scope": "Smoke test, not an efficacy or persona-calibration study",
        "learner_model": learner.model,
        "coach_model": coach.model,
        "design": "Six profile-comprehension checks; two baseline/debrief/post sequences",
        "old_controls_reused": False,
    }
    exp = Experiment(case, "candidate", root, config, coach, learner)
    checks, rows = [], []
    try:
        for index, key in enumerate(ERRORS):
            traits = VirtualTraits.sample(random.Random(100 + index))
            traits.errors = {k: 0.9 if k == key else 0.1 for k in ERRORS}
            actor = LLMUser(case, "candidate", traits, learner)
            answer = saved_parse(
                root / "raw" / f"comprehension{index}.json",
                learner,
                actor.system,
                [
                    {
                        "role": "user",
                        "content": "Instruction-comprehension check only: identify "
                        "your largest initial error tendency by ID and explain "
                        "its behavioral meaning. "
                        "Do not negotiate or repeat private role facts.",
                    }
                ],
                Comprehension,
                max_tokens=512,
            )
            checks.append(
                {
                    "expected": key,
                    "reported": answer.strongest_error_id,
                    "id_correct": answer.strongest_error_id == key,
                }
            )
        write_json(root / "comprehension_summary.json", checks)

        def run(uid):
            traits = VirtualTraits.sample(random.Random(config["seed"] + uid))
            target = ("error:1", "error:4")[uid]
            traits.errors = {k: 0.9 if k == target else 0.3 for k in ERRORS}
            original = traits.model_dump()
            seed = config["seed"] + uid * 1009
            baseline = exp.episode(f"learner{uid}_baseline", traits, 3, None, seed)
            feedback = exp.feedback(baseline)
            after = exp.episode(
                f"learner{uid}_after", traits, 3, None, seed, [feedback.report.model_dump_json()]
            )
            assert traits.model_dump() == original
            result = {
                "user": uid,
                "target": target,
                "baseline_R": episode_score(case, baseline),
                "post_R": episode_score(case, after),
                "baseline_status": baseline.status,
                "post_status": after.status,
                "baseline_counts": observe(baseline, case).model_dump(exclude={"score"}),
                "post_counts": observe(after, case).model_dump(exclude={"score"}),
            }
            write_json(root / f"user{uid}_summary.json", result)
            print(
                json.dumps({k: v for k, v in result.items() if not k.endswith("counts")}),
                flush=True,
            )
            return result

        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(run, [0, 1]))
        write_json(
            root / "summary.json",
            {
                "scope": config["scope"],
                "comprehension": checks,
                "rows": rows,
                "complete_episodes": 4,
                "no_trait_updates": True,
            },
        )
    finally:
        write_json(
            root / "usage.json",
            {
                "learner": learner.usage.snapshot(),
                "coach": coach.usage.snapshot(),
                "before": before,
                "after": ledger.snapshot(),
            },
        )


if __name__ == "__main__":
    main()
