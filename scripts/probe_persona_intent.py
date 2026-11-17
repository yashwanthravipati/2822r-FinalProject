"""Test explicit private intent on fresh isolated controlled opportunities."""

from __future__ import annotations

import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from consolidation_ablate import source_hash
from consolidation_evaluate import frozen_json
from negotrain.budget import SpendLedger
from negotrain.evaluation import write_json
from negotrain.llm import ClaudeLLM
from negotrain.profiling.observations import ERRORS
from persona_decision import IntentLLM
from probe_isolated_personas import run
from probe_persona_controls import REPEATS, probe_case


def summarize_intent(rows):
    expected = {(k, p, r) for k in ERRORS for p in (0.1, 0.9) for r in range(REPEATS)}
    actual = {(r["target"], r["level"], r["repeat"]) for r in rows}
    if actual != expected or len(rows) != len(expected):
        raise ValueError("Incomplete or duplicate intent cohort")
    assert all(r["variant"] == "enactment" for r in rows)
    groups = []
    for target in ERRORS:
        levels = {}
        for level in (0.1, 0.9):
            selected = [r for r in rows if r["target"] == target and r["level"] == level]
            opps, occs = (sum(r[k] for r in selected) for k in ("opportunities", "occurrences"))
            levels[str(level)] = {
                "n": len(selected),
                "events": sum(r["event"] for r in selected),
                "opportunities": opps,
                "occurrences": occs,
                "conditional_rate": occs / opps if opps else None,
            }
        groups.append(
            {
                "target": target,
                "levels": levels,
                "screen_pass": levels["0.1"]["events"] <= 1 and levels["0.9"]["events"] >= 3,
            }
        )
    return {
        "complete_probes": len(rows),
        "weaknesses": groups,
        "all_six_pass": all(g["screen_pass"] for g in groups),
        "scope": "Concrete enactment plus private intent, controlled one-decision diagnostic",
    }


def main():
    root = Path("results/ckpt3/persona-probes-v3")
    case = probe_case()
    names = (
        "probe_persona_intent.py",
        "persona_decision.py",
        "probe_isolated_personas.py",
        "probe_persona_controls.py",
        "persona_instructions.py",
    )
    protocol = {
        "kind": "private_intent",
        "core_sha256": source_hash(),
        "case_sha256": hashlib.sha256(case.model_dump_json().encode()).hexdigest(),
        "sources": {
            n: hashlib.sha256((Path("scripts") / n).read_bytes()).hexdigest() for n in names
        },
        "expected_probes": 48,
        "repeats": REPEATS,
        "target_levels": [0.1, 0.9],
        "other_errors": "unspecified",
        "seed": 2822111803,
        "model": "claude-sonnet-5-5",
        "effort": "low",
        "gate": "Each of six targets: high has at least 3/4 events; low at most 1/4",
        "change": "Require private intent and one-sentence effect before action",
        "primary": "Observed action event, never the model's claimed intent",
        "no_coaching": True,
        "sim4_used": False,
        "cedar_used": False,
    }
    frozen_json(root / "protocol.json", protocol)
    ledger = SpendLedger(".api-budget.sqlite3.ckpt3-dev")
    llm = ClaudeLLM(model=protocol["model"], effort="low", ledger=ledger)
    before = ledger.snapshot()
    attempt = len(list(root.glob("usage_*.json")))
    jobs = [(k, p, r) for k in ERRORS for p in (0.1, 0.9) for r in range(REPEATS)]
    random.Random(protocol["seed"]).shuffle(jobs)

    def one(job):
        wrapped = IntentLLM(llm)
        key = f"enactment_{job[0].replace(':', '')}_{job[1]}_{job[2]}"
        try:
            return run(root, case, "enactment", *job, wrapped)
        finally:
            if wrapped.notes:
                write_json(root / "raw" / "intent" / f"{key}.json", wrapped.notes)

    rows, failures = [], []
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(one, job): job for job in jobs}
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
        write_json(root / "summary.json", summarize_intent(rows))
    finally:
        write_json(
            root / f"usage_{attempt}.json",
            {"before": before, "after": ledger.snapshot(), "learner": llm.usage.snapshot()},
        )


if __name__ == "__main__":
    main()
