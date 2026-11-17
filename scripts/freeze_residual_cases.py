"""Author two original fictional confirmation cases before residual-study development."""

from __future__ import annotations

import itertools
from pathlib import Path

from consolidation_evaluate import frozen_json
from negotrain.schemas import Case
from train_residual_cohort import ROOT, digest
from verify_ckpt3 import economics


def make_case(key, title, public, issues, roles):
    return Case.model_validate(
        {
            "id": key,
            "title": title,
            "public_brief": public,
            "source": "Original fictional research case authored before residual-study development "
            "outcomes. Utilities are experimental assumptions; free to use and commit.",
            "issues": [
                {
                    "id": name,
                    "name": label,
                    "options": [
                        {"id": f"{name}_{i}", "label": option} for i, option in enumerate(options)
                    ],
                }
                for name, label, options in issues
            ],
            "roles": [
                {
                    "id": rid,
                    "name": name,
                    "confidential_brief": brief,
                    "reservation_value": rv,
                    "points": {
                        issue[0]: {f"{issue[0]}_{i}": value for i, value in enumerate(values)}
                        for issue, values in zip(issues, tables, strict=True)
                    },
                    "constraints": constraints,
                }
                for rid, name, brief, rv, tables, constraints in roles
            ],
        }
    )


def cases():
    pine = make_case(
        "pine_learning",
        "Pine Learning Software License",
        "A school district and a software vendor are negotiating a learning-platform license. "
        "Agree on all five listed terms as a complete package. Service options are available "
        "subject to each side's stated hard constraints. Each side may use its alternative.",
        [
            ("fee", "Annual fee", ["$24,000", "$36,000", "$48,000", "$60,000"]),
            (
                "access",
                "Student access",
                ["School hours", "Extended weekday hours", "Unlimited hours"],
            ),
            (
                "training",
                "Staff training",
                ["Self-service materials", "Remote cohort", "On-site workshop"],
            ),
            (
                "telemetry",
                "Usage reporting",
                ["Aggregate only", "Opt-in individual", "Mandatory individual"],
            ),
            ("term", "Contract duration", ["One year", "Two years", "Three years"]),
        ],
        [
            (
                "district",
                "School district",
                "Budget flexibility is limited. Value access and "
                "usable staff training, while preserving student privacy and renewal flexibility.",
                200,
                [[180, 120, 55, 0], [0, 40, 90], [0, 55, 75], [80, 40, 0], [60, 35, 0]],
                [
                    {
                        "description": "The district cannot require individual usage reporting.",
                        "disallowed": {"telemetry": ["telemetry_2"]},
                    }
                ],
            ),
            (
                "vendor",
                "Software vendor",
                "Recurring revenue and a stable contract matter. "
                "Support costs rise with access hours and hands-on training. "
                "Respect the price floor.",
                190,
                [[0, 65, 125, 190], [90, 45, 0], [80, 50, 0], [15, 55, 95], [0, 45, 85]],
                [
                    {
                        "description": "The vendor cannot license below $36,000 annually.",
                        "disallowed": {"fee": ["fee_0"]},
                    }
                ],
            ),
        ],
    )
    willow = make_case(
        "willow_kitchen",
        "Willow Community Kitchen Rental",
        "A nonprofit meal program and a shared-kitchen operator are arranging a monthly "
        "rental. Choose one listed option for each of four issues as one agreement. Prices "
        "cover the listed access and services. Both parties have alternatives; no custom terms.",
        [
            ("fee", "Monthly fee", ["$1,200", "$1,600", "$2,000", "$2,400"]),
            (
                "schedule",
                "Weekly cooking session",
                ["Saturday morning", "Saturday afternoon", "Weekday evening", "Weekday daytime"],
            ),
            (
                "storage",
                "Storage access",
                [
                    "None",
                    "Shared refrigerator",
                    "Dedicated refrigerator",
                    "Refrigerator and pantry",
                ],
            ),
            (
                "cleanup",
                "Cleanup arrangement",
                ["Tenant handles all", "Shared tasks", "Basic service", "Full service"],
            ),
        ],
        [
            (
                "nonprofit",
                "Meal program",
                "Protect the operating budget and volunteer access. "
                "Storage and cleanup help make the program practical, "
                "but a viable schedule is essential.",
                145,
                [[140, 90, 40, 0], [90, 70, 45, 0], [0, 40, 70, 95], [0, 35, 65, 85]],
                [
                    {
                        "description": "Volunteers cannot use a weekday daytime session.",
                        "disallowed": {"schedule": ["schedule_3"]},
                    }
                ],
            ),
            (
                "operator",
                "Kitchen operator",
                "Protect revenue and staffing capacity. Weekend "
                "slots and dedicated storage displace other customers. "
                "Prefer tenants handling cleanup.",
                150,
                [[0, 55, 105, 160], [0, 25, 65, 100], [95, 65, 35, 0], [90, 60, 25, 0]],
                [
                    {
                        "description": "Staffing does not permit full-service cleanup.",
                        "disallowed": {"cleanup": ["cleanup_3"]},
                    }
                ],
            ),
        ],
    )
    return [(pine, "district"), (willow, "nonprofit")]


def main():
    entries = []
    for case, role in cases():
        path = Path("data/cases") / f"{case.id}.json"
        frozen_json(path, case.model_dump(mode="json"))
        _, best = economics(case, role)
        legal, mutual = 0, 0
        for options in itertools.product(*(i.option_ids() for i in case.issues)):
            terms = dict(zip([i.id for i in case.issues], options, strict=True))
            if any(
                terms[k] in banned
                for r in case.roles
                for c in r.constraints
                if c.hard
                for k, banned in c.disallowed.items()
            ):
                continue
            legal += 1
            mutual += all(
                sum(r.points[k][v] for k, v in terms.items()) >= r.reservation_value
                for r in case.roles
            )
        assert mutual >= 20
        entries.append(
            {
                "id": case.id,
                "path": str(path),
                "role": role,
                "sha256": digest(path),
                "legal_packages": legal,
                "mutually_acceptable_packages": mutual,
                "feasible_best": best,
                "status": "reserved_unscored",
            }
        )
    frozen_json(
        ROOT / "confirmation_cases.json",
        {
            "cases": entries,
            "policy": "No API negotiations before the complete verified "
            "residual development cohort passes its frozen advance rule. "
            "No case tuning from outcomes.",
        },
    )
    print(entries)


if __name__ == "__main__":
    main()
