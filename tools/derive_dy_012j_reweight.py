#!/usr/bin/env python3
"""Sequentially fit the six DY reco/PU components in the 2J, 1J and 0J regions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ.setdefault("MPLCONFIGDIR", "/tmp/vdamante/matplotlib")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import ROOT
from scipy.optimize import Bounds, LinearConstraint, minimize

try:
    import mplhep as hep
except ImportError:
    hep = None

ROOT.gROOT.SetBatch(True)
if hep:
    plt.style.use(hep.style.CMS)

COMPONENTS = {
    "0J": "0J", "1JHard": "1J_Hard", "1JPU": "1J_PU",
    "2JHard": "2J_Hard", "2JPU1": "2J_PU1", "2JPU2": "2J_PU2",
    "VBFHard": "2J_Hard", "VBFPU1": "2J_PU1", "VBFPU2": "2J_PU2",
}
GGF_COMPONENTS = tuple(name for name in COMPONENTS if not name.startswith("VBF"))
VBF_COMPONENTS = ("VBFHard", "VBFPU1", "VBFPU2")

# Fit high reco-jet multiplicity first.  Its post-fit prediction is subtracted
# in the following inclusive observables, which implicitly select >=1J (j1)
# and >=2J (j2).  The final m_mumu fit is inclusive in reco multiplicity.
FIT_STAGES = (
    ("2J", "eta_signed_vs_pt_subleadingjet", ("2JHard", "2JPU1", "2JPU2")),
    ("1J", "eta_signed_vs_pt_leadingjet", ("1JHard", "1JPU")),
    ("0J", "m_mumu", ("0J",)),
)
DEFAULT_SUBTRACT = (
    # Canonical Run-3 process files for the Z sideband. Do not list aliases or
    # the MLL105-160 EWK alternative here, otherwise overlapping processes
    # could be subtracted twice when skim_cfg produced both files.
    "EWK", "SingleH", "ST", "TT", "TTX", "TW", "VV", "VVV", "W_NJets",
    # "GluGluHto2Mu", "VBFHto2Mu_M125_powheg",
)


def open_hist(path: Path, root_path: str, clone_name: str):
    root_file = ROOT.TFile.Open(str(path), "READ")
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Cannot open {path}")
    hist = root_file.Get(root_path)
    if not hist or not hist.InheritsFrom("TH1"):
        root_file.Close()
        raise KeyError(f"Missing histogram {root_path} in {path}")
    clone = hist.Clone(clone_name)
    clone.SetDirectory(0)
    root_file.Close()
    return clone


def hist_arrays(hist):
    values, variances = [], []
    for ix in range(1, hist.GetNbinsX() + 1):
        for iy in range(1, hist.GetNbinsY() + 1):
            values.append(hist.GetBinContent(ix, iy))
            variances.append(hist.GetBinError(ix, iy) ** 2)
    return np.asarray(values, float), np.asarray(variances, float)


def sum_hists(paths, root_path, reference):
    total = reference.Clone("non_dy")
    total.Reset("ICES")
    total.SetDirectory(0)
    used = []
    for path in paths:
        try:
            hist = open_hist(path, root_path, f"non_dy_{path.stem}")
        except KeyError:
            continue
        total.Add(hist)
        used.append(path.stem)
    return total, used


def solve_nonnegative_poisson(data, background, templates):
    """Fit non-negative DY scales with a binned Poisson likelihood.

    The expectation in every retained bin is
        mu = fixed non-DY/fitted-DY background + templates @ theta.
    MC templates are treated as fixed predictions; the likelihood is Poisson
    in the observed data counts.
    """
    npar = templates.shape[1]
    valid = (
        np.isfinite(data)
        & (data >= 0)
        & np.isfinite(background)
        & np.all(np.isfinite(templates), axis=1)
        & ((background + np.sum(templates, axis=1)) > 0)
    )
    observed = data[valid]
    fixed = background[valid]
    matrix = templates[valid]
    if matrix.shape[0] <= npar or np.linalg.matrix_rank(matrix) < npar:
        raise RuntimeError(
            "The DY component templates are linearly dependent in the valid "
            f"fit bins; {npar} independent normalizations cannot be identified."
        )

    epsilon = 1.0e-12

    def expectation(theta):
        return fixed + matrix @ theta

    def nll(theta):
        mu = expectation(theta)
        if np.any(mu <= 0):
            return np.inf
        return float(np.sum(mu - observed * np.log(mu)))

    def gradient(theta):
        mu = expectation(theta)
        return matrix.T @ (1.0 - observed / mu)

    result = minimize(
        nll,
        np.ones(npar),
        jac=gradient,
        method="SLSQP",
        bounds=Bounds(np.zeros(npar), np.full(npar, np.inf)),
        constraints=LinearConstraint(matrix, epsilon - fixed, np.inf),
        options={"ftol": 1.0e-10, "maxiter": 2000},
    )
    if not result.success or not np.all(np.isfinite(result.x)):
        raise RuntimeError(f"Poisson likelihood fit failed: {result.message}")

    theta = np.maximum(result.x, 0.0)
    mu = expectation(theta)
    hessian = matrix.T @ ((observed / mu**2)[:, np.newaxis] * matrix)
    covariance = np.linalg.pinv(hessian)
    positive = observed > 0
    deviance_terms = np.array(mu, copy=True)
    deviance_terms[positive] = (
        mu[positive]
        - observed[positive]
        + observed[positive] * np.log(observed[positive] / mu[positive])
    )
    deviance = float(2.0 * np.sum(deviance_terms))
    ndof = max(int(np.count_nonzero(valid) - npar), 0)
    return theta, covariance, deviance, ndof, valid, float(result.fun)


def correction_payload(era, theta, covariance):
    content = dict(zip(COMPONENTS, map(float, theta)))
    return {
        "schema_version": 2,
        "description": f"Data-driven DY hard-jet component fit for {era}",
        "corrections": [{
            "name": "dy_012j_reweight",
            "description": (
                "Separate DY normalizations for six ggF reco/PU components "
                "and three VBF hard/PU components."
            ),
            "version": 1,
            "inputs": [{
                "name": "component", "type": "string",
                "description": "Exclusive reco/PU jet component.",
            }],
            "output": {"name": "weight", "type": "real"},
            "data": {
                "nodetype": "category", "input": "component",
                "content": [{"key": name, "value": value} for name, value in content.items()],
                "default": 1.0,
            },
        }],
    }


def make_plots(output_dir, data, non_dy, component_hists, theta, era, stage):
    output_dir.mkdir(parents=True, exist_ok=True)
    labels = list(component_hists)
    colors = ["#6b3b00", "#0868df", "cornflowerblue"]
    data_v, _ = hist_arrays(data)
    non_v, _ = hist_arrays(non_dy)
    comp_v = [hist_arrays(hist)[0] for hist in component_hists.values()]
    x = np.arange(len(data_v))
    for tag, scales in (("prefit", np.ones(len(labels))), ("postfit", theta)):
        fig, (ax, rax) = plt.subplots(
            2, 1, figsize=(11, 8), sharex=True,
            gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05},
        )
        stack = [non_v, *[v * s for v, s in zip(comp_v, scales)]]
        ax.stackplot(x, stack, labels=["non-DY", *[f"DY {x}" for x in labels]],
                     colors=["0.65", *colors], step="mid")
        ax.errorbar(x, data_v, np.sqrt(np.maximum(data_v, 0)), fmt=".", color="black", label="Data")
        total = np.sum(stack, axis=0)
        ratio = np.divide(data_v, total, out=np.full_like(data_v, np.nan), where=total > 0)
        rax.plot(x, ratio, ".", color="black")
        rax.axhline(1, color="black", linestyle="--")
        rax.set_ylim(0.5, 1.5)
        rax.set_ylabel("Data/MC")
        rax.set_xlabel("flattened fit bin")
        ax.set_ylabel("Events")
        ax.set_yscale("log")
        ax.legend(ncol=3, fontsize=10)
        if hep:
            hep.cms.label(ax=ax, data=True, label="Preliminary", com=13.6)
        fig.savefig(output_dir / f"dy_012j_{stage}_{tag}.png", bbox_inches="tight")
        fig.savefig(output_dir / f"dy_012j_{stage}_{tag}.pdf", bbox_inches="tight")
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--era", required=True)
    parser.add_argument(
        "--input-dir", required=True, type=Path, nargs="+",
        help="One or more era directories; multiple inputs are fitted jointly.",
    )
    parser.add_argument("--region", default="Z_sideband_ggF")
    parser.add_argument("--vbf-region", default="Z_sideband_VBF")
    parser.add_argument(
        "--variable",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--data-sample", default="Data_Muon")
    parser.add_argument("--dy-process", default="DY")
    parser.add_argument("--subtract-samples", nargs="+", default=list(DEFAULT_SUBTRACT))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()

    input_dirs = args.input_dir
    used = set()
    component_names = list(COMPONENTS)
    component_index = {name: index for index, name in enumerate(component_names)}
    theta = np.full(len(COMPONENTS), np.nan)
    covariance = np.zeros((len(COMPONENTS), len(COMPONENTS)))
    stage_summaries = []
    plot_inputs = []

    for stage, variable, active_components in FIT_STAGES:
        root_path = f"{args.region}/{variable}"
        fixed_components = [
            component for component in component_names
            if np.isfinite(theta[component_index[component]])
        ]
        data_parts, background_parts, template_parts = [], [], []
        merged_data = merged_background = None
        merged_components = {}
        for period_index, input_dir in enumerate(input_dirs):
            data = open_hist(
                input_dir / f"{args.data_sample}.root", root_path,
                f"data_{stage}_{period_index}",
            )
            subtract_paths = [
                input_dir / f"{sample}.root" for sample in args.subtract_samples
                if (input_dir / f"{sample}.root").is_file()
            ]
            non_dy, used_here = sum_hists(subtract_paths, root_path, data)
            used.update(f"{input_dir.name}:{name}" for name in used_here)
            data_v, _ = hist_arrays(data)
            non_v, _ = hist_arrays(non_dy)
            component_hists = {}
            component_values = {}
            for component, suffix in COMPONENTS.items():
                hist = open_hist(
                    input_dir / f"{args.dy_process}_{suffix}.root", root_path,
                    f"dy_{stage}_{component}_{period_index}",
                )
                component_hists[component] = hist
                component_values[component], _ = hist_arrays(hist)

            fixed_v = np.zeros_like(data_v)
            effective_background = non_dy.Clone(f"background_{stage}_{period_index}")
            effective_background.SetDirectory(0)
            for component in fixed_components:
                index = component_index[component]
                fixed_v += theta[index] * component_values[component]
                effective_background.Add(component_hists[component], theta[index])
            data_parts.append(data_v)
            background_parts.append(non_v + fixed_v)
            template_parts.append(np.column_stack([
                component_values[name] for name in active_components
            ]))

            if merged_data is None:
                merged_data = data.Clone(f"data_{stage}"); merged_data.SetDirectory(0)
                merged_background = effective_background.Clone(f"background_{stage}"); merged_background.SetDirectory(0)
                merged_components = {
                    name: component_hists[name].Clone(f"dy_{stage}_{name}")
                    for name in active_components
                }
                for hist in merged_components.values(): hist.SetDirectory(0)
            else:
                merged_data.Add(data); merged_background.Add(effective_background)
                for name in active_components:
                    merged_components[name].Add(component_hists[name])

        templates = np.concatenate(template_parts, axis=0)
        stage_theta, stage_covariance, deviance, ndof, valid, poisson_nll = (
            solve_nonnegative_poisson(
                np.concatenate(data_parts), np.concatenate(background_parts),
                templates,
            )
        )
        active_indices = [component_index[name] for name in active_components]
        theta[active_indices] = stage_theta
        covariance[np.ix_(active_indices, active_indices)] = stage_covariance
        stage_summaries.append({
            "stage": stage,
            "variable": variable,
            "parameters": list(active_components),
            "fixed_components": fixed_components,
            "poisson_nll": poisson_nll,
            "poisson_deviance": deviance,
            "chi2": deviance,
            "ndof": ndof,
            "n_fit_bins": int(np.count_nonzero(valid)),
        })
        plot_inputs.append((
            stage, merged_data, merged_background, merged_components, stage_theta,
        ))

    # VBF is an independent three-parameter fit.  The selected VBF pair always
    # has two reconstructed jets; its 0/1/2J hard content is distinguished by
    # whether two/one/zero of those jets are classified as PU.
    stage = "VBF"
    variable = "eta_signed_vs_pt_vbfjet1"
    root_path = f"{args.vbf_region}/{variable}"
    data_parts, background_parts, template_parts = [], [], []
    merged_data = merged_non_dy = None
    merged_components = {}
    for period_index, input_dir in enumerate(input_dirs):
        data = open_hist(
            input_dir / f"{args.data_sample}.root", root_path,
            f"data_{stage}_{period_index}",
        )
        subtract_paths = [
            input_dir / f"{sample}.root" for sample in args.subtract_samples
            if (input_dir / f"{sample}.root").is_file()
        ]
        non_dy, used_here = sum_hists(subtract_paths, root_path, data)
        used.update(f"{input_dir.name}:{name}" for name in used_here)
        data_v, _ = hist_arrays(data)
        non_v, _ = hist_arrays(non_dy)
        component_hists = {}
        values = {}
        for component in VBF_COMPONENTS:
            suffix = COMPONENTS[component]
            hist = open_hist(
                input_dir / f"{args.dy_process}_{suffix}.root", root_path,
                f"dy_{stage}_{component}_{period_index}",
            )
            component_hists[component] = hist
            values[component], _ = hist_arrays(hist)
        data_parts.append(data_v)
        background_parts.append(non_v)
        template_parts.append(np.column_stack([values[name] for name in VBF_COMPONENTS]))
        if merged_data is None:
            merged_data = data.Clone("data_VBF"); merged_data.SetDirectory(0)
            merged_non_dy = non_dy.Clone("background_VBF"); merged_non_dy.SetDirectory(0)
            merged_components = {
                name: component_hists[name].Clone(f"dy_VBF_{name}")
                for name in VBF_COMPONENTS
            }
            for hist in merged_components.values(): hist.SetDirectory(0)
        else:
            merged_data.Add(data); merged_non_dy.Add(non_dy)
            for name in VBF_COMPONENTS: merged_components[name].Add(component_hists[name])
    templates = np.concatenate(template_parts, axis=0)
    stage_theta, stage_covariance, deviance, ndof, valid, poisson_nll = (
        solve_nonnegative_poisson(
            np.concatenate(data_parts), np.concatenate(background_parts), templates,
        )
    )
    active_indices = [component_index[name] for name in VBF_COMPONENTS]
    theta[active_indices] = stage_theta
    covariance[np.ix_(active_indices, active_indices)] = stage_covariance
    stage_summaries.append({
        "stage": stage,
        "region": args.vbf_region,
        "variable": variable,
        "parameters": list(VBF_COMPONENTS),
        "fixed_components": [],
        "poisson_nll": poisson_nll,
        "poisson_deviance": deviance,
        "chi2": deviance,
        "ndof": ndof,
        "n_fit_bins": int(np.count_nonzero(valid)),
    })
    plot_inputs.append((stage, merged_data, merged_non_dy, merged_components, stage_theta))

    if not used:
        raise RuntimeError("No non-DY samples with the requested histograms were found")

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_root.parent.mkdir(parents=True, exist_ok=True)
    payload = correction_payload(args.era, theta, covariance)
    fit_summary = {
        "era": args.era,
        "parameter_order": component_names,
        "values": theta.tolist(),
        "errors": np.sqrt(np.maximum(np.diag(covariance), 0.0)).tolist(),
        "covariance": covariance.tolist(),
        "region": args.region,
        "vbf_region": args.vbf_region,
        "input_dirs": [str(path) for path in input_dirs],
        "fit_order": [stage for stage, _, _ in FIT_STAGES] + ["VBF"],
        "stages": stage_summaries,
        "subtracted_samples": sorted(used),
    }
    args.output_json.write_text(json.dumps(payload, indent=2) + "\n")
    fit_summary_path = args.output_json.with_name(
        f"{args.output_json.stem}_fit.json"
    )
    fit_summary_path.write_text(json.dumps(fit_summary, indent=2) + "\n")

    output = ROOT.TFile.Open(str(args.output_root), "RECREATE")
    for stage, data, background, component_hists, stage_theta in plot_inputs:
        data.Write(f"data_{stage}")
        background.Write(f"background_{stage}")
        for component, hist in component_hists.items():
            hist.Write(f"dy_{stage}_{component}")
    n_components = len(COMPONENTS)
    covariance_hist = ROOT.TH2D("covariance", "covariance", n_components, 0, n_components, n_components, 0, n_components)
    for ix in range(n_components):
        for iy in range(n_components):
            covariance_hist.SetBinContent(ix + 1, iy + 1, covariance[ix, iy])
    covariance_hist.Write()
    output.Close()
    for stage, data, background, component_hists, stage_theta in plot_inputs:
        make_plots(
            args.output_dir, data, background, component_hists,
            stage_theta, args.era, stage,
        )

    errors = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    for component, value, error in zip(COMPONENTS, theta, errors):
        print(f"[FIT] DY {component}: {value:.6g} +/- {error:.6g}")
    for summary in stage_summaries:
        print(
            f"[FIT] {summary['stage']} Poisson deviance/ndof = "
            f"{summary['poisson_deviance']:.3f}/{summary['ndof']}"
        )
    print(f"[OUTPUT] {args.output_json}")
    print(f"[OUTPUT] {fit_summary_path}")
    print(f"[OUTPUT] {args.output_root}")


if __name__ == "__main__":
    main()
