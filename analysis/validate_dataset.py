#!/usr/bin/env python3
"""Stage 1: validate one dataset's ROOT ntuples and JSON reports."""

import argparse
import json
import multiprocessing
import os
import re
import sys
import time
from pathlib import Path

sys.path.append(os.environ.get("ANALYSIS_PATH", str(Path(__file__).resolve().parents[1])))

import common.utilities as utilities
from common.manifest_utilities import write_manifest
from common.validation_utilities import discover_root_files, validate_file


def discover_json_files(path):
    if path.endswith(".json"):
        return [os.path.abspath(path)]
    return sorted(
        os.path.abspath(os.path.join(root, name))
        for root, _, names in os.walk(path)
        for name in names
        if name.endswith(".json")
    )


def validate_json(path, retries=3, retry_delay=2.0):
    last_reason = "unknown validation error"
    for attempt in range(1, retries + 1):
        try:
            with open(path) as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                return path, False, "top-level JSON value is not an object"
            else:
                return path, True, ""
        except json.JSONDecodeError as error:
            # Syntax errors are deterministic; retry only transient I/O errors.
            return path, False, repr(error)
        except Exception as error:
            last_reason = repr(error)
        if attempt < retries and retry_delay:
            time.sleep(retry_delay)
    return path, False, f"{last_reason} (failed after {retries} attempts)"


def pairing_key(path, is_json=False):
    stem = Path(path).stem
    indexed_match = re.fullmatch(
        r"report_(\d+)" if is_json else r"skim_(\d+)",
        stem,
    )
    if indexed_match:
        return indexed_match.group(1)
    if is_json:
        for suffix in ("_skim_report", "_report"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
    elif stem.endswith("_skim"):
        stem = stem[: -len("_skim")]
    return stem


def is_empty_root_result(result):
    return not result[1] and result[2].startswith("empty tree ")


def pair_mc_results(root_results, json_results):
    roots_by_key = {}
    jsons_by_key = {}
    for result in root_results:
        roots_by_key.setdefault(pairing_key(result[0]), []).append(result)
    for result in json_results:
        jsons_by_key.setdefault(pairing_key(result[0], is_json=True), []).append(result)

    valid_roots = []
    valid_jsons = []
    invalid_roots = []
    invalid_jsons = []
    ignored_empty_roots = []
    for key in sorted(set(roots_by_key) | set(jsons_by_key)):
        root_items = roots_by_key.get(key, [])
        json_items = jsons_by_key.get(key, [])
        good_roots = [item for item in root_items if item[1]]
        empty_roots = [item for item in root_items if is_empty_root_result(item)]
        good_jsons = [item for item in json_items if item[1]]
        pair_is_valid = len(good_roots) == 1 and len(good_jsons) == 1
        empty_pair_is_valid = (
            not good_roots and len(empty_roots) == 1 and len(good_jsons) == 1
        )
        # MC normalization lives in the skim report. Keep the unique valid
        # JSON even when its ROOT output has no processable events; histogram
        # production receives only the readable ROOT files.
        normalization_json_is_valid = (
            len(root_items) == 1 and len(good_jsons) == 1
        )
        if pair_is_valid:
            root_path = good_roots[0][0]
            json_path = good_jsons[0][0]
            valid_roots.append(root_path)
            valid_jsons.append(json_path)
        elif empty_pair_is_valid:
            empty_path = empty_roots[0][0]
            valid_jsons.append(good_jsons[0][0])
            ignored_empty_roots.append(
                {
                    "path": empty_path,
                    "pairing_key": key,
                    "reason": empty_roots[0][2],
                }
            )
        elif normalization_json_is_valid:
            valid_jsons.append(good_jsons[0][0])

        for path, intrinsically_valid, intrinsic_reason in root_items:
            if (pair_is_valid and intrinsically_valid) or (
                empty_pair_is_valid and is_empty_root_result(
                    (path, intrinsically_valid, intrinsic_reason)
                )
            ):
                continue
            if not intrinsically_valid:
                reason = intrinsic_reason
            elif not json_items:
                reason = "missing JSON counterpart"
            elif not good_jsons:
                reason = "JSON counterpart is invalid"
            else:
                reason = "ambiguous ROOT/JSON pairing"
            invalid_roots.append({"path": path, "pairing_key": key, "reason": reason})

        for path, intrinsically_valid, intrinsic_reason in json_items:
            if normalization_json_is_valid and intrinsically_valid:
                continue
            if not intrinsically_valid:
                reason = intrinsic_reason
            elif not root_items:
                reason = "missing ROOT counterpart"
            elif not good_roots:
                reason = "ROOT counterpart is invalid"
            else:
                reason = "ambiguous ROOT/JSON pairing"
            invalid_jsons.append({"path": path, "pairing_key": key, "reason": reason})

    return (
        valid_roots,
        valid_jsons,
        invalid_roots,
        invalid_jsons,
        ignored_empty_roots,
    )


def expected_input_completeness(
    samples_with_files,
    dataset_name,
    root_results,
    json_results,
    is_data,
    chunk_manifest=None,
):
    if chunk_manifest is not None:
        chunks = chunk_manifest.get("chunks", [])
        expected_files = [
            chunk["root_file"]
            for chunk in chunks
            if "root_file" in chunk
        ]
        discovered_roots = {
            os.path.abspath(result[0]): result
            for result in root_results
        }
        roots_by_name = {}
        for result in root_results:
            roots_by_name.setdefault(os.path.basename(result[0]), []).append(result)
        discovered_jsons = {
            os.path.abspath(result[0]): result
            for result in json_results
        }
        jsons_by_name = {}
        for result in json_results:
            jsons_by_name.setdefault(os.path.basename(result[0]), []).append(result)
        missing = []
        for chunk in chunks:
            root_path = os.path.abspath(chunk["root_file"])
            root_result = discovered_roots.get(root_path)
            if root_result is None:
                relocated = roots_by_name.get(os.path.basename(root_path), [])
                if len(relocated) == 1:
                    root_result = relocated[0]
            root_present = root_result is not None
            if is_data:
                covered = root_present and (
                    root_result[1] or is_empty_root_result(root_result)
                )
            else:
                report_path = os.path.abspath(chunk["report_file"])
                report_result = discovered_jsons.get(report_path)
                if report_result is None:
                    relocated = jsons_by_name.get(os.path.basename(report_path), [])
                    if len(relocated) == 1:
                        report_result = relocated[0]
                covered = root_present and report_result is not None
            if not covered:
                missing.extend(chunk.get("input_files", [root_path]))
        return expected_files, missing, ""

    dataset_cfg = samples_with_files.get(dataset_name)
    if not isinstance(dataset_cfg, dict) or not isinstance(
        dataset_cfg.get("filelist"), list
    ):
        return [], [], f"missing filelist for {dataset_name}"

    expected_files = dataset_cfg["filelist"]
    root_results_by_key = {}
    json_results_by_key = {}
    for result in root_results:
        root_results_by_key.setdefault(pairing_key(result[0]), []).append(result)
    for result in json_results:
        json_results_by_key.setdefault(
            pairing_key(result[0], is_json=True), []
        ).append(result)

    missing = []
    for source_path in expected_files:
        key = pairing_key(source_path)
        roots = root_results_by_key.get(key, [])
        if is_data:
            # Corrupt/zombie data do not satisfy completeness; a readable
            # zero-entry skim does.
            covered = any(result[1] or is_empty_root_result(result) for result in roots)
        else:
            # A zombie MC skim is accounted for as produced, but its JSON is
            # required and will be excluded from normalization downstream.
            jsons = json_results_by_key.get(key, [])
            covered = bool(roots) and any(result[1] for result in jsons)
        if not covered:
            missing.append(source_path)

    return expected_files, missing, ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--era", required=True)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--root-input", required=True)
    parser.add_argument("--json-input", required=True)
    parser.add_argument("--output-manifest", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--tree", default="Events")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=2.0)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument(
        "--skip-input-completeness",
        action="store_true",
        help=(
            "Validate discovered ROOT/JSON integrity and MC pairing without "
            "comparing against the current skim chunk manifest or sample "
            "file list. Intended for archived/legacy skim productions."
        ),
    )
    args = parser.parse_args()
    if args.workers < 1 or args.retries < 1 or args.progress_every < 1:
        parser.error("--workers, --retries and --progress-every must be >= 1")
    if args.retry_delay < 0:
        parser.error("--retry-delay must be >= 0")

    analysis_path = os.environ.get(
        "ANALYSIS_PATH", str(Path(__file__).resolve().parents[1])
    )
    samples_path = os.path.join(
        analysis_path, "config", args.era, "samples.yaml"
    )
    samples = utilities.get_config(samples_path)
    samples_with_files_path = os.path.join(
        analysis_path, "config", args.era, "samples_withfiles.yaml"
    )
    samples_with_files = utilities.get_config(samples_with_files_path)
    dataset_cfg = samples.get(args.dataset_name, {})
    is_data = dataset_cfg.get("is_data", False) or "data" in args.dataset_name.lower()
    chunk_manifest_path = os.path.join(
        analysis_path,
        "htcondor",
        "log",
        args.era,
        args.dataset_name,
        "skim_chunks.json",
    )
    chunk_manifest = None
    if os.path.exists(chunk_manifest_path):
        with open(chunk_manifest_path) as chunk_manifest_handle:
            chunk_manifest = json.load(chunk_manifest_handle)
        print(
            f"[COMPLETENESS] Using chunk manifest: {chunk_manifest_path}",
            flush=True,
        )

    print(f"[DISCOVERY] Scanning ROOT input: {args.root_input}", flush=True)
    root_files = discover_root_files(args.root_input)
    if is_data:
        json_files = []
        print(
            "[DISCOVERY] Data dataset: JSON discovery and validation are disabled",
            flush=True,
        )
    else:
        print(f"[DISCOVERY] Scanning JSON input: {args.json_input}", flush=True)
        json_files = discover_json_files(args.json_input)
    print(
        f"[VALIDATION] {args.dataset_name}: discovered "
        f"{len(root_files)} ROOT and {len(json_files)} JSON files",
        flush=True,
    )
    context = multiprocessing.get_context("spawn")
    root_results = []
    root_valid_count = 0
    root_invalid_count = 0
    root_empty_count = 0
    with context.Pool(args.workers) as pool:
        results = pool.imap_unordered(
            validate_file,
            (
                (path, args.tree, args.retries, args.retry_delay)
                for path in root_files
            ),
            chunksize=1,
        )
        for done, result in enumerate(results, start=1):
            root_results.append(result)
            if result[1]:
                root_valid_count += 1
            elif is_empty_root_result(result):
                root_empty_count += 1
                disposition = (
                    "ignored for data"
                    if is_data
                    else "events skipped; JSON retained for normalization"
                )
                print(f"[ROOT EMPTY] {result[0]}: {disposition}", flush=True)
            else:
                root_invalid_count += 1
                print(f"[ROOT INVALID] {result[0]}: {result[2]}", flush=True)
            if done % args.progress_every == 0 or done == len(root_files):
                print(
                    f"[ROOT PROGRESS] {done}/{len(root_files)} checked; "
                    f"valid={root_valid_count}, empty={root_empty_count}, "
                    f"invalid={root_invalid_count}",
                    flush=True,
                )
    json_results = []
    json_valid_count = 0
    json_invalid_count = 0
    for done, path in enumerate(json_files, start=1):
        result = validate_json(path, args.retries, args.retry_delay)
        json_results.append(result)
        if result[1]:
            json_valid_count += 1
        else:
            json_invalid_count += 1
            print(f"[JSON INVALID] {result[0]}: {result[2]}", flush=True)
        if done % args.progress_every == 0 or done == len(json_files):
            print(
                f"[JSON PROGRESS] {done}/{len(json_files)} checked; "
                f"valid={json_valid_count}, invalid={json_invalid_count}",
                flush=True,
            )
    if is_data:
        valid_roots = sorted(path for path, valid, _ in root_results if valid)
        valid_jsons = sorted(path for path, valid, _ in json_results if valid)
        ignored_empty_roots = [
            {"path": path, "reason": reason}
            for path, valid, reason in root_results
            if not valid and reason.startswith("empty tree ")
        ]
        invalid_roots = [
            {"path": path, "reason": reason}
            for path, valid, reason in root_results
            if not valid and not reason.startswith("empty tree ")
        ]
        invalid_jsons = [
            {"path": path, "reason": reason}
            for path, valid, reason in json_results
            if not valid
        ]
    else:
        ignored_empty_roots = []
        print("[PAIRING] Matching validated ROOT and JSON files", flush=True)
        (
            valid_roots,
            valid_jsons,
            invalid_roots,
            invalid_jsons,
            ignored_empty_roots,
        ) = pair_mc_results(root_results, json_results)
        print(
            f"[PAIRING] accepted={len(valid_roots)} pairs; "
            f"invalid ROOT={len(invalid_roots)}; invalid JSON={len(invalid_jsons)}",
            flush=True,
        )
    if args.skip_input_completeness:
        expected_files, missing_input_files, completeness_error = [], [], ""
        print(
            "[COMPLETENESS] Skipped by explicit request; validating only "
            "discovered-file integrity and ROOT/JSON pairing.",
            flush=True,
        )
    else:
        expected_files, missing_input_files, completeness_error = (
            expected_input_completeness(
                samples_with_files,
                args.dataset_name,
                root_results,
                json_results,
                is_data,
                chunk_manifest=chunk_manifest,
            )
        )
    print(
        f"[COMPLETENESS] {args.dataset_name}: expected={len(expected_files)}, "
        f"missing={len(missing_input_files)}",
        flush=True,
    )
    failures = []
    if completeness_error:
        failures.append(completeness_error)
    if missing_input_files:
        failures.append(
            f"{len(missing_input_files)} expected skim output(s) missing or unusable"
        )
    if not valid_roots:
        print(
            "[WARNING] No processable ROOT files remain; downstream histogram "
            "production will write empty histograms.",
            flush=True,
        )
    if is_data and (invalid_roots or invalid_jsons):
        failures.append(
            f"data requires zero invalid files: {len(invalid_roots)} ROOT, "
            f"{len(invalid_jsons)} JSON"
        )
    validation_passed = not failures
    write_manifest(
        args.output_manifest,
        "validation",
        era=args.era,
        dataset=args.dataset_name,
        is_data=is_data,
        status="passed" if validation_passed else "failed",
        failures=failures,
        root_input=os.path.abspath(args.root_input),
        json_input=os.path.abspath(args.json_input),
        tree=args.tree,
        valid_root_files=valid_roots,
        valid_json_files=valid_jsons,
        invalid_root_files=invalid_roots,
        ignored_empty_root_files=ignored_empty_roots,
        invalid_json_files=invalid_jsons,
        expected_input_files=expected_files,
        missing_input_files=missing_input_files,
        summary={
            "input_expected": len(expected_files),
            "input_missing": len(missing_input_files),
            "root_valid": len(valid_roots),
            "root_invalid": len(invalid_roots),
            "root_empty_ignored": len(ignored_empty_roots),
            "json_valid": len(valid_jsons),
            "json_invalid": len(invalid_jsons),
            "json_required": not is_data,
        },
    )
    print(f"[VALIDATION] wrote {args.output_manifest}", flush=True)
    if not validation_passed:
        raise RuntimeError(
            f"Validation failed for {args.dataset_name}: " + "; ".join(failures)
        )


if __name__ == "__main__":
    main()
