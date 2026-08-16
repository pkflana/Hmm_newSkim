#!/usr/bin/env python3
"""Copy hadded ROOT files and rebin one histogram using optimized edges."""

from __future__ import annotations

import argparse
import shutil
from array import array
from pathlib import Path

import yaml


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_BINNING_CONFIG = REPOSITORY / "config/plot/binning_erabased_DNN.yaml"


def normalize_era(era: str) -> str:
    return era if era.startswith("Run3_") else f"Run3_{era}"


def load_edges(path: Path, era: str) -> list[float]:
    with path.open() as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid binning configuration in {path}: expected a mapping")
    if era not in payload:
        available = ", ".join(sorted(str(key) for key in payload))
        raise ValueError(
            f"era {era} is not defined in {path} (available: {available})"
        )
    try:
        edges = [float(value) for value in payload[era]]
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid bin edges for {era} in {path}") from error
    if len(edges) < 2 or any(high <= low for low, high in zip(edges, edges[1:])):
        raise ValueError(f"invalid bin edges for {era} in {path}: {edges}")
    return edges


def rebin_file(path: Path, object_path: str, edges: list[float]) -> bool:
    import ROOT

    root_file = ROOT.TFile.Open(str(path), "UPDATE")
    if not root_file or root_file.IsZombie():
        raise OSError(f"cannot update {path}")
    histogram = root_file.Get(object_path)
    if not histogram or not histogram.InheritsFrom(ROOT.TH1.Class()):
        root_file.Close()
        return False
    directory_path, name = object_path.rsplit("/", 1)
    directory = root_file.GetDirectory(directory_path)
    if not directory:
        root_file.Close()
        return False
    old_low = float(histogram.GetXaxis().GetXmin())
    old_high = float(histogram.GetXaxis().GetXmax())
    tolerance = 1e-6
    if edges[0] < old_low - tolerance or edges[-1] > old_high + tolerance:
        root_file.Close()
        raise ValueError(
            f"requested range [{edges[0]}, {edges[-1]}] is outside "
            f"[{old_low}, {old_high}] in {path}"
        )
    original_edges = [
        float(histogram.GetXaxis().GetBinLowEdge(index))
        for index in range(1, histogram.GetNbinsX() + 2)
    ]
    snapped_edges = []
    for requested in edges:
        closest = min(original_edges, key=lambda existing: abs(existing - requested))
        if abs(closest - requested) > tolerance:
            root_file.Close()
            raise ValueError(
                f"requested edge {requested} does not match an original bin edge "
                f"in {path} (closest is {closest})"
            )
        snapped_edges.append(closest)
    directory.cd()
    temporary_name = f"{name}__optimized_rebin"
    rebinned = histogram.Rebin(
        len(snapped_edges) - 1,
        temporary_name,
        array("d", snapped_edges),
    )
    if not rebinned:
        root_file.Close()
        raise RuntimeError(f"ROOT failed to rebin {object_path} in {path}")
    # Detach the new histogram before deleting the old key: after SetName both
    # otherwise share the same directory/name and ROOT may delete the new one.
    rebinned.SetDirectory(0)
    rebinned.SetName(name)
    rebinned.SetTitle(histogram.GetTitle())
    directory.Delete(f"{name};*")
    directory.cd()
    rebinned.SetDirectory(directory)
    rebinned.Write(name, ROOT.TObject.kOverwrite)
    root_file.Close()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="one hadded era directory")
    parser.add_argument("--output", type=Path, required=True, help="output era directory")
    parser.add_argument(
        "--era",
        help="era whose binning to use, e.g. 2024 or Run3_2024 "
        "(default: input directory name)",
    )
    parser.add_argument(
        "--binning-config",
        type=Path,
        default=DEFAULT_BINNING_CONFIG,
        help=f"era-based binning YAML (default: {DEFAULT_BINNING_CONFIG})",
    )
    parser.add_argument("--region", default="Signal_Fit_VBF")
    parser.add_argument("--variable", default="DNN_NNOutput")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    source_files = sorted(args.input.glob("*.root"))
    if not source_files:
        parser.error(f"no ROOT files found in {args.input}")
    if args.output.exists() and any(args.output.iterdir()) and not args.overwrite:
        parser.error(f"{args.output} is not empty; use --overwrite")
    args.output.mkdir(parents=True, exist_ok=True)
    era = normalize_era(args.era or args.input.resolve().name)
    try:
        edges = load_edges(args.binning_config, era)
    except (OSError, ValueError, yaml.YAMLError) as error:
        parser.error(str(error))
    object_path = f"{args.region.rstrip('/')}/{args.variable}"
    changed = 0
    missing = []
    for source in source_files:
        destination = args.output / source.name
        shutil.copy2(source, destination)
        if rebin_file(destination, object_path, edges):
            changed += 1
        else:
            missing.append(source.name)
    print(f"Era: {era}")
    print(f"Edges ({args.binning_config}): {edges}")
    print(f"Copied {len(source_files)} ROOT files to {args.output}")
    print(f"Rebinned {object_path} in {changed} files")
    if missing:
        print(f"Histogram absent in {len(missing)} files: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
