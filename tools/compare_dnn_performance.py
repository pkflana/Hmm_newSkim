#!/usr/bin/env python3
"""Compare DNN ROC curves and threshold performance from Central histograms."""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import sys
from pathlib import Path

import numpy as np


def csv_items(values: list[str]) -> list[str]:
    return [
        item.strip()
        for value in values
        for item in value.split(",")
        if item.strip()
    ]


def central_directory(path: Path) -> Path:
    candidate = path / "Hists_Central"
    return candidate if candidate.is_dir() else path


def matches(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def read_histogram(path: Path, object_path: str) -> tuple[np.ndarray, np.ndarray]:
    import ROOT

    root_file = ROOT.TFile.Open(str(path), "READ")
    if not root_file or root_file.IsZombie():
        raise OSError(f"cannot open {path}")
    histogram = root_file.Get(object_path)
    if not histogram or not histogram.InheritsFrom(ROOT.TH1.Class()):
        root_file.Close()
        raise KeyError(f"{object_path} not found in {path.name}")
    contents = np.asarray(
        [
            float(histogram.GetBinContent(index))
            for index in range(1, histogram.GetNbinsX() + 1)
        ],
        dtype=np.float64,
    )
    edges = np.asarray(
        [
            float(histogram.GetXaxis().GetBinLowEdge(index))
            for index in range(1, histogram.GetNbinsX() + 2)
        ],
        dtype=np.float64,
    )
    root_file.Close()
    return contents, edges


def collect(
    era_dir: Path,
    object_path: str,
    signal_patterns: list[str],
    background_patterns: list[str],
    exclude_patterns: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], list[str]]:
    signal = None
    background = None
    edges = None
    signal_files = []
    background_files = []

    for path in sorted(era_dir.glob("*.root")):
        stem = path.stem
        is_signal = matches(stem, signal_patterns)
        is_background = (
            not is_signal
            and not stem.lower().startswith(("data", "muon", "singlemuon"))
            and matches(stem, background_patterns)
            and not matches(stem, exclude_patterns)
        )
        if not is_signal and not is_background:
            continue
        try:
            contents, current_edges = read_histogram(path, object_path)
        except (OSError, KeyError) as error:
            print(f"[WARNING] {error}", file=sys.stderr)
            continue
        if edges is not None and not np.allclose(edges, current_edges):
            raise ValueError(f"incompatible binning in {path}")
        edges = current_edges
        if is_signal:
            signal = contents.copy() if signal is None else signal + contents
            signal_files.append(stem)
        else:
            background = (
                contents.copy() if background is None else background + contents
            )
            background_files.append(stem)

    if signal is None:
        raise RuntimeError(f"no signal histograms found in {era_dir}")
    if background is None:
        raise RuntimeError(f"no background histograms found in {era_dir}")
    return signal, background, edges, signal_files, background_files


def background_efficiency_at_signal_efficiency(
    tpr: np.ndarray, fpr: np.ndarray, target: float
) -> float:
    """Return the best (lowest) background efficiency reaching target signal."""
    candidates = fpr[tpr >= target]
    return float(np.min(candidates)) if candidates.size else math.nan


def metrics(
    signal: np.ndarray,
    background: np.ndarray,
    edges: np.ndarray,
    working_points: tuple[float, ...] = (0.5, 0.7, 0.8, 0.9),
) -> dict:
    negative_signal = float(np.sum(signal[signal < 0]))
    negative_background = float(np.sum(background[background < 0]))
    # Negative-weight cancellation happens before this clipping. Clipping the
    # remaining negative bins keeps efficiencies monotonic and interpretable.
    signal = np.clip(signal, 0.0, None)
    background = np.clip(background, 0.0, None)
    signal_yield = float(np.sum(signal))
    background_yield = float(np.sum(background))
    if signal_yield <= 0 or background_yield <= 0:
        raise RuntimeError("signal and background integrals must both be positive")

    signal_above = np.r_[np.cumsum(signal[::-1])[::-1], 0.0]
    background_above = np.r_[np.cumsum(background[::-1])[::-1], 0.0]
    tpr = signal_above / signal_yield
    fpr = background_above / background_yield
    auc = float(np.trapz(tpr[::-1], fpr[::-1]))
    denominator = np.sqrt(np.maximum(signal_above + background_above, 0.0))
    significance = np.divide(
        signal_above,
        denominator,
        out=np.zeros_like(signal_above),
        where=denominator > 0,
    )
    best = int(np.argmax(significance))
    return {
        "auc": auc,
        "signal_yield": signal_yield,
        "background_yield": background_yield,
        "negative_signal_sum": negative_signal,
        "negative_background_sum": negative_background,
        "best_threshold": float(edges[best]),
        "best_significance": float(significance[best]),
        "signal_efficiency_at_best": float(tpr[best]),
        "background_efficiency_at_best": float(fpr[best]),
        "background_efficiency_at_signal_efficiency": {
            f"{target:.2f}": background_efficiency_at_signal_efficiency(
                tpr, fpr, target
            )
            for target in working_points
        },
        "thresholds": edges.tolist(),
        "tpr": tpr.tolist(),
        "fpr": fpr.tolist(),
        "significance": significance.tolist(),
    }


def relative_change(updated: float, legacy: float) -> float:
    return (updated / legacy - 1.0) if legacy else math.nan


def compare_results(legacy: dict, updated: dict) -> dict:
    """Compact direct comparison; positive deltas favour the updated model."""
    working_points = sorted(
        set(legacy["background_efficiency_at_signal_efficiency"])
        & set(updated["background_efficiency_at_signal_efficiency"])
    )
    background = {}
    for point in working_points:
        old = legacy["background_efficiency_at_signal_efficiency"][point]
        new = updated["background_efficiency_at_signal_efficiency"][point]
        background[point] = {
            "legacy": old,
            "updated": new,
            "absolute_reduction": old - new,
            "relative_reduction": (1.0 - new / old) if old else math.nan,
        }
    return {
        "auc_delta": updated["auc"] - legacy["auc"],
        "auc_relative_change": relative_change(updated["auc"], legacy["auc"]),
        "best_significance_delta": (
            updated["best_significance"] - legacy["best_significance"]
        ),
        "best_significance_relative_change": relative_change(
            updated["best_significance"], legacy["best_significance"]
        ),
        "background_efficiency_at_signal_efficiency": background,
    }


def parse_campaign(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("use LABEL=PATH")
    label, path = value.split("=", 1)
    if not label or not path:
        raise argparse.ArgumentTypeError("use a non-empty LABEL=PATH")
    return label, Path(path).expanduser()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build ROC/AUC and S/sqrt(S+B) comparisons from DNN_NNOutput "
            "histograms in one or more Central campaigns."
        )
    )
    parser.add_argument(
        "--campaign",
        action="append",
        type=parse_campaign,
        required=True,
        metavar="LABEL=PATH",
        help="repeat to compare legacy and updated campaigns",
    )
    parser.add_argument("--era", required=True, help="for example 2023")
    parser.add_argument("--region", default="Signal_Fit_VBF/incl")
    parser.add_argument("--variable", default="DNN_NNOutput")
    parser.add_argument(
        "--signal-pattern",
        action="append",
        required=True,
        help="signal filename glob; repeat or comma-separate",
    )
    parser.add_argument(
        "--background-pattern",
        action="append",
        default=None,
        help="background filename glob; default: every non-data, non-signal file",
    )
    parser.add_argument(
        "--exclude-pattern",
        action="append",
        default=["*Hto2Mu*"],
        help=(
            "filename glob excluded from background; selected signals take "
            "precedence (default excludes alternate H->mumu samples)"
        ),
    )
    parser.add_argument("--output", type=Path, default=Path("dnn_performance"))
    parser.add_argument(
        "--working-point",
        action="append",
        type=float,
        default=[],
        help="signal efficiency for background-rejection comparison; repeatable",
    )
    args = parser.parse_args()

    era = args.era if args.era.startswith("Run3_") else f"Run3_{args.era}"
    signal_patterns = csv_items(args.signal_pattern)
    background_patterns = csv_items(args.background_pattern or ["*"])
    exclude_patterns = csv_items(args.exclude_pattern)
    working_points = tuple(args.working_point or (0.5, 0.7, 0.8, 0.9))
    if any(point <= 0 or point > 1 for point in working_points):
        parser.error("--working-point must be in (0, 1]")
    object_path = f"{args.region.rstrip('/')}/{args.variable}"
    results = {}

    for label, campaign in args.campaign:
        era_dir = central_directory(campaign.resolve()) / era
        signal, background, edges, signal_files, background_files = collect(
            era_dir,
            object_path,
            signal_patterns,
            background_patterns,
            exclude_patterns,
        )
        result = metrics(signal, background, edges, working_points)
        result["campaign"] = str(campaign)
        result["signal_files"] = signal_files
        result["background_files"] = background_files
        results[label] = result
        print(
            f"{label}: AUC={result['auc']:.5f}, "
            f"best S/sqrt(S+B)={result['best_significance']:.5g} "
            f"at DNN>{result['best_threshold']:.5g} "
            f"(signal={len(signal_files)} files, "
            f"background={len(background_files)} files)"
        )

    comparison = None
    if len(results) == 2:
        labels = list(results)
        legacy_label = next(
            (label for label in labels if label.lower() in {"old", "legacy", "vecchia"}),
            labels[0],
        )
        updated_label = next(
            (
                label
                for label in labels
                if label != legacy_label
                and label.lower() in {"new", "updated", "nuova"}
            ),
            next(label for label in labels if label != legacy_label),
        )
        comparison = {
            "legacy_label": legacy_label,
            "updated_label": updated_label,
            **compare_results(results[legacy_label], results[updated_label]),
        }
        print(
            "comparison: "
            f"delta AUC={comparison['auc_delta']:+.5f}, "
            "delta best S/sqrt(S+B)="
            f"{comparison['best_significance_delta']:+.5g}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    json_path = args.output.with_suffix(".json")
    png_path = args.output.with_suffix(".png")
    with json_path.open("w") as handle:
        json.dump(
            {
                "era": era,
                "object": object_path,
                "signal_patterns": signal_patterns,
                "background_patterns": background_patterns,
                "exclude_patterns": exclude_patterns,
                "results": results,
                "comparison": comparison,
            },
            handle,
            indent=2,
        )

    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    for label, result in results.items():
        axes[0].plot(result["fpr"], result["tpr"], label=f"{label} (AUC={result['auc']:.3f})")
        axes[1].plot(result["thresholds"], result["significance"], label=label)
    axes[0].plot([0, 1], [0, 1], linestyle="--", color="0.6")
    axes[0].set(xlabel="Background efficiency", ylabel="Signal efficiency", xlim=(0, 1), ylim=(0, 1))
    axes[1].set(xlabel=f"{args.variable} threshold", ylabel=r"$S/\sqrt{S+B}$")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend()
    figure.suptitle(f"{era} — {args.region}")
    figure.tight_layout()
    figure.savefig(png_path, dpi=160)
    print(f"Wrote {png_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
