#!/usr/bin/env python3
"""Optimize a DNN threshold and a contiguous multibin categorization.

The input is a directory of per-process ROOT files, such as
Hists_Central_hadded/Run3_2024. Signal and background files are selected with
explicit, repeatable glob patterns. Data are always rejected from background.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
from pathlib import Path

import numpy as np


def csv_items(values: list[str] | None) -> list[str]:
    return [
        item.strip()
        for value in values or []
        for item in value.split(",")
        if item.strip()
    ]


def matches(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def read_histogram(path: Path, object_path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    import ROOT

    root_file = ROOT.TFile.Open(str(path), "READ")
    if not root_file or root_file.IsZombie():
        raise OSError(f"cannot open {path}")
    histogram = root_file.Get(object_path)
    if not histogram or not histogram.InheritsFrom(ROOT.TH1.Class()):
        root_file.Close()
        raise KeyError(f"{object_path} not found in {path.name}")
    contents = np.asarray(
        [histogram.GetBinContent(i) for i in range(1, histogram.GetNbinsX() + 1)],
        dtype=float,
    )
    variances = np.asarray(
        [histogram.GetBinError(i) ** 2 for i in range(1, histogram.GetNbinsX() + 1)],
        dtype=float,
    )
    edges = np.asarray(
        [histogram.GetXaxis().GetBinLowEdge(i) for i in range(1, histogram.GetNbinsX() + 2)],
        dtype=float,
    )
    root_file.Close()
    return contents, variances, edges


def collect(
    era_dir: Path,
    object_path: str,
    signal_patterns: list[str],
    background_patterns: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str], list[str]]:
    signal = background = background_variance = edges = None
    signal_files: list[str] = []
    background_files: list[str] = []
    for path in sorted(era_dir.glob("*.root")):
        stem = path.stem
        is_signal = matches(stem, signal_patterns)
        is_background = (
            not is_signal
            and not stem.lower().startswith(("data", "muon", "singlemuon"))
            and matches(stem, background_patterns)
        )
        if not is_signal and not is_background:
            continue
        contents, variances, current_edges = read_histogram(path, object_path)
        if edges is not None and not np.allclose(edges, current_edges):
            raise ValueError(f"incompatible binning in {path}")
        edges = current_edges
        if is_signal:
            signal = contents.copy() if signal is None else signal + contents
            signal_files.append(stem)
        else:
            background = contents.copy() if background is None else background + contents
            background_variance = (
                variances.copy()
                if background_variance is None
                else background_variance + variances
            )
            background_files.append(stem)
    if signal is None:
        raise RuntimeError(f"no signal histograms found in {era_dir}")
    if background is None or background_variance is None or edges is None:
        raise RuntimeError(f"no background histograms found in {era_dir}")
    return signal, background, background_variance, edges, signal_files, background_files


def asimov_q(signal: float, background: float, relative_systematic: float = 0.0) -> float:
    """Return the Asimov discovery significance squared.

    With a nonzero background systematic this uses the profile-likelihood
    expression from Cowan et al., EPJC 71 (2011) 1554, eq. 71.
    """
    s, b = max(float(signal), 0.0), max(float(background), 0.0)
    if s <= 0.0 or b <= 0.0:
        return 0.0
    sigma2 = (relative_systematic * b) ** 2
    if sigma2 <= 0.0:
        return 2.0 * ((s + b) * math.log1p(s / b) - s)
    first = (s + b) * math.log((s + b) * (b + sigma2) / (b * b + (s + b) * sigma2))
    second = (b * b / sigma2) * math.log1p(sigma2 * s / (b * (b + sigma2)))
    return max(2.0 * (first - second), 0.0)


def valid_bin(background: float, variance: float, min_background: float, max_rel_stat: float) -> bool:
    if background < min_background or background <= 0.0:
        return False
    return math.sqrt(max(variance, 0.0)) / background <= max_rel_stat


def interval_sums(prefix: np.ndarray, lo: int, hi: int) -> float:
    return float(prefix[hi] - prefix[lo])


def optimize_threshold(
    signal: np.ndarray,
    background: np.ndarray,
    variance: np.ndarray,
    edges: np.ndarray,
    min_background: float,
    max_rel_stat: float,
    relative_systematic: float,
) -> dict:
    rows = []
    for index in range(len(signal)):
        s = float(np.sum(signal[index:]))
        b = float(np.sum(background[index:]))
        v = float(np.sum(variance[index:]))
        if not valid_bin(b, v, min_background, max_rel_stat):
            continue
        q = asimov_q(s, b, relative_systematic)
        rows.append(
            {
                "threshold": float(edges[index]),
                "signal": s,
                "background": b,
                "background_stat_error": math.sqrt(max(v, 0.0)),
                "significance": math.sqrt(q),
            }
        )
    if not rows:
        raise RuntimeError("no threshold satisfies the background constraints")
    return {"best": max(rows, key=lambda row: row["significance"]), "scan": rows}


def optimize_binning(
    signal: np.ndarray,
    background: np.ndarray,
    variance: np.ndarray,
    edges: np.ndarray,
    max_bins: int,
    min_background: float,
    max_rel_stat: float,
    relative_systematic: float,
) -> dict:
    """Dynamic-programming optimization of contiguous bins over the full range."""
    n = len(signal)
    ps = np.r_[0.0, np.cumsum(signal)]
    pb = np.r_[0.0, np.cumsum(background)]
    pv = np.r_[0.0, np.cumsum(variance)]
    score = np.full((max_bins + 1, n + 1), -np.inf)
    previous = np.full((max_bins + 1, n + 1), -1, dtype=int)
    score[0, 0] = 0.0
    for count in range(1, max_bins + 1):
        for hi in range(1, n + 1):
            for lo in range(count - 1, hi):
                if not np.isfinite(score[count - 1, lo]):
                    continue
                s = interval_sums(ps, lo, hi)
                b = interval_sums(pb, lo, hi)
                v = interval_sums(pv, lo, hi)
                if not valid_bin(b, v, min_background, max_rel_stat):
                    continue
                candidate = score[count - 1, lo] + asimov_q(s, b, relative_systematic)
                if candidate > score[count, hi]:
                    score[count, hi] = candidate
                    previous[count, hi] = lo
    valid_counts = [count for count in range(1, max_bins + 1) if np.isfinite(score[count, n])]
    if not valid_counts:
        raise RuntimeError("no binning satisfies the background constraints")
    count = max(valid_counts, key=lambda value: score[value, n])
    intervals = []
    hi = n
    while count:
        lo = int(previous[count, hi])
        intervals.append((lo, hi))
        hi, count = lo, count - 1
    intervals.reverse()
    bins = []
    for lo, hi in intervals:
        s = interval_sums(ps, lo, hi)
        b = interval_sums(pb, lo, hi)
        v = interval_sums(pv, lo, hi)
        bins.append(
            {
                "low": float(edges[lo]),
                "high": float(edges[hi]),
                "signal": s,
                "background": b,
                "background_stat_error": math.sqrt(max(v, 0.0)),
                "significance": math.sqrt(asimov_q(s, b, relative_systematic)),
            }
        )
    return {
        "edges": [bins[0]["low"], *[item["high"] for item in bins]],
        "bins": bins,
        "combined_significance": math.sqrt(sum(item["significance"] ** 2 for item in bins)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Hists_Central_hadded directory")
    parser.add_argument("--era", required=True, help="Run3_2024 or 2024")
    parser.add_argument("--region", default="Signal_Fit_VBF")
    parser.add_argument("--variable", default="DNN_NNOutput")
    parser.add_argument("--signal-pattern", action="append", required=True)
    parser.add_argument("--background-pattern", action="append", required=True)
    parser.add_argument("--max-bins", type=int, default=5)
    parser.add_argument("--min-background", type=float, default=5.0)
    parser.add_argument("--max-relative-background-stat", type=float, default=0.5)
    parser.add_argument("--relative-background-systematic", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=Path("dnn_binning_optimization"))
    args = parser.parse_args()
    if args.max_bins < 1:
        parser.error("--max-bins must be positive")
    if args.min_background <= 0:
        parser.error("--min-background must be positive")
    if args.max_relative_background_stat <= 0:
        parser.error("--max-relative-background-stat must be positive")
    if args.relative_background_systematic < 0:
        parser.error("--relative-background-systematic cannot be negative")

    era = args.era if args.era.startswith("Run3_") else f"Run3_{args.era}"
    era_dir = args.input.resolve()
    if era_dir.name != era:
        era_dir /= era
    object_path = f"{args.region.rstrip('/')}/{args.variable}"
    signal_patterns = csv_items(args.signal_pattern)
    background_patterns = csv_items(args.background_pattern)
    signal, background, variance, edges, signal_files, background_files = collect(
        era_dir, object_path, signal_patterns, background_patterns
    )
    negative_signal = float(np.sum(signal[signal < 0.0]))
    negative_background = float(np.sum(background[background < 0.0]))
    signal = np.clip(signal, 0.0, None)
    background = np.clip(background, 0.0, None)
    threshold = optimize_threshold(
        signal,
        background,
        variance,
        edges,
        args.min_background,
        args.max_relative_background_stat,
        args.relative_background_systematic,
    )
    binning = optimize_binning(
        signal,
        background,
        variance,
        edges,
        args.max_bins,
        args.min_background,
        args.max_relative_background_stat,
        args.relative_background_systematic,
    )
    result = {
        "era": era,
        "object": object_path,
        "input": str(era_dir),
        "signal_patterns": signal_patterns,
        "background_patterns": background_patterns,
        "signal_files": signal_files,
        "background_files": background_files,
        "negative_bin_sums_before_clipping": {
            "signal": negative_signal,
            "background": negative_background,
        },
        "constraints": {
            "max_bins": args.max_bins,
            "min_background": args.min_background,
            "max_relative_background_stat": args.max_relative_background_stat,
            "relative_background_systematic": args.relative_background_systematic,
        },
        "optimal_threshold": threshold["best"],
        "optimal_binning": binning,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    json_path = args.output.with_suffix(".json")
    png_path = args.output.with_suffix(".png")
    with json_path.open("w") as handle:
        json.dump(result, handle, indent=2)

    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    rows = threshold["scan"]
    axes[0].plot([row["threshold"] for row in rows], [row["significance"] for row in rows])
    best = threshold["best"]
    axes[0].axvline(best["threshold"], color="crimson", linestyle="--", label=f"best > {best['threshold']:.3g}")
    axes[0].set(xlabel="DNN threshold", ylabel="Asimov significance")
    centers = 0.5 * (edges[:-1] + edges[1:])
    widths = np.diff(edges)
    axes[1].bar(centers, background, width=widths, alpha=0.55, label="Background")
    axes[1].step(edges, np.r_[signal, signal[-1]], where="post", color="crimson", label="Signal")
    for edge in binning["edges"][1:-1]:
        axes[1].axvline(edge, color="black", linestyle="--", alpha=0.7)
    axes[1].set(xlabel=args.variable, ylabel="Expected events", yscale="log")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend()
    figure.suptitle(f"{era} — {args.region}")
    figure.tight_layout()
    figure.savefig(png_path, dpi=160)
    print(f"Best cut: {args.variable} > {best['threshold']:.6g}, Z_A={best['significance']:.6g}")
    print(f"Optimal bin edges ({len(binning['bins'])} bins): {binning['edges']}")
    print(f"Combined Z_A={binning['combined_significance']:.6g}")
    print(f"Signal files ({len(signal_files)}): {', '.join(signal_files)}")
    print(f"Background files ({len(background_files)}): {', '.join(background_files)}")
    print(f"Wrote {png_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
