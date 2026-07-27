#!/usr/bin/env python3
"""Validate configured DNN features against preprocessing embedded in ONNX."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import yaml


def load_toml(path: Path) -> dict:
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError as error:
            raise RuntimeError(
                "Python 3.11+ or the tomli package is required to read TOML"
            ) from error
    with path.open("rb") as handle:
        return tomllib.load(handle)


def configured_features(config_dir: Path) -> list[str]:
    columns_path = config_dir / "columns_config.yaml"
    if columns_path.is_file():
        with columns_path.open() as handle:
            columns = yaml.safe_load(handle)
        if isinstance(columns, dict) and "features" in columns:
            return list(dict.fromkeys(columns["features"]))
        raise ValueError(
            f"{columns_path} must contain a top-level 'features' list"
        )

    config = load_toml(config_dir / "config.toml")
    features = config.get("dataset", {}).get("data_columns")
    if not features:
        raise ValueError(
            f"No features found in {columns_path} or "
            f"{config_dir / 'config.toml'}"
        )
    return list(dict.fromkeys(features))


def constant_arrays(model) -> dict[str, np.ndarray]:
    from onnx import numpy_helper

    arrays = {}
    for node in model.graph.node:
        if node.op_type != "Constant" or not node.output:
            continue
        value_attribute = next(
            (attribute for attribute in node.attribute if attribute.name == "value"),
            None,
        )
        if value_attribute is not None:
            arrays[node.output[0]] = numpy_helper.to_array(value_attribute.t)
    return arrays


def embedded_standardization(model) -> tuple[np.ndarray, np.ndarray]:
    """Return mean and standard deviation from the input Sub -> Div chain."""
    constants = constant_arrays(model)
    input_names = {value.name for value in model.graph.input}

    subtraction = next(
        (
            node
            for node in model.graph.node
            if node.op_type == "Sub"
            and any(name in input_names for name in node.input)
            and any(name in constants for name in node.input)
        ),
        None,
    )
    if subtraction is None:
        raise ValueError("no input Sub node with a constant mean was found")

    mean_name = next(name for name in subtraction.input if name in constants)
    subtraction_output = subtraction.output[0]
    division = next(
        (
            node
            for node in model.graph.node
            if node.op_type == "Div"
            and subtraction_output in node.input
            and any(name in constants for name in node.input)
        ),
        None,
    )
    if division is None:
        raise ValueError("no Div node with a constant scale was found after Sub")

    std_name = next(name for name in division.input if name in constants)
    return (
        np.asarray(constants[mean_name], dtype=np.float64).reshape(-1),
        np.asarray(constants[std_name], dtype=np.float64).reshape(-1),
    )


def model_input_width(model) -> int | None:
    if not model.graph.input:
        return None
    dimensions = model.graph.input[0].type.tensor_type.shape.dim
    if not dimensions:
        return None
    last = dimensions[-1]
    return int(last.dim_value) if last.HasField("dim_value") else None


def inspect_models(
    config_dir: Path,
    models_dir: Path,
    std_threshold: float,
) -> int:
    try:
        import onnx
    except ImportError as error:
        raise RuntimeError(
            "The onnx package is required. Run 'source env.sh' first."
        ) from error

    features = configured_features(config_dir)
    model_paths = sorted(models_dir.glob("trained_model_*.onnx"))
    if not model_paths:
        raise FileNotFoundError(
            f"No trained_model_*.onnx files found in {models_dir}"
        )

    problems = []
    model_stats = []
    for model_path in model_paths:
        model = onnx.load(str(model_path))
        width = model_input_width(model)
        mean, std = embedded_standardization(model)
        model_stats.append((model_path, mean, std))

        if width is not None and width != len(features):
            problems.append(
                f"{model_path.name}: model input width {width} != "
                f"{len(features)} configured features"
            )
        if len(mean) != len(features) or len(std) != len(features):
            problems.append(
                f"{model_path.name}: preprocessing vectors have lengths "
                f"mean={len(mean)}, std={len(std)}, expected={len(features)}"
            )

    print(f"Configuration: {config_dir}")
    print(f"Models:        {models_dir}")
    print(f"Features:      {len(features)}")
    print(f"Folds:         {len(model_stats)}")
    print(f"Std threshold: {std_threshold:g}")
    print()
    print(
        f"{'#':>3}  {'feature':<34} "
        + "  ".join(
            f"{path.stem.replace('trained_model_', 'fold '):>24}"
            for path, _, _ in model_stats
        )
    )
    print("-" * (40 + 26 * len(model_stats)))

    for index, feature in enumerate(features):
        cells = []
        feature_problem = False
        for model_path, means, stds in model_stats:
            if index >= len(means) or index >= len(stds):
                cells.append("missing")
                feature_problem = True
                continue
            mean = means[index]
            std = stds[index]
            status = "OK"
            if not np.isfinite(mean) or not np.isfinite(std):
                status = "NONFINITE"
                feature_problem = True
                problems.append(
                    f"{model_path.name}: {feature} has mean={mean}, std={std}"
                )
            elif abs(std) <= std_threshold:
                status = "ZERO_VAR"
                feature_problem = True
                problems.append(
                    f"{model_path.name}: {feature} has effectively zero "
                    f"variance (mean={mean:.16g}, std={std:.16g})"
                )
            elif std < 0:
                status = "NEG_STD"
                feature_problem = True
                problems.append(
                    f"{model_path.name}: {feature} has negative std={std}"
                )
            cells.append(f"mu={mean:9.3g} sd={std:9.3g} {status}")

        marker = "!" if feature_problem else " "
        print(f"{index:3d}{marker} {feature:<34} " + "  ".join(cells))

    reference_mean = model_stats[0][1]
    reference_std = model_stats[0][2]
    for model_path, mean, std in model_stats[1:]:
        if mean.shape == reference_mean.shape and not np.allclose(
            mean, reference_mean, rtol=1.0e-6, atol=1.0e-9
        ):
            print(
                f"\n[INFO] {model_path.name} has fold-specific means; "
                "this is allowed but should be intentional."
            )
        if std.shape == reference_std.shape and not np.allclose(
            std, reference_std, rtol=1.0e-6, atol=1.0e-9
        ):
            print(
                f"\n[INFO] {model_path.name} has fold-specific standard "
                "deviations; this is allowed but should be intentional."
            )

    print()
    if problems:
        print(f"[FAIL] Found {len(problems)} model-input problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("[OK] Feature order, dimensions, and preprocessing constants look valid.")
    return 0


ERA_CODES = {
    "Run3_2022": 0,
    "Run3_2022EE": 1,
    "Run3_2023": 2,
    "Run3_2023BPix": 3,
    "Run3_2024": 4,
    "Run3_2025": 5,
}


def central_histogram_directory(path: Path) -> Path:
    candidate = path / "Hists_Central"
    return candidate if candidate.is_dir() else path


def histogram_moments(files: list[Path], object_path: str):
    import ROOT

    sum_weight = 0.0
    sum_weight_x = 0.0
    sum_weight_x2 = 0.0
    found = 0
    for file_path in files:
        root_file = ROOT.TFile.Open(str(file_path), "READ")
        if not root_file or root_file.IsZombie():
            continue
        histogram = root_file.Get(object_path)
        if histogram and histogram.InheritsFrom(ROOT.TH1.Class()):
            found += 1
            for index in range(1, histogram.GetNbinsX() + 1):
                # Absolute contents avoid cancellations between negative and
                # positive MC weights in this shape diagnostic.
                weight = abs(float(histogram.GetBinContent(index)))
                center = float(histogram.GetBinCenter(index))
                sum_weight += weight
                sum_weight_x += weight * center
                sum_weight_x2 += weight * center * center
        root_file.Close()

    if found == 0 or sum_weight == 0.0:
        return None
    mean = sum_weight_x / sum_weight
    variance = max(0.0, sum_weight_x2 / sum_weight - mean * mean)
    return mean, float(np.sqrt(variance)), found


def compare_central_histograms(
    config_dir: Path,
    models_dir: Path,
    histogram_base: Path,
    region: str,
    requested_eras: list[str],
    max_files: int | None,
    std_threshold: float,
    mean_z_threshold: float,
    min_std_ratio: float,
    max_std_ratio: float,
) -> int:
    import onnx

    features = configured_features(config_dir)
    model_paths = sorted(models_dir.glob("trained_model_*.onnx"))
    means = []
    stds = []
    for model_path in model_paths:
        mean, std = embedded_standardization(onnx.load(str(model_path)))
        means.append(mean)
        stds.append(std)
    training_mean = np.mean(np.stack(means), axis=0)
    training_std = np.mean(np.stack(stds), axis=0)

    central_dir = central_histogram_directory(histogram_base)
    eras = requested_eras or sorted(
        path.name
        for path in central_dir.glob("Run3_*")
        if path.is_dir() and path.name != "Run3_2022_23"
    )
    print()
    print("=" * 100)
    print("CENTRAL HISTOGRAM COMPARISON")
    print(f"Input:  {central_dir}")
    print(f"Region: {region}")
    print(
        "Moments use absolute bin contents and bin centers; they are an "
        "approximate shape diagnostic."
    )

    problems = []
    for era in eras:
        era_name = era if era.startswith("Run3_") else f"Run3_{era}"
        era_dir = central_dir / era_name
        files = sorted(
            path
            for path in era_dir.glob("*.root")
            if path.is_file() and path.stat().st_size > 0
        )
        if max_files:
            files = files[:max_files]
        print()
        print(f"--- {era_name}: {len(files)} final ROOT file(s) ---")
        print(
            f"{'#':>3}  {'feature':<34} {'train mean':>12} {'train std':>12} "
            f"{'hist mean':>12} {'hist std':>12}  status"
        )
        print("-" * 105)

        for index, feature in enumerate(features):
            train_mean = training_mean[index]
            train_std = training_std[index]
            if feature == "era_code":
                expected = ERA_CODES.get(era_name)
                status = "ERA_CONSTANT" if expected is not None else "UNKNOWN_ERA"
                print(
                    f"{index:3d}  {feature:<34} {train_mean:12.5g} "
                    f"{train_std:12.5g} {str(expected):>12} {0.0:12.5g}  {status}"
                )
                if expected is None:
                    problems.append(f"{era_name}: unknown era_code")
                continue

            moments = histogram_moments(files, f"{region}/{feature}")
            if moments is None:
                status = "MISSING"
                problems.append(
                    f"{era_name}: missing or empty {region}/{feature}"
                )
                print(
                    f"{index:3d}  {feature:<34} {train_mean:12.5g} "
                    f"{train_std:12.5g} {'-':>12} {'-':>12}  {status}"
                )
                continue

            observed_mean, observed_std, found = moments
            statuses = []
            if observed_std <= std_threshold:
                statuses.append("HIST_ZERO_VAR")
                problems.append(
                    f"{era_name}: {feature} has histogram std={observed_std:g}"
                )
            if train_std <= std_threshold:
                statuses.append("MODEL_ZERO_VAR")
                mean_difference = abs(observed_mean - train_mean)
                if observed_std > std_threshold or mean_difference > std_threshold:
                    statuses.append("MODEL/HIST_MISMATCH")
                    problems.append(
                        f"{era_name}: {feature} is constant in the model "
                        f"(mean={train_mean:g}, std={train_std:g}) but Central "
                        f"histograms have mean={observed_mean:g}, "
                        f"std={observed_std:g}"
                    )
            else:
                mean_shift = abs(observed_mean - train_mean) / train_std
                std_ratio = observed_std / train_std
                if mean_shift > mean_z_threshold:
                    statuses.append(f"MEAN_SHIFT_{mean_shift:.1f}SIGMA")
                    problems.append(
                        f"{era_name}: {feature} histogram mean differs from "
                        f"training by {mean_shift:.2f} sigma"
                    )
                if not min_std_ratio <= std_ratio <= max_std_ratio:
                    statuses.append(f"STD_RATIO_{std_ratio:.2g}")
                    problems.append(
                        f"{era_name}: {feature} histogram/training std ratio "
                        f"is {std_ratio:.4g}"
                    )
            status = ",".join(statuses) if statuses else f"OK({found})"
            print(
                f"{index:3d}  {feature:<34} {train_mean:12.5g} "
                f"{train_std:12.5g} {observed_mean:12.5g} "
                f"{observed_std:12.5g}  {status}"
            )

    print()
    if problems:
        print(f"[FAIL] Central histogram comparison found {len(problems)} problem(s).")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("[OK] Central histograms are compatible with the model inputs.")
    return 0


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description=(
            "Check configured DNN feature order and the mean/std preprocessing "
            "constants embedded in every ONNX fold."
        )
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=repo / "common" / "updated_DNN_configs",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=repo / "common" / "updated_DNN_models",
    )
    parser.add_argument(
        "--std-threshold",
        type=float,
        default=1.0e-10,
        help="absolute std at or below which a feature is considered constant",
    )
    parser.add_argument(
        "--histograms-base",
        type=Path,
        help=(
            "campaign directory containing Hists_Central, or the "
            "Hists_Central directory itself"
        ),
    )
    parser.add_argument(
        "--region",
        default="Signal_Fit_VBF/incl",
        help="nested ROOT directory used for the histogram comparison",
    )
    parser.add_argument(
        "--eras",
        default="",
        help="comma-separated eras; default: discover all individual eras",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        help="limit final ROOT files read per era for a faster check",
    )
    parser.add_argument("--mean-z-threshold", type=float, default=5.0)
    parser.add_argument("--min-std-ratio", type=float, default=0.1)
    parser.add_argument("--max-std-ratio", type=float, default=10.0)
    args = parser.parse_args()

    try:
        model_status = inspect_models(
            args.config_dir.resolve(),
            args.models_dir.resolve(),
            args.std_threshold,
        )
        histogram_status = 0
        if args.histograms_base:
            requested_eras = [
                era.strip()
                for era in args.eras.split(",")
                if era.strip()
            ]
            histogram_status = compare_central_histograms(
                args.config_dir.resolve(),
                args.models_dir.resolve(),
                args.histograms_base.resolve(),
                args.region,
                requested_eras,
                args.max_files,
                args.std_threshold,
                args.mean_z_threshold,
                args.min_std_ratio,
                args.max_std_ratio,
            )
        return 1 if model_status or histogram_status else 0
    except Exception as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
