"""Independently check controlled diagnostic outcomes and frozen provenance."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

from consolidation_ablate import source_hash
from negotrain.evaluation import write_json
from negotrain.schemas import Session
from probe_persona_controls import probe_case, probe_prefix, summarize
from probe_persona_intent import summarize_intent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root):
    protocol = json.loads((root / "protocol.json").read_text())
    assert source_hash() == protocol["core_sha256"]
    if "sources" in protocol:
        expected = {
            "probe_isolated_personas.py",
            "probe_persona_controls.py",
            "persona_instructions.py",
        }
        if protocol.get("kind") == "private_intent":
            expected |= {"probe_persona_intent.py", "persona_decision.py"}
        assert set(protocol["sources"]) == expected
        for name, sha in protocol["sources"].items():
            assert digest(Path("scripts") / name) == sha
    else:
        assert digest(Path("scripts/probe_persona_controls.py")) == protocol["runner_sha256"]
        assert digest(Path("scripts/persona_instructions.py")) == protocol["helper_sha256"]
    rows = json.loads((root / "rows.json").read_text())
    summary = (
        summarize_intent(rows) if protocol.get("kind") == "private_intent" else summarize(rows)
    )
    assert summary == json.loads((root / "summary.json").read_text())
    assert len(list((root / "raw").glob("*.json"))) == len(rows) == protocol["expected_probes"]
    case = probe_case()
    assert hashlib.sha256(case.model_dump_json().encode()).hexdigest() == protocol["case_sha256"]

    def value(role, offer):
        return sum(case.role(role).points[k][v] for k, v in offer.terms.items())

    offers = [
        dict(zip([i.id for i in case.issues], options, strict=True))
        for options in itertools.product(*(i.option_ids() for i in case.issues))
    ]
    best = max(
        sum(case.role("buyer").points[k][v] for k, v in o.items())
        for o in offers
        if sum(case.role("seller").points[k][v] for k, v in o.items()) >= 100
    )
    receipts = []
    for row in rows:
        path = root / "raw" / f"{row['id']}.json"
        raw = json.loads(path.read_text())
        assert raw["complete"]
        session = Session.model_validate(raw["session"])
        prefix = probe_prefix(case, row["target"], row["id"])
        n = len(prefix.turns)
        for actual, expected in zip(session.turns[:n], prefix.turns, strict=True):
            # Annotation may replace the authored tags, but not the dialogue/actions.
            assert actual.model_dump(exclude={"created_at", "tags"}) == expected.model_dump(
                exclude={"created_at", "tags"}
            )
        decision = session.turns[n]
        assert decision.speaker == "user"
        for turn in session.turns[n:]:
            prefix.add_turn(turn, case)
        offer = decision.offer
        target = row["target"]
        if target in ("error:1", "error:2"):
            prior = next(
                t.offer for t in reversed(session.turns[:n]) if t.speaker == "user" and t.offer
            )
            event = offer is not None and value("buyer", offer) < value("buyer", prior)
        elif target == "error:3":
            event = offer is not None and value("buyer", offer) < (100 + best) / 2
        elif target == "error:4":
            event = decision.accept and (50 - 25) / (best - 25) < 0.25
        elif target == "error:5":
            user = [t for t in session.turns if t.speaker == "user"]
            assert all(t.tags is not None for t in user)
            used = set().union(*(set(t.tags.raised_issues) for t in user))
            event = any(
                i.id not in used and len({t.offer.terms[i.id] for t in user if t.offer}) <= 1
                for i in case.issues
            )
        else:
            earlier = [t.offer for t in session.turns[:n] if t.offer]
            event = offer is not None and any(
                value("buyer", o) >= value("buyer", offer)
                and value("seller", o) >= value("seller", offer)
                and (
                    value("buyer", o) > value("buyer", offer)
                    or value("seller", o) > value("seller", offer)
                )
                for o in earlier
            )
        assert event == row["event"], row["id"]
        receipts.append({"id": row["id"], "event": event, "sha256": digest(path)})
    usage = [json.loads(p.read_text()) for p in root.glob("usage_*.json")]
    result = {
        "verified_probes": len(rows),
        "independent_feasible_max": best,
        "ledger_cost_usd": sum(u["after"]["actual_usd"] - u["before"]["actual_usd"] for u in usage),
        "requests": sum(u["after"]["requests"] - u["before"]["requests"] for u in usage),
        "core_sha256": source_hash(),
        "verified_events": receipts,
    }
    write_json(root / "verification.json", result)
    return {k: v for k, v in result.items() if k != "verified_events"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("results/ckpt3/persona-probes-v1"))
    print(json.dumps(verify(parser.parse_args().root), indent=2))
