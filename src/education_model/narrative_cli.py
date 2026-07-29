from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .narratives import load_narrative_schema, propose_narrative_codes, proposals_to_frame
from .narrative_validation import full_validation_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Narrative coding and validation utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    propose = sub.add_parser("propose")
    propose.add_argument("--text", required=True)
    propose.add_argument("--schema", default="config/narrative_schema.json")
    propose.add_argument("--output")

    validate = sub.add_parser("validate")
    validate.add_argument("--human", required=True)
    validate.add_argument("--algorithm")
    validate.add_argument("--output", default="outputs/narrative_validation_report.json")

    args = parser.parse_args()
    if args.command == "propose":
        schema = load_narrative_schema(args.schema)
        frame = proposals_to_frame(propose_narrative_codes(args.text, schema), schema)
        if args.output:
            frame.to_csv(args.output, index=False)
            print(f"Wrote {args.output}")
        else:
            print(frame.to_string(index=False))
    elif args.command == "validate":
        human = pd.read_csv(args.human)
        algorithm = pd.read_csv(args.algorithm) if args.algorithm else None
        report = full_validation_report(human, algorithm)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote {output}")


if __name__ == "__main__":
    main()
