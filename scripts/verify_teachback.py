"""Verify teach-back provenance before the unchanged complete-outcome audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from analyze_consolidation import main as audit
from consolidation_ablate import check_frozen, read
from consolidation_evaluate import digest
from teachback_memory import Answer, corrections


def verify(root):
    protocol, _ = check_frozen(root)
    for key, filename in (
        ("teachback_source_sha256", "teachback_evaluate.py"),
        ("teachback_memory_sha256", "teachback_memory.py"),
    ):
        if digest(Path("scripts") / filename) != protocol[key]:
            raise ValueError("teach-back source changed")
    source = Path(protocol["source_root"])
    for uid in protocol["users"]:
        data = read(root / "raw" / f"learner{uid}.memories.json")
        original = read(source / "raw" / f"learner{uid}.memories.json")["memories"]["reports"]
        if data["memories"]["reports"] != original:
            raise ValueError("control reports changed")
        memory = data["memories"]["teachback_reports"]
        if len(memory) != 1 or not memory[0].endswith("\n\n".join(original)):
            raise ValueError("teach-back dropped original reports")
        recorded = data["teachback_examples"]
        expected = corrections(
            [r["comparison"] for r in recorded],
            [Answer.model_validate(r["answer"]) for r in recorded],
        )
        if recorded != expected:
            raise ValueError("arithmetic corrections changed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args, _ = parser.parse_known_args()
    verify(args.root)
    audit()
