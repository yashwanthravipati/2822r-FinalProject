import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from negotrain.cases import load_case
from negotrain.cases.parser import ParsedCase, ParsedRole

spec = importlib.util.spec_from_file_location(
    "sim4_preparation", Path(__file__).parents[1] / "scripts" / "prepare_sim4.py"
)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def test_counterpart_is_inferred_before_and_without_private_sources(case, tmp_path, monkeypatch):
    source = tmp_path / "source"
    (source / "shared-docs").mkdir(parents=True)
    (source / "global-relief-docs").mkdir()
    (source / "shared-docs" / "public.md").write_text("SHARED PUBLIC TEXT")
    (source / "global-relief-docs" / "private.md").write_text("ONLY GLOBAL RELIEF SECRET")
    (source / "role.md").write_text("PRIVATE ROLE CARD")
    roles = []
    for role, new_id in zip(case.roles, ("global_relief", "rc_alpha"), strict=True):
        roles.append(
            {
                "id": new_id,
                "name": role.name,
                "confidential_brief": "Public-only estimate",
                "points": [
                    {"issue_id": i, "option_id": o, "points": p}
                    for i, opts in role.points.items()
                    for o, p in opts.items()
                ],
                "reservation_value": role.reservation_value,
                "constraints": [],
                "inferred": True,
            }
        )
    # Keep the fixture's economics but the smaller finite space required by the parser.
    issues = [i.model_dump() for i in case.issues[:3]]
    ids = {i["id"] for i in issues}
    for role in roles:
        role["points"] = [p for p in role["points"] if p["issue_id"] in ids]
        role["reservation_value"] = 0
    parsed = ParsedCase.model_validate(
        {
            "id": "sim4",
            "title": "Synthetic test",
            "public_brief": "SHARED PUBLIC TEXT",
            "issues": issues,
            "roles": roles,
            "scoring_notes": "Inferred test utilities",
        }
    )
    own = ParsedRole.model_validate(
        {**roles[0], "confidential_brief": "ONLY GLOBAL RELIEF SECRET", "inferred": False}
    )
    calls = []

    def saved(path, llm, system, messages, schema, **kwargs):
        calls.append((schema, messages))
        return parsed if schema is ParsedCase else own

    monkeypatch.setattr(prepare, "saved_parse", saved)
    monkeypatch.setattr(prepare, "SpendLedger", lambda *args: None)
    empty = SimpleNamespace(snapshot=lambda: {})
    monkeypatch.setattr(
        prepare, "ClaudeLLM", lambda **kwargs: SimpleNamespace(usage=empty, ledger=empty)
    )
    output = tmp_path / "case.json"
    monkeypatch.setattr(
        "sys.argv", ["prepare_sim4", "--source", str(source), "--output", str(output)]
    )
    prepare.main()
    assert calls[0][0] is ParsedCase and calls[1][0] is ParsedRole
    assert "ONLY GLOBAL RELIEF SECRET" not in str(calls[0][1])
    assert "PRIVATE ROLE CARD" not in str(calls[0][1])
    assert "ONLY GLOBAL RELIEF SECRET" in str(calls[1][1])
    result = load_case(output)
    for doc in result.source_documents:
        assert doc.visible_to == (
            ["global_relief", "rc_alpha"]
            if doc.name.startswith("shared-docs/")
            else ["global_relief"]
        )
    assert "SECRET" not in result.role("rc_alpha").confidential_brief
    assert json.loads(output.with_suffix(".manifest.json").read_text())["source_files"]
