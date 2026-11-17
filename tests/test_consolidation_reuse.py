import importlib.util
import json
from pathlib import Path

import pytest


def test_ablation_preserves_all_reports_and_exact_control_bytes(tmp_path, monkeypatch):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("ablation", scripts / "consolidation_ablate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "audit_case", lambda *args: None)
    source, target = tmp_path / "source", tmp_path / "target"
    memory = source / "raw/learner0.memories.json"
    reports = [f"report {i}" for i in range(5)]
    memories = {m: [m] for m in module.METHODS if m != "reports_with_procedure"}
    memories["reports"] = reports
    module.write_json(memory, {"memories": memories})
    case_path = tmp_path / "case.json"
    case_path.write_text("{}")
    protocol = {
        "source_sha256": module.source_hash(),
        "budget": "dev",
        "users": [0],
        "cases": [
            {
                "key": "known",
                "path": str(case_path),
                "sha256": module.digest(case_path),
                "status": "development",
            }
        ],
        "probe_tiers": [1, 3, 5],
    }
    module.write_json(source / "protocol.json", protocol)
    digest = module.digest(source / "protocol.json")
    module.write_json(
        source / "frozen.json",
        {
            "protocol_sha256": digest,
            "memories": {str(memory): module.digest(memory)},
            "history": {},
        },
    )
    module.write_json(source / "verified_analysis.json", {"protocol_sha256": digest})
    for method in module.REUSED:
        stage = "baseline" if method == "baseline" else f"{method}_after"
        for tier in (1, 3, 5):
            module.write_json(
                source / f"assessment/known/raw/learner0_{stage}_t{tier}.json",
                {"complete": True, "payload": f"{stage}-{tier}"},
            )
    module.prepare(target, source)
    _, frozen = module.check_frozen(target)
    assert len(frozen["reused_episodes"]) == 12
    new = json.loads((target / "raw/learner0.memories.json").read_text())["memories"]
    assert new["reports"] == reports
    assert all(report in new["reports_with_procedure"][0] for report in reports)
    assert module.PROCEDURE in new["reports_with_procedure"][0]
    provenance = json.loads((target / "reuse_manifest.json").read_text())
    assert all(
        Path(r["source"]).read_bytes() == Path(r["destination"]).read_bytes() for r in provenance
    )
    Path(provenance[0]["destination"]).write_text("changed")
    with pytest.raises(ValueError, match="frozen artifact"):
        module.check_frozen(target)
