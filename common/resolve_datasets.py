#!/usr/bin/env python3
"""Print the canonical dataset selection used by all campaign stages."""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from common.dataset_selection import resolve_dataset_selection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--era", required=True)
    parser.add_argument(
        "--format",
        choices=("lines", "csv", "json", "processes", "process-json"),
        default="lines",
    )
    args = parser.parse_args()
    analysis_path = os.environ.get(
        "ANALYSIS_PATH", str(Path(__file__).resolve().parents[1])
    )
    selection = resolve_dataset_selection(analysis_path, args.era)

    if args.format == "lines":
        print("\n".join(selection["datasets"]))
    elif args.format == "csv":
        print(",".join(selection["datasets"]))
    elif args.format == "processes":
        print("\n".join(selection["processes"]))
    elif args.format == "process-json":
        print(json.dumps(selection["process_datasets"], indent=2))
    else:
        print(json.dumps(selection, indent=2))


if __name__ == "__main__":
    main()
