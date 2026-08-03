#!/usr/bin/env python3
"""Return success only when a staged workflow output is complete."""

import argparse
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from common.validation_utilities import stage_output_complete


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["validation", "histograms", "systematics"])
    parser.add_argument("path")
    args = parser.parse_args()
    raise SystemExit(0 if stage_output_complete(args.stage, args.path) else 1)


if __name__ == "__main__":
    main()
