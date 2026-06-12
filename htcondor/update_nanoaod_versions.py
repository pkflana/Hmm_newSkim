#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
import sys
from copy import deepcopy

import yaml


def parse_args():
    parser = argparse.ArgumentParser(
        description="Find and optionally update samples.yaml nanoAOD paths to the latest DAS version."
    )
    parser.add_argument(
        "-e",
        "--era",
        required=True,
        help="Era to process, e.g. Run3_2024. Multiple eras can be comma-separated.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite config/<era>/samples.yaml. By default writes samples_latest_nanoaod.yaml.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output YAML path. Only valid with a single era and without --in-place.",
    )
    parser.add_argument(
        "--dataset",
        action="append",
        default=[],
        help="Only update this sample key. Can be passed multiple times.",
    )
    parser.add_argument(
        "--include-data",
        action="store_true",
        help="Also update /.../NANOAOD data paths. By default only /.../NANOAODSIM is updated.",
    )
    parser.add_argument(
        "--instance",
        default=None,
        help="DAS instance override, e.g. prod/phys03. If omitted, uses per-sample instance if present.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print changes without writing an output file.",
    )
    return parser.parse_args()


def as_list(value):
    if isinstance(value, list):
        return value
    return [value]


def preserve_shape(original, updated_values):
    if isinstance(original, list):
        return updated_values
    return updated_values[0]


def split_dataset_path(path):
    parts = path.strip().split("/")
    if len(parts) != 4 or parts[0] != "":
        raise ValueError(f"Not a valid DAS dataset path: {path}")
    return parts[1], parts[2], parts[3]


def make_latest_query_pattern(path):
    primary, processing, tier = split_dataset_path(path)

    patterns = [
        r"_(realistic(?:_postBPix)?)(?:_v\d+)?(?:_ext\d+)?-v\d+$",
        r"_(realistic(?:_postBPix)?)(?:_v\d+)?-v\d+$",
        r"-v\d+$",
    ]

    wildcard_processing = None
    for pattern in patterns:
        if re.search(pattern, processing):
            if "realistic" in pattern:
                wildcard_processing = re.sub(pattern, r"_\1_*", processing)
            else:
                wildcard_processing = re.sub(pattern, "-*", processing)
            break

    if wildcard_processing is None:
        wildcard_processing = f"{processing}*"

    return f"/{primary}/{wildcard_processing}/{tier}"


def version_key(path):
    _, processing, _ = split_dataset_path(path)
    numbers = tuple(int(num) for num in re.findall(r"(?:^|[_-])v(\d+)", processing))
    ext_match = re.search(r"_ext(\d+)", processing)
    ext = int(ext_match.group(1)) if ext_match else 0
    return numbers + (ext, processing)


def das_dataset_query(pattern, instance=None):
    query = f"dataset={pattern}"
    if instance:
        query += f" instance={instance}"

    command = ["dasgoclient", f"--query={query}"]
    result = subprocess.check_output(command, text=True)
    return [line.strip() for line in result.splitlines() if line.strip()]


def latest_dataset(path, instance=None):
    pattern = make_latest_query_pattern(path)
    matches = das_dataset_query(pattern, instance=instance)

    if not matches:
        return path, pattern, []

    latest = max(matches, key=version_key)
    return latest, pattern, matches


def update_samples(samples, selected_datasets, include_data, instance_override):
    updated = deepcopy(samples)
    changes = []
    warnings = []

    for sample_name, sample_info in updated.items():
        if selected_datasets and sample_name not in selected_datasets:
            continue
        if not isinstance(sample_info, dict) or "nanoAOD" not in sample_info:
            continue

        original_nanoaod = sample_info["nanoAOD"]
        new_paths = []
        sample_instance = instance_override or sample_info.get("instance")

        for path in as_list(original_nanoaod):
            try:
                _, _, tier = split_dataset_path(path)
            except ValueError as exc:
                warnings.append(f"{sample_name}: {exc}")
                new_paths.append(path)
                continue

            if tier == "NANOAOD" and not include_data:
                new_paths.append(path)
                continue

            try:
                latest, pattern, matches = latest_dataset(path, instance=sample_instance)
            except subprocess.CalledProcessError as exc:
                warnings.append(f"{sample_name}: DAS query failed for {path}: {exc}")
                new_paths.append(path)
                continue

            if latest != path:
                changes.append(
                    {
                        "sample": sample_name,
                        "old": path,
                        "new": latest,
                        "pattern": pattern,
                        "n_matches": len(matches),
                    }
                )

            new_paths.append(latest)

        sample_info["nanoAOD"] = preserve_shape(original_nanoaod, new_paths)

    return updated, changes, warnings


def output_path_for_era(config_path, era, args):
    if args.in_place:
        return os.path.join(config_path, era, "samples.yaml")
    if args.output:
        return args.output
    return os.path.join(config_path, era, "samples_latest_nanoaod.yaml")


def main():
    args = parse_args()
    eras = [era.strip() for era in args.era.split(",") if era.strip()]

    if args.output and (args.in_place or len(eras) != 1):
        raise SystemExit("[ERROR] --output can only be used with one era and without --in-place")

    analysis_path = os.environ.get(
        "ANALYSIS_PATH",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    )
    config_path = os.path.join(analysis_path, "config")

    any_changes = False

    for era in eras:
        samples_path = os.path.join(config_path, era, "samples.yaml")
        out_path = output_path_for_era(config_path, era, args)

        with open(samples_path, "r") as stream:
            samples = yaml.safe_load(stream)

        print(f"\n[INFO] Processing {samples_path}")
        updated, changes, warnings = update_samples(
            samples,
            selected_datasets=set(args.dataset),
            include_data=args.include_data,
            instance_override=args.instance,
        )

        for warning in warnings:
            print(f"[WARNING] {warning}")

        if not changes:
            print("[INFO] No nanoAOD updates found.")
        else:
            any_changes = True
            print(f"[INFO] Found {len(changes)} nanoAOD update(s):")
            for change in changes:
                print(
                    f"  {change['sample']}: {change['old']} -> {change['new']} "
                    f"(matches={change['n_matches']}, pattern={change['pattern']})"
                )

        if args.dry_run:
            print("[DRY RUN] No file written.")
            continue

        with open(out_path, "w") as stream:
            yaml.dump(updated, stream, default_flow_style=False, sort_keys=False)
        print(f"[INFO] Saved {out_path}")

    return 0 if any_changes else 0


if __name__ == "__main__":
    sys.exit(main())
