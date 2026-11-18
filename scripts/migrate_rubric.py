"""Write a separate rubric-based case, retaining the original for legacy experiments."""

import argparse

from negotrain import config
from negotrain.cases import load_case, save_private_case
from negotrain.rubrics import TYPE_LABELS, enable_rubric


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case")
    parser.add_argument("--type", choices=list(TYPE_LABELS), required=True)
    parser.add_argument(
        "--id", required=True, help="New case id; existing private cases are never overwritten"
    )
    args = parser.parse_args()
    if not args.id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in args.id):
        parser.error("case id must use lowercase letters, numbers, underscores or hyphens")
    original = load_case(args.case)
    if original.id == args.id:
        parser.error("use a new id to preserve legacy experiments and sessions")
    if any((folder / (args.id + ".json")).exists() for folder in config.cases_dirs()):
        parser.error("a case with that id already exists")
    case = enable_rubric(original, args.type)
    case.id = args.id
    case.title += " — " + TYPE_LABELS[args.type]
    print(save_private_case(case))


if __name__ == "__main__":
    main()
