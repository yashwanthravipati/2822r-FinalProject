"""Exact pre-session own-value arithmetic; never consult an opponent's private sheet."""

from __future__ import annotations

import json
from pathlib import Path

from consolidation_evaluate import frozen_json


def worksheet_values(case, role_id):
    role = case.role(role_id)
    rows = []
    for issue in case.issues:
        values = role.points[issue.id]
        maximum = max(values[o.id] for o in issue.options)
        rows.append(
            {
                "issue": issue.id,
                "name": issue.name,
                "maximum_own_points": maximum,
                "options": [
                    {
                        "id": option.id,
                        "label": option.label,
                        "own_points": values[option.id],
                        "loss_from_issue_maximum": maximum - values[option.id],
                    }
                    for option in issue.options
                ],
            }
        )
    upper = sum(row["maximum_own_points"] for row in rows)
    return {
        "case_id": case.id,
        "role_id": role_id,
        "own_point_upper_bound": upper,
        "walkaway": role.reservation_value,
        "maximum_total_loss_to_match_walkaway": upper - role.reservation_value,
        "issues": rows,
        "own_hard_constraints": [c.model_dump() for c in role.constraints],
    }


def worksheet(case, role_id):
    values = worksheet_values(case, role_id)
    lines = [
        "Preparation worksheet for the CURRENT case (computed from my own sheet only):",
        f"Own point upper bound B = {values['own_point_upper_bound']:g}.",
        f"Walk-away W = {values['walkaway']:g}.",
        "For any complete listed package, add the option losses below: "
        "my points U = B - total loss; my surplus = U - W.",
        "To match walking away, total loss may be at most "
        f"{values['maximum_total_loss_to_match_walkaway']:g}. "
        "A larger loss means the package is WORSE than walking away.",
        "B is an arithmetic upper bound, not a promise of a legal or mutually acceptable "
        "deal. Check my hard constraints separately. Their private preferences are unknown.",
    ]
    for row in values["issues"]:
        lines.append(f"{row['name']} ({row['issue']}):")
        for option in row["options"]:
            lines.append(
                f"  {option['id']} / {option['label']}: own points {option['own_points']:g}; "
                f"loss {option['loss_from_issue_maximum']:g}"
            )
    lines.append("My hard constraints: " + json.dumps(values["own_hard_constraints"]))
    lines.extend(
        [
            "Before proposing OR accepting, privately use this worksheet to check all terms. "
            "Never trade below my walk-away just because the final small concession sounds "
            "reasonable. Recheck the whole package, not only the changed issue.",
            "A lower point loss is better for me, but an unaccepted demand has no terminal "
            "value. Ask about their priorities and exchange low-cost terms for higher-value "
            "returns. Close an acceptable deal when further improvement is not credible.",
            "The following reports describe earlier practice. Their case-specific figures "
            "do not override this CURRENT-case worksheet. Transfer their decision lessons.",
        ]
    )
    return "\n".join(lines)


def project_memories(root: Path, uid: int, case_key: str):
    """Materialize only the current case's frozen memory for the unchanged assessment loop."""
    data = json.loads((root / "raw" / f"learner{uid}.memories.json").read_text())
    selected = data["by_case"][case_key]
    projected = root / "raw" / "projected" / case_key
    frozen_json(projected / "raw" / f"learner{uid}.memories.json", selected)
    return projected
