"""Fresh controlled opportunities distinguish label comprehension from enactment."""

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
from negotrain.counterpart import TIERS
from negotrain.evaluation import write_json
from negotrain.llm import ClaudeLLM
from negotrain.profiling.observations import ERRORS, observe
from negotrain.profiling.tagging import tag_session
from negotrain.schemas import Case, Offer, Session, Turn, TurnTags
from negotrain.virtual_users import LLMUser, VirtualTraits
from persona_instructions import ENACTMENT, apply_enactment

VARIANTS = ("definitions", "enactment")
REPEATS = 4


def probe_case():
    labels = {
        "price": ["Low price", "Medium price", "High price"],
        "delivery": ["Fast delivery", "Standard delivery", "Slow delivery"],
        "support": ["Premium support", "Standard support", "Basic support"],
    }
    return Case.model_validate(
        {
            "id": "persona_control_probe",
            "title": "Fictional service agreement",
            "public_brief": "Negotiate price, delivery and support as one complete package. "
            "Each side has an alternative and may decline. All listed options are legal.",
            "source": "Original synthetic diagnostic; not a learning or transfer case.",
            "issues": [
                {
                    "id": k,
                    "name": k.title(),
                    "options": [{"id": str(i), "label": label} for i, label in enumerate(v)],
                }
                for k, v in labels.items()
            ],
            "roles": [
                {
                    "id": "buyer",
                    "name": "Buyer",
                    "confidential_brief": "You prefer low price, fast delivery and premium support."
                    " Your alternative is worth 25.",
                    "reservation_value": 25,
                    "points": {k: {"0": 100, "1": 50, "2": 0} for k in labels},
                },
                {
                    "id": "seller",
                    "name": "Seller",
                    "confidential_brief": "You prefer high price, fast delivery and basic support. "
                    "Your alternative is worth 100.",
                    "reservation_value": 100,
                    "points": {
                        "price": {"0": 0, "1": 50, "2": 100},
                        "delivery": {"0": 100, "1": 50, "2": 0},
                        "support": {"0": 0, "1": 50, "2": 100},
                    },
                },
            ],
        }
    )


def package(price, delivery, support):
    return Offer(terms={"price": str(price), "delivery": str(delivery), "support": str(support)})


def probe_prefix(case, target, key):
    session = Session(
        id=key,
        case_id=case.id,
        user_role_id="buyer",
        counterpart_role_id="seller",
        counterpart_profile=TIERS[3],
        seed=2822111801,
    )
    best, middle, demand = package(0, 0, 0), package(1, 0, 0), package(2, 0, 2)

    def add(speaker, text, offer):
        session.add_turn(
            Turn(
                index=len(session.turns),
                speaker=speaker,
                text=text,
                offer=offer,
                tags=TurnTags(source="scripted", raised_issues=["price"])
                if speaker == "user"
                else None,
            ),
            case,
        )

    if target in ("error:1", "error:2"):
        add("counterpart", "This is my opening package.", demand)
        add("user", "I propose this price and package.", best)
        add("counterpart", "I am holding my opening position; no concessions yet.", demand)
        if target == "error:2":
            add("user", "I can move on the price to help us get a deal.", middle)
            add("counterpart", "I have made no movement. My package is unchanged.", demand)
    elif target == "error:3":
        add(
            "counterpart",
            "Here is my opening package. Please make a complete counteroffer.",
            demand,
        )
    elif target == "error:4":
        add("user", "I propose this price and package.", best)
        add("counterpart", "Here is a complete offer. Can you accept it as-is?", package(1, 2, 2))
    elif target == "error:5":
        add("user", "The price is my focus. Here is my package.", middle)
        add(
            "counterpart",
            "We have one exchange left. Give me your final package and explanation.",
            demand,
        )
    elif target == "error:6":
        shared = package(1, 0, 1)
        add("user", "Here is a package I could work with.", shared)
        add(
            "counterpart",
            "Keeping price and support the same, I prefer fast delivery to standard, "
            "and standard to slow. Fast is better for us than either alternative. "
            "Please send your final complete proposal.",
            shared,
        )
    else:
        raise ValueError(target)
    return session


def run_probe(root, case, variant, target, level, repeat, llm):
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
        traits = VirtualTraits(
            errors={k: level if k == target else 0 for k in ERRORS},
            awareness=0.5,
            rapport=0.5,
            response={k: 0 for k in ERRORS},
        )
        actor = LLMUser(case, "buyer", traits, llm, feedback=[], focus=None)
        if variant == "enactment":
            apply_enactment(actor)
        session.add_turn(actor.respond(session), case)
        write_json(path, {"complete": False, "session": session.model_dump(mode="json")})
    decision = session.turns[prior_length]
    if not complete and target == "error:5":
        # Close the deliberately one-exchange diagnostic, then measure whole-prefix issue use.
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


def summarize(rows):
    expected = {
        (v, k, p, r) for v in VARIANTS for k in ERRORS for p in (0.1, 0.9) for r in range(REPEATS)
    }
    actual = {(r["variant"], r["target"], r["level"], r["repeat"]) for r in rows}
    if actual != expected or len(rows) != len(expected):
        raise ValueError("Incomplete or duplicate diagnostic cohort")
    variants = {}
    for variant in VARIANTS:
        groups = []
        for target in ERRORS:
            levels = {}
            for level in (0.1, 0.9):
                selected = [
                    r
                    for r in rows
                    if r["variant"] == variant and r["target"] == target and r["level"] == level
                ]
                opps = sum(r["opportunities"] for r in selected)
                occs = sum(r["occurrences"] for r in selected)
                levels[str(level)] = {
                    "n": len(selected),
                    "events": sum(r["event"] for r in selected),
                    "opportunities": opps,
                    "occurrences": occs,
                    "conditional_rate": occs / opps if opps else None,
                }
            passed = levels["0.1"]["events"] <= 1 and levels["0.9"]["events"] >= 3
            groups.append({"target": target, "levels": levels, "screen_pass": passed})
        variants[variant] = {
            "weaknesses": groups,
            "all_six_pass": all(g["screen_pass"] for g in groups),
        }
    return {
        "complete_probes": len(rows),
        "variants": variants,
        "scope": "Controlled one-decision diagnostic, not training or full-session validation",
    }


def main():
    root = Path("results/ckpt3/persona-probes-v1")
    case = probe_case()
    protocol = {
        "core_sha256": source_hash(),
        "case_sha256": hashlib.sha256(case.model_dump_json().encode()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "enactment_sha256": hashlib.sha256(ENACTMENT.encode()).hexdigest(),
        "helper_sha256": hashlib.sha256(
            Path("scripts/persona_instructions.py").read_bytes()
        ).hexdigest(),
        "variants": list(VARIANTS),
        "repeats": REPEATS,
        "other_errors": 0,
        "target_levels": [0.1, 0.9],
        "seed": 2822111801,
        "expected_probes": 96,
        "model": "claude-sonnet-5-5",
        "effort": "low",
        "gate": "Each of six targets: high has at least 3/4 events; low at most 1/4",
        "primary": "target event at controlled response, including zero on no formal event",
        "secondary": "numeric detector opportunities; undefined with zero opportunities",
        "limits": "Authored prefixes; one decision; isolated traits; unseeded LLM; no coaching",
        "sim4_used": False,
        "cedar_used": False,
    }
    frozen_json(root / "protocol.json", protocol)
    ledger = SpendLedger(".api-budget.sqlite3.ckpt3-dev")
    llm = ClaudeLLM(model=protocol["model"], effort="low", ledger=ledger)
    attempt = len(list(root.glob("usage_*.json")))
    before = ledger.snapshot()
    jobs = [
        (v, k, p, r) for v in VARIANTS for k in ERRORS for p in (0.1, 0.9) for r in range(REPEATS)
    ]
    random.Random(protocol["seed"]).shuffle(jobs)
    rows, failures = [], []
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(run_probe, root, case, *job, llm): job for job in jobs}
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
