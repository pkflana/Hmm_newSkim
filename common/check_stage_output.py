#!/usr/bin/env python3
"""Return success only when a staged workflow output is complete."""

import argparse
import json
from pathlib import Path


def nonempty(path):
    candidate = Path(path)
    return candidate.is_file() and candidate.stat().st_size > 0


def validation_complete(path):
    if not nonempty(path):
        return False
    try:
        with open(path) as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False
    return (
        manifest.get("stage") == "validation"
        and manifest.get("status") == "passed"
        and isinstance(manifest.get("valid_root_files"), list)
        and (
            bool(manifest["valid_root_files"])
            or bool(manifest.get("ignored_empty_root_files", []))
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["validation", "histograms", "systematics"])
    parser.add_argument("path")
    args = parser.parse_args()

    if args.stage == "validation":
        complete = validation_complete(args.path)
    else:
        complete = nonempty(args.path)
    raise SystemExit(0 if complete else 1)


if __name__ == "__main__":
    main()
