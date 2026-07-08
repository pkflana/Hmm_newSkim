#!/usr/bin/env python3

import argparse
import json
import os

import ROOT


ROOT.gROOT.SetBatch(True)


DEFAULT_POINTS = [
    {"name": "muR0p5_muF0p5", "index": 0},
    {"name": "muR0p5_muF1", "index": 1},
    {"name": "muR1_muF0p5", "index": 3},
    {"name": "muR1_muF2", "index": 5},
    {"name": "muR2_muF1", "index": 7},
    {"name": "muR2_muF2", "index": 8},
]

QCD_SCALE_HELPER = r"""
#include <ROOT/RVec.hxx>

namespace qcd_scale_patch {
inline float weightAt(
    const ROOT::VecOps::RVec<float>& weights,
    const unsigned int index
) {
    return index < weights.size() ? static_cast<float>(weights[index]) : 1.f;
}
}  // namespace qcd_scale_patch
"""


def load_points(config_path):
    if not config_path:
        return DEFAULT_POINTS

    import common.utilities as utilities

    config = utilities.get_config(config_path)
    return config.get("qcd_scale", {}).get("points", DEFAULT_POINTS)


def report_key(point_name, legacy_names):
    if legacy_names:
        return f"gen_qcdScale_{point_name}"
    return f"qcd_scale__{point_name}"


def compute_qcd_scale_sums(root_file, tree_name, branch, points):
    if not ROOT.gInterpreter.Declare(QCD_SCALE_HELPER):
        raise RuntimeError("Failed to declare QCD scale helper")

    rdf = ROOT.RDataFrame(tree_name, root_file)
    available_columns = {str(column) for column in rdf.GetColumnNames()}
    for column in ("genWeight", branch):
        if column not in available_columns:
            raise RuntimeError(f"Column '{column}' is missing from {root_file}")

    gen_sum = rdf.Sum("genWeight").GetValue()
    sums = {}
    for point in points:
        name = point["name"]
        index = int(point["index"])
        column = f"patch_qcd_scale_sum__{name}"
        sums[name] = (
            rdf.Define(
                column,
                f"genWeight * qcd_scale_patch::weightAt({branch}, {index}u)",
            )
            .Sum(column)
            .GetValue()
        )

    return gen_sum, sums


def report_gen_total(report):
    try:
        return float(report["gen"]["total"]["value"])
    except (KeyError, TypeError, ValueError):
        return None


def update_report(
    report_path,
    root_gen_sum,
    sums,
    legacy_names=False,
    overwrite=False,
    allow_mismatched_gen_sum=False,
):
    with open(report_path) as handle:
        report = json.load(handle)

    json_gen_sum = report_gen_total(report)
    if (
        json_gen_sum is not None
        and json_gen_sum != 0.0
        and abs(root_gen_sum - json_gen_sum) / abs(json_gen_sum) > 1.0e-3
        and not allow_mismatched_gen_sum
    ):
        raise RuntimeError(
            "The ROOT file genWeight sum does not match the report gen total: "
            f"ROOT={root_gen_sum}, report={json_gen_sum}. "
            "This usually means the ROOT file is already skimmed and cannot be "
            "used to recover pre-skim QCD scale denominators. Rerun from the "
            "original NanoAOD/input file, or pass --allow-mismatched-gen-sum "
            "only if you intentionally want skim-level sums."
        )

    updated = []
    skipped = []
    for point_name, value in sums.items():
        key = report_key(point_name, legacy_names)
        if key in report and not overwrite:
            skipped.append(key)
            continue
        report[key] = {
            "total": {
                "selection": "return true;",
                "value": float(value),
            }
        }
        updated.append(key)

    with open(report_path, "w") as handle:
        json.dump(report, handle, indent=4, sort_keys=False)
        handle.write("\n")

    return updated, skipped


def main():
    parser = argparse.ArgumentParser(
        description="Patch skim report JSONs with QCD scale sum nodes."
    )
    parser.add_argument("--root-file", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--tree-name", default="Events")
    parser.add_argument("--branch", default="LHEScaleWeight")
    parser.add_argument("--config", help="systematics.yaml to read qcd_scale.points from")
    parser.add_argument(
        "--legacy-names",
        action="store_true",
        help="Write gen_qcdScale_POINT keys instead of qcd_scale__POINT.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--allow-mismatched-gen-sum",
        action="store_true",
        help=(
            "Allow patching when the ROOT genWeight sum does not match the "
            "report gen total. This is usually wrong for skimmed ROOT files."
        ),
    )
    args = parser.parse_args()

    if not os.path.exists(args.root_file):
        raise FileNotFoundError(args.root_file)
    if not os.path.exists(args.report_json):
        raise FileNotFoundError(args.report_json)

    points = load_points(args.config)
    root_gen_sum, sums = compute_qcd_scale_sums(
        args.root_file,
        args.tree_name,
        args.branch,
        points,
    )
    updated, skipped = update_report(
        args.report_json,
        root_gen_sum,
        sums,
        legacy_names=args.legacy_names,
        overwrite=args.overwrite,
        allow_mismatched_gen_sum=args.allow_mismatched_gen_sum,
    )

    print(f"[INFO] Report JSON: {args.report_json}")
    print(f"[INFO] Updated keys: {len(updated)}")
    for key in updated:
        print(f"  + {key}")
    if skipped:
        print(f"[INFO] Existing keys kept: {len(skipped)}")
        for key in skipped:
            print(f"  = {key}")


if __name__ == "__main__":
    main()
