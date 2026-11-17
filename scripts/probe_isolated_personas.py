"""Repeat controlled diagnostics with non-target traits unspecified, not forbidden."""

from __future__ import annotations

import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from consolidation_ablate import source_hash
from consolidation_evaluate import frozen_json
from negotrain.budget import SpendLedger
from negotrain.cases.offers import points
from negotrain.evaluation import write_json
from negotrain.llm import ClaudeLLM
from negotrain.profiling.observations import ERRORS, observe
from negotrain.profiling.tagging import tag_session
from negotrain.schemas import Session, Turn
from negotrain.virtual_users import LLMUser, VirtualTraits
from persona_instructions import apply_enactment
from probe_persona_controls import REPEATS, VARIANTS, probe_case, probe_prefix, summarize

SCOPE = "\nOnly the named tendency supplied in initial_tendencies has a specified frequency. "
SCOPE += "Other tendencies are unspecified, not zero. Do not infer frequency settings for them. "
SCOPE += "If behavioral definitions overlap, that does not prohibit the supplied habit.\n"


def actor_for(case, target, level, variant, llm):
    traits = VirtualTraits(errors={target: level}, awareness=0.5, rapport=0.5, response={})
    actor = LLMUser(case, "buyer", traits, llm, feedback=[], focus=None)
    if variant == "enactment":
        apply_enactment(actor)
    actor.system = actor.system.append_uncached(SCOPE)
    return actor


def run(root, case, variant, target, level, repeat, llm):
    key = f"{variant}_{target.replace(':', '')}_{level}_{repeat}"
    path = root / "raw" / f"{key}.json"
    session = probe_prefix(case, target, key)
    before = observe(session, case).counts[target]
    prior_length = len(session.turns)
    complete = False
    if path.exists():
        saved = json.loads(path.read_text())
        session = Session.model_validate(saved["session"])
        complete = saved["complete"]
    else:
        actor = actor_for(case, target, level, variant, llm)
        session.add_turn(actor.respond(session), case)
        write_json(path, {"complete": False, "session": session.model_dump(mode="json")})
    decision = session.turns[prior_length]
    if not complete and target == "error:5":
        if session.status == "active":
            offer = session.latest_offer_from("user")
            accept = offer is not None and points(case, "seller", offer) >= 100
            session.add_turn(
                Turn(
                    index=len(session.turns),
                    speaker="counterpart",
                    text="This diagnostic exchange is over.",
                    accept=accept,
                    walk_away=not accept,
                ),
                case,
            )
        tag_session(session, case, llm)
    after = observe(session, case).counts[target]
    write_json(path, {"complete": True, "session": session.model_dump(mode="json")})
    return {
        "id": key,
        "variant": variant,
        "target": target,
        "level": level,
        "repeat": repeat,
        "event": after.occurrences > before.occurrences,
        "opportunities": after.opportunities - before.opportunities,
        "occurrences": after.occurrences - before.occurrences,
        "offered": decision.offer is not None,
        "accepted": decision.accept,
        "walked": decision.walk_away,
    }


def main():
    root = Path("results/ckpt3/persona-probes-v2")
    case = probe_case()
    sources = [
        Path(__file__),
        Path("scripts/probe_persona_controls.py"),
        Path("scripts/persona_instructions.py"),
    ]
    protocol = {
        "core_sha256": source_hash(),
        "case_sha256": hashlib.sha256(case.model_dump_json().encode()).hexdigest(),
        "sources": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "variants": list(VARIANTS),
        "repeats": REPEATS,
        "expected_probes": 96,
        "other_errors": "unspecified; omitted from the actor payload",
        "target_levels": [0.1, 0.9],
        "seed": 2822111802,
        "model": "claude-sonnet-5-5",
        "effort": "low",
        "gate": "Each of six targets: high has at least 3/4 events; low at most 1/4",
        "change_from_v1": "Omit non-target frequencies and explicitly state they are unspecified",
        "primary": "Target event at controlled response, including zero on no formal event",
        "limits": "One decision, four draws, authored prefixes; no full-session or learning claim",
        "sim4_used": False,
        "cedar_used": False,
    }
    frozen_json(root / "protocol.json", protocol)
    ledger = SpendLedger(".api-budget.sqlite3.ckpt3-dev")
    llm = ClaudeLLM(model=protocol["model"], effort="low", ledger=ledger)
    before = ledger.snapshot()
    attempt = len(list(root.glob("usage_*.json")))
    jobs = [
        (v, k, p, r) for v in VARIANTS for k in ERRORS for p in (0.1, 0.9) for r in range(REPEATS)
    ]
    random.Random(protocol["seed"]).shuffle(jobs)
    rows, failures = [], []
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(run, root, case, *job, llm): job for job in jobs}
            for future in as_completed(futures):
                try:
                    row = future.result()
                    rows.append(row)
                    write_json(root / "rows.json", sorted(rows, key=lambda r: r["id"]))
                    print(json.dumps({"complete": len(rows), "id": row["id"]}), flush=True)
                except Exception as exc:
                    failures.append({"job": futures[future], "exception": type(exc).__name__})
                    write_json(root / "failures.json", failures)
        if failures:
            raise RuntimeError(f"{len(failures)} failed probes")
        write_json(root / "summary.json", summarize(rows))
    finally:
        write_json(
            root / f"usage_{attempt}.json",
            {"before": before, "after": ledger.snapshot(), "learner": llm.usage.snapshot()},
        )


if __name__ == "__main__":
    main()
