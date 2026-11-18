"""Compute component metrics from local human references and predictions, without API calls."""

import argparse
import json
from pathlib import Path

from negotrain.rubric_evaluation import (
    FeedbackRating,
    ReferenceExample,
    SteeringRating,
    evaluate_diagnosis,
    evaluate_feedback,
    evaluate_steering,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, help="JSON with diagnosis, steering and/or feedback lists"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--weakness-threshold", type=float, default=0.5)
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    report = {
        "diagnosis": evaluate_diagnosis(
            [ReferenceExample.model_validate(x) for x in data.get("diagnosis", [])],
            weakness_threshold=args.weakness_threshold,
        ),
        "steering": evaluate_steering(
            [SteeringRating.model_validate(x) for x in data.get("steering", [])]
        ),
        "feedback": evaluate_feedback(
            [FeedbackRating.model_validate(x) for x in data.get("feedback", [])]
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
