#!/usr/bin/env python3
"""Preflight skim columns required by the hard/PU component campaign."""

import argparse
import json
import sys
from pathlib import Path

import ROOT

sys.path.append(str(Path(__file__).resolve().parents[1]))
from common.dataset_utilities import (
    jet_gen_component_processes,
    load_routing,
    resolve_dataset_selection,
)

REQUIRED_ALTERNATIVES = {"SelectedJet_genJetIdx", "Jet_genJetIdx"}


def check_dataset(manifest_path):
    if not manifest_path.is_file():
        return f"missing manifest: {manifest_path}"
    with manifest_path.open() as handle:
        manifest = json.load(handle)
    root_files = manifest.get("valid_root_files", [])
    if not root_files:
        return f"manifest has no valid ROOT files: {manifest_path}"

    root_file = ROOT.TFile.Open(root_files[0], "READ")
    if not root_file or root_file.IsZombie():
        return f"cannot open representative ROOT file: {root_files[0]}"
    try:
        events = root_file.Get("Events")
        if not events:
            return f"missing Events tree: {root_files[0]}"
        columns = {branch.GetName() for branch in events.GetListOfBranches()}
    finally:
        root_file.Close()
    if not columns.intersection(REQUIRED_ALTERNATIVES):
        return (
            "missing SelectedJet_genJetIdx/Jet_genJetIdx in "
            f"{root_files[0]}"
        )
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifests", required=True, type=Path)
    parser.add_argument("--eras", nargs="+", required=True)
    parser.add_argument(
        "--processes",
        nargs="+",
        default=None,
        help=(
            "Processes to check. By default use every process enabled in "
            "config/histogram_sample_routing.yaml."
        ),
    )
    parser.add_argument(
        "--analysis-path",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()

    routing = load_routing(
        args.analysis_path / "config" / "histogram_sample_routing.yaml"
    )
    requested_processes = set(
        args.processes or jet_gen_component_processes(routing)
    )
    failures = []
    checked = 0
    for era in args.eras:
        selection = resolve_dataset_selection(args.analysis_path, era)
        process_datasets = selection["process_datasets"]
        matched_processes = [
            process for process in process_datasets if process in requested_processes
        ]
        missing_processes = sorted(requested_processes - set(process_datasets))
        for process in missing_processes:
            print(f"[SKIP] {era}/{process}: process is not selected for this era")
        for process in matched_processes:
            for dataset in process_datasets[process]:
                manifest = args.manifests / era / f"{dataset}.json"
                error = check_dataset(manifest)
                checked += 1
                if error:
                    failures.append(f"{era}/{process}/{dataset}: {error}")
                else:
                    print(f"[OK] {era}/{process}/{dataset}")

    if failures:
        print("\n[ERROR] Jet-component preflight failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            "\nRegenerate the affected skims with the current "
            "analysis/jets.py before submitting this campaign.",
            file=sys.stderr,
        )
        return 1
    print(f"\n[OK] Preflight passed for {checked} dataset/era combinations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
