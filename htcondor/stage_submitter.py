#!/usr/bin/env python3
"""Shared Python frontend for manifest-driven HTCondor stages."""

import os
import subprocess
import sys
from pathlib import Path

ENTRYPOINTS = {
    "validation": "analysis/scripts/validate.sh",
    "histograms": "histograms/scripts/hists.sh",
    "systematics": "histograms/scripts/systematics.sh",
}


def with_condor_option(arguments):
    if "--condor" in arguments:
        return list(arguments)
    output = []
    inserted = False
    for argument in arguments:
        if argument == "--" and not inserted:
            output.append("--condor")
            inserted = True
        output.append(argument)
    if not inserted:
        output.append("--condor")
    return output


def submit(stage, arguments=None):
    if stage not in ENTRYPOINTS:
        raise ValueError(f"Unknown workflow stage: {stage}")
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    analysis_path = Path(
        os.environ.get("ANALYSIS_PATH", Path(__file__).resolve().parents[1])
    ).resolve()
    command = [
        "bash",
        str(analysis_path / ENTRYPOINTS[stage]),
        *with_condor_option(arguments),
    ]
    print("[SUBMITTER] " + " ".join(command), flush=True)
    return subprocess.run(command, cwd=analysis_path).returncode
