#!/usr/bin/env python3
"""Produce systematic shape plots across samples and Run-3 eras."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
DEFAULT_ERAS = (
    "Run3_2022",
    "Run3_2022EE",
    "Run3_2023",
    "Run3_2023BPix",
    "Run3_2024",
    "Run3_2025",
    "Run3_2022_25",
)
DEFAULT_GROUPS = (
    "Jet Res",
    "Jet Scale",
    "Muon Eff.",
    "Muon Res",
    "Muon Scale",
    "EWKZ PS",
    "QCD Scale",
    "PDF",
)
DEFAULT_SAMPLES = (
    "DYto2Mu_MLL105To160",
    "EWK_2Mu2J_MLL_105to160_herwig",
    "ST",
    "VV",
    "TT",
    "TTX",
    "VVV",
    "W_NJets",
    "TW",
    "SingleH",
    "GluGluHto2Mu",
    "VBFHto2Mu_M125_powheg",
)


def csv(values: list[str] | None, defaults: tuple[str, ...]) -> list[str]:
    if not values:
        return list(defaults)
    return [item.strip() for value in values for item in value.split(",") if item.strip()]


def slug(value: str) -> str:
    return "_".join(value.replace(".", "").split())


def plot_command(
    *, input_base: Path, output: Path, era: str, region: str, variable: str,
    samples: list[str], group: str, execute: bool,
) -> list[str]:
    command = [
        str(REPO / "hmumu"), "plot",
        "--era", era,
        "--input", str(input_base / era),
        "--output", str(output),
        "--region", region,
        "--variable", variable,
        "--samples", *samples,
        "--systematics",
        "--systematic-group", group,
        "--overlay-systematic",
        "--no-mc-stat-uncertainty",
    ]
    if execute:
        command.append("--run")
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-base", required=True)
    parser.add_argument("--output", default="plots_systematics_campaign")
    parser.add_argument("--era", action="append", dest="eras")
    parser.add_argument("--sample", action="append", dest="samples")
    parser.add_argument("--systematic-group", action="append", dest="groups")
    parser.add_argument("--region", default="Signal_Fit_VBF")
    parser.add_argument("--variable", default="DNN_NNOutput")
    parser.add_argument(
        "--mode", choices=("sample", "combined", "both"), default="both",
        help="sample-by-sample plots, all-sample plots, or both",
    )
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()

    input_base = Path(args.input_base)
    output = Path(args.output)
    eras = csv(args.eras, DEFAULT_ERAS)
    samples = csv(args.samples, DEFAULT_SAMPLES)
    groups = csv(args.groups, DEFAULT_GROUPS)
    commands: list[list[str]] = []

    for era in eras:
        if not (input_base / era).is_dir():
            print(f"[SKIP] Missing era directory: {input_base / era}")
            continue
        if args.mode in {"sample", "both"}:
            for sample in samples:
                for group in groups:
                    commands.append(plot_command(
                        input_base=input_base,
                        output=output / "sample_by_sample" / sample / slug(group),
                        era=era,
                        region=args.region,
                        variable=args.variable,
                        samples=[sample],
                        group=group,
                        execute=args.run,
                    ))
        if args.mode in {"combined", "both"}:
            for group in groups:
                commands.append(plot_command(
                    input_base=input_base,
                    output=output / "all_samples" / slug(group),
                    era=era,
                    region=args.region,
                    variable=args.variable,
                    samples=samples,
                    group=group,
                    execute=args.run,
                ))

    print(
        f"Prepared {len(commands)} plot jobs: {len(eras)} era choices, "
        f"{len(samples)} samples, {len(groups)} systematic groups."
    )
    for index, command in enumerate(commands, 1):
        print(f"[{index}/{len(commands)}] {shlex.join(command)}", flush=True)
        if args.run:
            completed = subprocess.run(command, cwd=REPO, check=False)
            if completed.returncode:
                return completed.returncode
    if not args.run:
        print("\nPlan only: add --run to create the plots.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
