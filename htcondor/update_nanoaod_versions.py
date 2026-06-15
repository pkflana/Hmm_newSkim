#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
import sys
from copy import deepcopy

import yaml


EXT_SAMPLE_RE = re.compile(r"^(?P<base>.+)_ext(?P<ext>\d+)$")
EXT_PATH_RE = re.compile(r"_ext(?P<ext>\d+)")
SAMPLE_HEADER_RE = re.compile(r"^([^#\s][^:]*):\s*$")
COMMENTED_NANOAOD_RE = re.compile(r"^\s*#\s*-\s*(/.*)$")
NANOAOD_ITEM_RE = re.compile(r"^\s*-\s*(/.*)$")


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


def path_ext_number(path):
    match = EXT_PATH_RE.search(path)
    return int(match.group("ext")) if match else 0


def nominal_path_from_ext(path):
    if path_ext_number(path) == 0:
        return path

    try:
        primary, processing, tier = split_dataset_path(path)
    except ValueError:
        return path

    nominal_processing = EXT_PATH_RE.sub("", processing)
    return f"/{primary}/{nominal_processing}/{tier}"


def normalize_nanoaod_paths(paths):
    deduped = []
    seen = set()

    for path in as_list(paths):
        nominal_path = nominal_path_from_ext(path)
        if nominal_path != path and nominal_path not in seen:
            deduped.append(nominal_path)
            seen.add(nominal_path)

        if path in seen:
            continue
        deduped.append(path)
        seen.add(path)

    return sorted(
        deduped,
        key=lambda path: (path_ext_number(path) != 0, path_ext_number(path)),
    )


def merge_ext_samples(samples):
    normalized = {}
    merged = []
    orphan_ext = []

    for sample_name, sample_info in (samples or {}).items():
        match = EXT_SAMPLE_RE.match(sample_name)
        if match and match.group("base") in samples:
            continue
        normalized[sample_name] = sample_info

    for sample_name, sample_info in (samples or {}).items():
        match = EXT_SAMPLE_RE.match(sample_name)
        if not match:
            continue

        base_name = match.group("base")
        if base_name not in normalized:
            orphan_ext.append(sample_name)
            continue

        base_info = normalized[base_name]
        if not isinstance(base_info, dict) or not isinstance(sample_info, dict):
            continue

        base_paths = as_list(base_info.get("nanoAOD", []))
        ext_paths = as_list(sample_info.get("nanoAOD", []))
        base_info["nanoAOD"] = normalize_nanoaod_paths(base_paths + ext_paths)
        merged.append((sample_name, base_name))

    for sample_info in normalized.values():
        if isinstance(sample_info, dict) and "nanoAOD" in sample_info:
            sample_info["nanoAOD"] = normalize_nanoaod_paths(sample_info["nanoAOD"])

    return normalized, merged, orphan_ext


def natural_key(text):
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", text)
    ]


def sample_category_rank(sample_name, sample_info):
    sample_info = sample_info if isinstance(sample_info, dict) else {}

    if sample_info.get("is_data"):
        return 0

    key = sample_name.lower()
    cross_section = str(sample_info.get("crossSection", "")).lower()
    text = f"{key} {cross_section}"

    if sample_info.get("is_signal") or "hto2mu" in key:
        return 10

    if key.startswith("dy") or "dyto" in text:
        return 20
    if key.startswith("ewk") or "ewk" in text:
        return 30
    if (
        any(
            token in key
            for token in [
                "glugluh",
                "vbfh",
                "wplush",
                "wminush",
                "zh_",
                "ggzh",
                "tth",
                "vh",
            ]
        )
        or "higgs" in text
    ):
        return 40
    if key.startswith(("tbar", "tbbar", "twminus", "tt", "tth", "ttw", "ttz")):
        return 50
    if key.startswith("st"):
        return 50
    if key.startswith("wto") or key.startswith("w_") or key == "w":
        return 60
    if key.startswith(("ww", "wz", "zz")):
        return 70
    if key.startswith(("www", "wwz", "wzz", "zzz")):
        return 80

    return 90


def get_reference_order(config_path):
    reference_path = os.path.join(config_path, "Run3_2024", "samples.yaml")

    try:
        with open(reference_path, "r") as stream:
            reference_samples = yaml.safe_load(stream) or {}
    except FileNotFoundError:
        return {}

    reference_samples, _, _ = merge_ext_samples(reference_samples)
    return {sample_name: index for index, sample_name in enumerate(reference_samples)}


def order_samples(samples, reference_order):
    return dict(
        sorted(
            samples.items(),
            key=lambda item: (
                sample_category_rank(item[0], item[1]),
                reference_order.get(item[0], 10_000),
                natural_key(item[0]),
            ),
        )
    )


def collect_commented_nanoaod_paths(yaml_text):
    comments = {}
    current_sample = None
    in_nanoaod = False

    for line in yaml_text.splitlines():
        sample_match = SAMPLE_HEADER_RE.match(line)
        if sample_match:
            current_sample = sample_match.group(1)
            in_nanoaod = False
            continue

        if current_sample is None:
            continue

        stripped = line.strip()
        if stripped == "nanoAOD:":
            in_nanoaod = True
            continue

        if in_nanoaod and stripped and not stripped.startswith("-") and not stripped.startswith("#"):
            in_nanoaod = False

        if not in_nanoaod:
            continue

        comment_match = COMMENTED_NANOAOD_RE.match(line)
        if comment_match:
            comments.setdefault(current_sample, [])
            comments[current_sample].append(comment_match.group(1))

    return comments


def inject_commented_nanoaod_paths(yaml_text, commented_paths):
    if not commented_paths:
        return yaml_text

    lines = yaml_text.splitlines()
    output = []
    current_sample = None
    in_nanoaod = False
    active_paths = set()

    def flush_comments():
        if current_sample not in commented_paths:
            return

        existing_comments = {
            match.group(1)
            for line in output
            for match in [COMMENTED_NANOAOD_RE.match(line)]
            if match
        }

        for path in commented_paths[current_sample]:
            if path in active_paths or path in existing_comments:
                continue
            output.append(f"  # - {path}")

    for line in lines:
        sample_match = SAMPLE_HEADER_RE.match(line)
        if sample_match:
            if in_nanoaod:
                flush_comments()
            current_sample = sample_match.group(1)
            in_nanoaod = False
            active_paths = set()
            output.append(line)
            continue

        if current_sample is not None and line.strip() == "nanoAOD:":
            in_nanoaod = True
            output.append(line)
            continue

        if in_nanoaod:
            item_match = NANOAOD_ITEM_RE.match(line)
            if item_match:
                active_paths.add(item_match.group(1))
            elif line.strip() and not line.strip().startswith("#"):
                flush_comments()
                in_nanoaod = False

        output.append(line)

    if in_nanoaod:
        flush_comments()

    return "\n".join(output) + "\n"


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
    path_ext = path_ext_number(path)
    same_extension_matches = [
        match for match in matches if path_ext_number(match) == path_ext
    ]

    if not same_extension_matches:
        return path, pattern, []

    latest = max(same_extension_matches, key=version_key)
    return latest, pattern, same_extension_matches


def update_samples(samples, selected_datasets, include_data, instance_override):
    updated = deepcopy(samples)
    changes = []
    warnings = []

    for sample_name, sample_info in updated.items():
        if selected_datasets and sample_name not in selected_datasets:
            continue
        if not isinstance(sample_info, dict) or "nanoAOD" not in sample_info:
            continue

        new_paths = []
        sample_instance = instance_override or sample_info.get("instance")

        for path in as_list(sample_info["nanoAOD"]):
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

        sample_info["nanoAOD"] = normalize_nanoaod_paths(new_paths)

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
    reference_order = get_reference_order(config_path)

    any_changes = False

    for era in eras:
        samples_path = os.path.join(config_path, era, "samples.yaml")
        out_path = output_path_for_era(config_path, era, args)

        with open(samples_path, "r") as stream:
            samples_text = stream.read()

        commented_nanoaod_paths = collect_commented_nanoaod_paths(samples_text)
        samples = yaml.safe_load(samples_text)

        print(f"\n[INFO] Processing {samples_path}")
        samples, merged_ext_samples, orphan_ext_samples = merge_ext_samples(samples)

        for ext_sample, base_sample in merged_ext_samples:
            print(f"[INFO] Merged {ext_sample} into {base_sample}.nanoAOD")

        for ext_sample in orphan_ext_samples:
            print(
                f"[WARNING] Keeping {ext_sample} as a separate sample because "
                "the nominal sample was not found."
            )

        updated, changes, warnings = update_samples(
            samples,
            selected_datasets=set(args.dataset),
            include_data=args.include_data,
            instance_override=args.instance,
        )
        updated, merged_ext_samples, orphan_ext_samples = merge_ext_samples(updated)
        updated = order_samples(updated, reference_order)

        for warning in warnings:
            print(f"[WARNING] {warning}")

        for ext_sample, base_sample in merged_ext_samples:
            print(f"[INFO] Merged {ext_sample} into {base_sample}.nanoAOD")

        for ext_sample in orphan_ext_samples:
            print(
                f"[WARNING] Keeping {ext_sample} as a separate sample because "
                "the nominal sample was not found."
            )

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

        output_text = yaml.safe_dump(
            updated,
            default_flow_style=False,
            sort_keys=False,
            width=1000,
        )
        output_text = inject_commented_nanoaod_paths(
            output_text,
            commented_nanoaod_paths,
        )

        with open(out_path, "w") as stream:
            stream.write(output_text)
        print(f"[INFO] Saved {out_path}")

    return 0 if any_changes else 0


if __name__ == "__main__":
    sys.exit(main())
