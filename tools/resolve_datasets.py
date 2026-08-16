#!/usr/bin/env python3
"""Print the canonical dataset selection used by all campaign stages."""

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from common.dataset_utilities import resolve_dataset_selection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--era", required=True)
    parser.add_argument(
        "--exclude-data",
        action="store_true",
        help="Exclude datasets belonging to Data_* processes.",
    )
    parser.add_argument(
        "--format",
        choices=("lines", "csv", "json", "processes", "process-json"),
        default="lines",
    )
    args = parser.parse_args()
    analysis_path = os.environ.get("ANALYSIS_PATH", str(REPO))
    selection = resolve_dataset_selection(analysis_path, args.era)
    if args.exclude_data:
        data_datasets = {
            dataset
            for process, datasets in selection["process_datasets"].items()
            if process.lower().startswith("data")
            for dataset in datasets
        }
        selection["datasets"] = [
            dataset
            for dataset in selection["datasets"]
            if dataset not in data_datasets
        ]

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
