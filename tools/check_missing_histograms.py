#!/usr/bin/env python3
"""Report missing per-dataset histogram files without changing campaign state."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))

from common.histogram_completeness import (  # noqa: E402
    check_campaign,
    check_histograms,
    datasets_for_processes,
    datasets_for_histogram_groups,
    discover_eras,
    expected_datasets,
    normalize_era,
)


def comma_separated(values: list[str]) -> list[str]:
    return [
        item.strip()
        for value in values
        for item in value.split(",")
        if item.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only check of per-dataset ROOT outputs. This command never "
            "submits jobs and never creates, removes, or edits files."
        )
    )
    parser.add_argument("folder", type=Path, help="histogram macro-directory or era directory")
    parser.add_argument(
        "-e", "--era", action="append",
        help="era to check; repeat/comma-separate (default: discover Run3_* subdirectories)",
    )
    parser.add_argument(
        "-s", "--systematics", action="append",
        help=(
            "check a complete campaign: Hists_SYST, Hists_SYST_hadded, and "
            "Hists_systMerged; repeat/comma-separate"
        ),
    )
    parser.add_argument(
        "--dataset", action="append", default=[],
        help=(
            "expected dataset or configured process; process names are expanded "
            "to their subsamples (repeat/comma-separate)"
        ),
    )
    parser.add_argument(
        "--group", action="append", default=[],
        help=(
            "histogram MC macrogroup (DiTriBoson, DY_amcatnlo, "
            "DY_amcatnlo_105_160, EWK, signals, SingleH, SingleTop, "
            "TTX, TT, W); repeat/comma-separate"
        ),
    )
    parser.add_argument(
        "--process", action="append", default=[],
        help="process_names.yaml process to expand; repeat/comma-separate",
    )
    parser.add_argument(
        "--datasets-file", type=Path,
        help="text file containing one expected dataset per line (# comments allowed)",
    )
    parser.add_argument("--suffix", default="", help="filename suffix before .root")
    parser.add_argument(
        "--exact",
        action="store_true",
        help="treat --dataset values as literal filenames (for hadded outputs)",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument(
        "--show-unexpected", action="store_true",
        help="also list ROOT files that are not in the expected selection",
    )
    args = parser.parse_args()

    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        parser.error(f"directory does not exist: {folder}")
    eras = (
        [normalize_era(item) for item in comma_separated(args.era)]
        if args.era
        else discover_eras(folder)
    )
    if not eras:
        parser.error("no Run3_* era directories found; pass --era explicitly")

    explicit = comma_separated(args.dataset)
    if args.datasets_file:
        explicit.extend(
            line.split("#", 1)[0].strip()
            for line in args.datasets_file.read_text().splitlines()
            if line.split("#", 1)[0].strip()
        )
    explicit = list(dict.fromkeys(explicit))
    processes = comma_separated(args.process)
    groups = comma_separated(args.group)

    if args.systematics:
        systematics = comma_separated(args.systematics)
        if not explicit and not processes and not groups:
            parser.error(
                "campaign mode requires --dataset/--datasets-file or --group"
            )
        campaign_checks = []
        try:
            for era in eras:
                selected = list(explicit)
                if groups:
                    selected.extend(
                        datasets_for_histogram_groups(
                            REPOSITORY, era, groups
                        )
                    )
                if processes:
                    selected.extend(
                        datasets_for_processes(REPOSITORY, era, processes)
                    )
                selected = list(dict.fromkeys(selected))
                campaign_checks.append(
                    check_campaign(
                        REPOSITORY, folder, era, systematics, selected
                    )
                )
        except KeyError as error:
            parser.error(str(error))

        if args.json:
            print(json.dumps(
                {
                    "campaign": str(folder),
                    "checks": campaign_checks,
                },
                default=lambda value: (
                    str(value) if isinstance(value, Path) else asdict(value)
                ),
                indent=2,
            ))
        else:
            for check in campaign_checks:
                print(
                    f"\n=== {check.era}: {len(check.expected_datasets)} dataset(s), "
                    f"{len(check.expected_processes)} process(es) ==="
                )
                for dataset in check.unmapped_datasets:
                    print(
                        f"  UNMAPPED {dataset}: no process in "
                        f"config/{check.era}/process_names.yaml"
                    )
                for systematic in check.systematics:
                    print(f"\n[{systematic.systematic}]")
                    print_stage("DATASET", systematic.datasets)
                    print_stage("HADDED ", systematic.processes)
                    for temporary in systematic.temporary:
                        final = "final present" if temporary.final_present else "final missing"
                        print(
                            f"  TMP     {temporary.dataset}: "
                            f"{len(temporary.chunks)} chunk file(s), {final} "
                            f"({temporary.directory})"
                        )
                    for failure in systematic.failed_chunks:
                        chunks = (
                            ",".join(map(str, failure.chunk_numbers))
                            if failure.chunk_numbers else "see report"
                        )
                        print(
                            f"  FAILED  {failure.dataset}: chunk(s) {chunks} "
                            f"({failure.report})"
                        )
                print("\n[MERGED SYSTEMATICS]")
                print_stage("MERGED ", check.merged)

        failed = any(
            stage.datasets.missing
            or stage.datasets.empty
            or stage.processes.missing
            or stage.processes.empty
            or stage.temporary
            or stage.failed_chunks
            for check in campaign_checks
            for stage in check.systematics
        ) or any(
            check.unmapped_datasets
            or check.merged.missing
            or check.merged.empty
            for check in campaign_checks
        )
        return int(failed)

    checks = []
    try:
        for era in eras:
            process_datasets = datasets_for_processes(
                REPOSITORY, era, processes
            ) if processes else []
            selected = list(dict.fromkeys([*explicit, *process_datasets]))
            checks.append(
                check_histograms(
                    folder,
                    era,
                    expected_datasets(
                        REPOSITORY, era, selected or None, exact=args.exact
                    ),
                    args.suffix,
                )
            )
    except KeyError as error:
        parser.error(str(error))
    if args.json:
        payload = []
        for check in checks:
            item = asdict(check)
            item["directory"] = str(item["directory"])
            payload.append(item)
        print(json.dumps({"folder": str(folder), "checks": payload}, indent=2))
    else:
        for check in checks:
            print(
                f"{check.era}: expected={len(check.expected)} "
                f"complete={len(check.complete)} missing={len(check.missing)} "
                f"empty={len(check.empty)}"
            )
            for dataset in check.missing:
                print(f"  MISSING {dataset}{args.suffix}.root")
            for dataset in check.empty:
                print(f"  EMPTY   {dataset}{args.suffix}.root")
            if args.show_unexpected:
                for filename in check.unexpected:
                    print(f"  EXTRA   {filename}")

    return 1 if any(check.missing or check.empty for check in checks) else 0


def print_stage(label, check) -> None:
    print(
        f"  {label}: expected={len(check.expected)} "
        f"complete={len(check.complete)} missing={len(check.missing)} "
        f"empty={len(check.empty)} ({check.directory})"
    )
    for name in check.missing:
        print(f"    MISSING {name}.root")
    for name in check.empty:
        print(f"    EMPTY   {name}.root")


if __name__ == "__main__":
    raise SystemExit(main())
