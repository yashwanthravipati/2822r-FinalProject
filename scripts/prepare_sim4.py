"""Prepare Sim4 with public-only counterpart inference; requires case/API authorization."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from negotrain.budget import SpendLedger
from negotrain.cases.documents import extract_documents
from negotrain.cases.offers import feasible_best_points, space_size
from negotrain.cases.parser import SYSTEM, ParsedCase, ParsedRole, to_case
from negotrain.evaluation import write_json
from negotrain.learning import saved_parse
from negotrain.llm import ClaudeLLM
from negotrain.schemas import Constraint, RoleSheet, SourceDocument

PUBLIC = """Construct a finite case for Global Relief (id global_relief, user) negotiating
with Red Cross Alpha (id rc_alpha, counterpart). Use ONLY these shared documents. Use six
issues with three meaningful options each. Cover referral selection/oversight, resources,
implementation and safeguards. Neither private role sheet is supplied in this call.
All points and walk-away values are inferred EXPERIMENTAL organizational preferences,
not official grading, patient welfare or clinical values. State this in scoring_notes.
Preserve mandatory constraints and distinguish permissions, protections and consent.
Do not grant an NGO powers to override government/security rules. Use some opposed
priorities and mutually acceptable packages. Treat disputed reports as uncertain. The
public brief must contain shared information only. Mark both inferred=true; Global
Relief's sheet will be replaced in a separate call using its actual private documents.
"""
OWN = """Construct ONLY Global Relief's role sheet, id global_relief, from its own and
shared documents. Use the fixed issue/option IDs exactly. Give points for every option
and a walk-away value on the same scale. These scores are inferred EXPERIMENTAL
preferences, not official grading or clinical valuations; say so in the private brief.
Do not infer or describe hidden counterpart preferences. Preserve working through
RC-Alpha, neutrality and local trust, clinical prioritization and informed consent.
Distinguish permission from protection; do not promise unverified capacity or guarantees.
Ban options that violate mandatory constraints. Keep contested claims uncertain.
Preserve useful specifics in the private brief. Set inferred=false because the actual
role card is supplied, while explicitly labeling numeric scores as assumptions.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/cases/sim4"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/cases/private/sim4_inferred.json")
    )
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Sim4 already exists; audit/reuse it rather than regenerate.")
    files = sorted(p for p in args.source.rglob("*") if p.suffix in (".docx", ".md"))
    uploads = [(str(p.relative_to(args.source)), p.read_bytes()) for p in files]
    documents, warnings = extract_documents(uploads)
    if warnings or not documents:
        raise ValueError(warnings or "no source documents")
    shared = {k: v for k, v in documents.items() if k.startswith("shared-docs/")}
    private = {k: v for k, v in documents.items() if k not in shared}
    client = ClaudeLLM(effort="low", ledger=SpendLedger(".api-budget.sqlite3.ckpt3-dev", 100))
    root = args.output.parent / "sim4-build"
    parsed = saved_parse(
        root / "public.json",
        client,
        SYSTEM + "\n" + PUBLIC,
        [{"role": "user", "content": json.dumps(shared)}],
        ParsedCase,
        max_tokens=12000,
    )
    case = to_case(parsed, source="Sim4 inferred experimental utilities; not official scores.")
    if {r.id for r in case.roles} != {"global_relief", "rc_alpha"} or space_size(case) > 729:
        raise ValueError("unexpected role IDs or issue space")
    own = saved_parse(
        root / "own.json",
        client,
        OWN,
        [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "issues": [i.model_dump() for i in case.issues],
                        "public_sources": shared,
                        "private_sources": private,
                    }
                ),
            }
        ],
        ParsedRole,
        max_tokens=10000,
    )
    if own.id != "global_relief":
        raise ValueError("wrong user role")
    table = {}
    for entry in own.points:
        table.setdefault(entry.issue_id, {})[entry.option_id] = entry.points
    user = RoleSheet(
        id=own.id,
        name=own.name,
        confidential_brief=own.confidential_brief,
        points=table,
        reservation_value=own.reservation_value,
        constraints=[
            Constraint(description=c.description, disallowed={c.issue_id: c.banned_option_ids})
            for c in own.constraints
        ],
        inferred=False,
    )
    case.roles = [user, case.role("rc_alpha")]
    case.id = "sim4_inferred"
    case.source_documents = [
        SourceDocument(
            name=k,
            text=v,
            visible_to=["global_relief", "rc_alpha"] if k in shared else ["global_relief"],
        )
        for k, v in documents.items()
    ]
    case = type(case).model_validate(case.model_dump())
    for role in case.roles:
        if feasible_best_points(case, role.id) <= role.reservation_value:
            raise ValueError("nonpositive feasible surplus; audit the projection")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(case.model_dump_json(indent=2))
    manifest = {
        "case_file_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "source_files": {name: hashlib.sha256(data).hexdigest() for name, data in uploads},
        "counterpart_inference": "shared-docs only, before private own-role construction",
        "scoring": "inferred experimental preferences; not official grades or patient welfare",
        "usage": client.usage.snapshot(),
        "ledger": client.ledger.snapshot(),
    }
    write_json(args.output.with_suffix(".manifest.json"), manifest)
    print(
        json.dumps(
            {
                "path": str(args.output),
                "packages": space_size(case),
                "roles": [r.id for r in case.roles],
                "usage": client.usage.snapshot(),
                "ledger": client.ledger.snapshot(),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
