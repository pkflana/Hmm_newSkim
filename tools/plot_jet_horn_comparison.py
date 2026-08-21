#!/usr/bin/env python3
"""Compare 2024 and 2025 jet-horn campaigns with Data/DY ratio panels."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import mplhep as hep
import numpy as np
import uproot


DEFAULT_BASE = Path("/eos/user/v/vdamante/H_mumu/campaigns/JetHornVetoComparison")
CAMPAIGNS = (
    ("2024", "2024/Central_hadded/Run3_2024", "#e41a1c"),
    ("2025 with horn veto", "2025_WithHornVeto/Central_hadded/Run3_2025", "#1746ff"),
    ("2025 without horn veto", "2025_NoHornVeto/Central_hadded/Run3_2025", "#006400"),
)


def histogram_keys(path: Path) -> set[str]:
    with uproot.open(path) as root_file:
        return {
            key.split(";")[0]
            for key, classname in root_file.classnames(recursive=True).items()
            if classname.startswith("TH1")
        }


def read_histogram(path: Path, key: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with uproot.open(path) as root_file:
        histogram = root_file[key]
        values = np.asarray(histogram.values(), dtype=float)
        edges = np.asarray(histogram.axis().edges(), dtype=float)
        variances = histogram.variances()
        errors = np.sqrt(np.maximum(0.0, variances)) if variances is not None else np.sqrt(np.maximum(0.0, values))
    return values, edges, errors


def safe_name(key: str) -> str:
    return key.replace("/", "__").replace(" ", "_")


def plot_one(base: Path, output: Path, key: str) -> None:
    payload = []
    for label, relative, color in CAMPAIGNS:
        folder = base / relative
        data = read_histogram(folder / "Data_Muon.root", key)
        dy = read_histogram(folder / "DY.root", key)
        if not np.array_equal(data[1], dy[1]):
            raise RuntimeError(f"Data/DY binning mismatch for {label}: {key}")
        payload.append((label, color, data, dy))

    reference = float(np.sum(payload[0][2][0]))
    if reference <= 0:
        print(f"[SKIP] Empty 2024 Data histogram: {key}")
        return

    hep.style.use("CMS")
    # Skims use sentinel-valued bins for unavailable jet observables. Trim only
    # common empty edge bins, preserving every bin populated in any campaign.
    occupied = np.zeros_like(payload[0][2][0], dtype=bool)
    for _, _, data, dy in payload:
        occupied |= (data[0] != 0) | (dy[0] != 0)
    first, last = np.flatnonzero(occupied)[[0, -1]]

    fig, (axis, ratio_axis) = plt.subplots(
        2, 1, figsize=(9, 8), sharex=True,
        gridspec_kw={"height_ratios": (3.1, 1), "hspace": 0.04},
    )

    for label, color, data, dy in payload:
        data_values, edges, data_errors = data
        dy_values, _, _ = dy
        data_values = data_values[first:last + 1]
        data_errors = data_errors[first:last + 1]
        dy_values = dy_values[first:last + 1]
        edges = edges[first:last + 2]
        centers = 0.5 * (edges[:-1] + edges[1:])

        data_scale = reference / np.sum(data_values) if np.sum(data_values) > 0 else 1.0
        dy_scale = reference / np.sum(dy_values) if np.sum(dy_values) > 0 else 1.0
        shown_data = data_values * data_scale
        shown_dy = dy_values * dy_scale

        axis.stairs(shown_dy, edges, color=color, linewidth=1.8, label=f"DY {label}")
        axis.errorbar(
            centers, shown_data, yerr=data_errors * data_scale,
            color=color, marker=".", linestyle="none", markersize=5,
            linewidth=1, label=f"Data {label}",
        )

        ratio = np.divide(shown_data, shown_dy, out=np.full_like(shown_data, np.nan), where=shown_dy != 0)
        ratio_error = np.divide(data_errors * data_scale, shown_dy, out=np.zeros_like(data_errors), where=shown_dy != 0)
        ratio_axis.errorbar(
            centers, ratio, yerr=ratio_error, color=color, marker=".",
            linestyle="-", linewidth=1.2, markersize=4, label=label,
        )

    axis.set_yscale("log")
    positive = [entry[2][0][first:last + 1][entry[2][0][first:last + 1] > 0] for entry in payload]
    positive = np.concatenate([entry for entry in positive if entry.size])
    axis.set_ylim(max(0.1, positive.min() * 0.3), None)
    axis.set_ylabel("Events normalized to 2024 data", fontsize=18)
    axis.legend(ncol=2, fontsize=11, loc="best")
    hep.cms.label("Preliminary", data=True, com=13.6, ax=axis)

    ratio_axis.axhspan(0.8, 1.2, color="#9ecae1", alpha=0.25, label="20% variation")
    ratio_axis.axhline(1.0, color="black", linewidth=1)
    ratio_axis.set_ylim(0.5, 1.5)
    ratio_axis.set_ylabel("Data / DY", fontsize=18)
    ratio_axis.set_xlabel(key.rsplit("/", 1)[-1], fontsize=18)
    ratio_axis.legend(ncol=2, fontsize=9, loc="upper center")
    ratio_axis.grid(axis="y", alpha=0.2)
    fig.subplots_adjust(left=0.16, right=0.97, top=0.91, bottom=0.12)

    destination = output / key.rsplit("/", 1)[0]
    destination.mkdir(parents=True, exist_ok=True)
    stem = destination / key.rsplit("/", 1)[-1]
    fig.savefig(stem.with_suffix(".png"), dpi=160, bbox_inches="tight")
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"[PLOT] {stem}.png")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--output", type=Path, default=Path("plots/jet_horn_comparison"))
    parser.add_argument("--region", action="append", help="Only plot this region; repeatable")
    parser.add_argument("--variable", action="append", help="Only plot this variable; repeatable")
    args = parser.parse_args()

    files = [args.base / relative / sample for _, relative, _ in CAMPAIGNS for sample in ("Data_Muon.root", "DY.root")]
    missing = [path for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required ROOT files:\n" + "\n".join(map(str, missing)))

    keys = set.intersection(*(histogram_keys(path) for path in files))
    if args.region:
        regions = set(args.region)
        keys = {key for key in keys if key.rsplit("/", 1)[0] in regions}
    if args.variable:
        variables = set(args.variable)
        keys = {key for key in keys if key.rsplit("/", 1)[-1] in variables}

    print(f"Common one-dimensional histograms: {len(keys)}")
    for key in sorted(keys):
        plot_one(args.base, args.output, key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
