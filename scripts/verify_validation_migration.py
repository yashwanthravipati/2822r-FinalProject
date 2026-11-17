"""Check that stricter case validation preserves every recorded offer's score."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from consolidation_ablate import source_hash
from consolidation_evaluate import frozen_json
from negotrain.cases import load_case
from negotrain.cases.scoring import score_offer
from negotrain.evaluation import write_json
from negotrain.schemas import Session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    root = Path("results/ckpt3/persona-calibration-v1")
    cases = {c.id: c for c in (load_case(p) for p in Path("data/cases").glob("*.json"))}
    scores = []
    paths = sorted((root / "raw").glob("*.json"))
    assert len(paths) == 48, "Complete live cohort required"
    for path in paths:
        raw = json.loads(path.read_text())
        assert raw["complete"]
        session = Session.model_validate(raw["session"])
        case = cases[session.case_id]
        for turn in session.turns:
            if turn.offer:
                scores.append(
                    [
                        session.id,
                        turn.index,
                        [score_offer(case, r.id, turn.offer).model_dump() for r in case.roles],
                    ]
                )
    observed = {
        "case_hashes": {
            k: hashlib.sha256(c.model_dump_json().encode()).hexdigest()
            for k, c in sorted(cases.items())
        },
        "scored_offers": len(scores),
        "episodes": len(paths),
        "score_digest": hashlib.sha256(json.dumps(scores, sort_keys=True).encode()).hexdigest(),
    }
    reference = root / "validation_reference.json"
    if args.capture:
        frozen_json(reference, {"source_sha256": source_hash(), "observed": observed})
    else:
        before = json.loads(reference.read_text())
        assert observed == before["observed"], (
            "Stricter validation changed recorded cases or scores"
        )
        write_json(
            root / "validation_recheck.json",
            {
                "reference_source_sha256": before["source_sha256"],
                "current_source_sha256": source_hash(),
                "cases_and_scores_unchanged": True,
                **observed,
            },
        )
    print(json.dumps({"episodes": len(paths), "offers": len(scores), "capture": args.capture}))


if __name__ == "__main__":
    main()
