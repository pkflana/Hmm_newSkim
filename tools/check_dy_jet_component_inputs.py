#!/usr/bin/env python3
"""Preflight DY skim columns required by the hard/PU component campaign."""

import argparse
import json
import sys
from pathlib import Path

import ROOT


DY_DATASETS = {
    "Run3_2022": (
        "DYto2L_M_50_amcatnloFXFX",
        "DYto2Mu_MLL_105to160_amcatnloFXFX",
    ),
    "Run3_2022EE": (
        "DYto2L_M_50_amcatnloFXFX",
        "DYto2Mu_MLL_105to160_amcatnloFXFX",
    ),
    "Run3_2023": (
        "DYto2L_M_50_amcatnloFXFX",
        "DYto2Mu_MLL_105to160_amcatnloFXFX",
    ),
    "Run3_2023BPix": (
        "DYto2L_M_50_amcatnloFXFX",
        "DYto2Mu_MLL_105to160_amcatnloFXFX",
    ),
    "Run3_2024": (
        "DYto2Mu_M_50_amcatnloFXFX",
        "DYto2Tau_M_50_amcatnloFXFX",
        "DYto2E_M_50_amcatnloFXFX",
        "DYto2Mu_MLL_105to160_amcatnloFXFX",
        "DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF",
    ),
    "Run3_2025": (
        "DYto2Mu_M_50_amcatnloFXFX",
        "DYto2Tau_M_50_amcatnloFXFX",
        "DYto2E_M_50_amcatnloFXFX",
        "DYto2Mu_MLL_105to160_amcatnloFXFX",
        "DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF",
    ),
}

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
    args = parser.parse_args()

    failures = []
    checked = 0
    for era in args.eras:
        for dataset in DY_DATASETS[era]:
            manifest = args.manifests / era / f"{dataset}.json"
            error = check_dataset(manifest)
            checked += 1
            if error:
                failures.append(f"{era}/{dataset}: {error}")
            else:
                print(f"[OK] {era}/{dataset}")

    if failures:
        print("\n[ERROR] DY jet-component preflight failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            "\nRegenerate the affected DY skims with the current "
            "analysis/jets.py before submitting this campaign.",
            file=sys.stderr,
        )
        return 1
    print(f"\n[OK] Preflight passed for {checked} DY dataset/era combinations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
