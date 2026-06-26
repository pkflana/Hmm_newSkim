"""QCD renormalization/factorization scale variations from NanoAOD LHE weights."""

import ROOT


_QCD_SCALE_HELPER = r"""
#include <ROOT/RVec.hxx>

namespace qcd_scale {
inline float weightAt(
    const ROOT::VecOps::RVec<float>& weights,
    const unsigned int index
) {
    return index < weights.size() ? static_cast<float>(weights[index]) : 1.f;
}
}  // namespace qcd_scale
"""

if not ROOT.gInterpreter.Declare(_QCD_SCALE_HELPER):
    raise RuntimeError("Failed to declare the QCD scale weight helper")


def get_qcd_scale_points(config):
    """Return configured six-point scale variations."""
    return config.get(
        "points",
        [
            {"name": "muR0p5_muF0p5", "index": 0},
            {"name": "muR0p5_muF1", "index": 1},
            {"name": "muR1_muF0p5", "index": 3},
            {"name": "muR1_muF2", "index": 5},
            {"name": "muR2_muF1", "index": 7},
            {"name": "muR2_muF2", "index": 8},
        ],
    )


def define_qcd_scale_sum_columns(df, config, json_dict):
    """Book exact selected-event sums for every scale variation."""
    config = config or {}
    if not config.get("enabled", True):
        return df, json_dict

    branch = config.get("branch", "LHEScaleWeight")
    available_columns = {str(column) for column in df.GetColumnNames()}
    if branch not in available_columns:
        print(f"[WARNING] QCD scale branch '{branch}' is missing.")
        return df, json_dict

    for point in get_qcd_scale_points(config):
        name = point["name"]
        index = int(point["index"])
        column = f"weight_qcd_scale_sum__{name}"
        df = df.Define(
            column,
            f"genWeight * qcd_scale::weightAt({branch}, {index}u)",
        )
        json_dict[f"qcd_scale__{name}"] = {
            "total": {
                "selection": "return true;",
                "value": df.Sum(column),
            }
        }
    return df, json_dict


__all__ = ["define_qcd_scale_sum_columns", "get_qcd_scale_points"]
