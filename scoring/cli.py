from __future__ import annotations

import argparse
import json
import sys

from pydantic import ValidationError

from scoring.models import JDFeatures
from scoring.engine import evaluate


def main() -> int:
    parser = argparse.ArgumentParser(description="career-ops scoring engine")
    parser.add_argument("--input", type=str, help="Path to JDFeatures JSON file (reads stdin if omitted)")
    parser.add_argument("--diagnostics", action="store_true", help="Include diagnostic trace in output")
    args = parser.parse_args()

    try:
        if args.input:
            with open(args.input) as f:
                raw = f.read()
        else:
            raw = sys.stdin.read()

        data = json.loads(raw)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1

    try:
        features = JDFeatures(**data)
    except ValidationError as e:
        print(json.dumps({"error": e.errors()}), file=sys.stderr)
        return 1

    result = evaluate(features, diagnostics=args.diagnostics)
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
