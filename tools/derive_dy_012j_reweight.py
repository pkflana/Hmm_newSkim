#!/usr/bin/env python3
"""Fit six data-driven DY reco/PU jet-component normalizations."""

from __future__ import annotations

import argparse
import itertools
import json
import math
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
}
DEFAULT_SUBTRACT = (
    # Canonical Run-3 process files for the Z sideband. Do not list aliases or
    # the MLL105-160 EWK alternative here, otherwise overlapping processes
    # could be subtracted twice when skim_cfg produced both files.
    "EWK", "SingleH", "ST", "TT", "TTX", "TW", "VV", "VVV", "W_NJets",
    "GluGluHto2Mu", "VBFHto2Mu_M125_powheg",
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


def solve_nonnegative_wls(target, templates, variance, template_variances):
    """Small bounded WLS solver; enumerate active component sets."""
    npar = templates.shape[1]
    theta = np.ones(npar)
    best = None
    for _ in range(8):
        effective_var = variance + np.sum(
            template_variances * theta[np.newaxis, :] ** 2, axis=1
        )
        valid = np.isfinite(target) & (effective_var > 0) & np.all(
            np.isfinite(templates), axis=1
        )
        y = target[valid]
        matrix = templates[valid]
        weight = 1.0 / effective_var[valid]
        if np.linalg.matrix_rank(matrix * np.sqrt(weight)[:, None]) < npar:
            raise RuntimeError(
                "The DY component templates are linearly dependent in the valid "
                "fit bins; six independent normalizations cannot be identified."
            )
        best = None
        for size in range(1, npar + 1):
            for active in itertools.combinations(range(npar), size):
                design = matrix[:, active]
                weighted = design * np.sqrt(weight)[:, None]
                solution, _, _, _ = np.linalg.lstsq(
                    weighted, y * np.sqrt(weight), rcond=None
                )
                if np.any(solution < 0):
                    continue
                candidate = np.zeros(npar)
                candidate[list(active)] = solution
                residual = y - matrix @ candidate
                chi2 = float(np.sum(weight * residual * residual))
                if best is None or chi2 < best[0]:
                    best = (chi2, candidate, active, valid, weight)
        if best is None:
            raise RuntimeError("No valid non-negative fit solution")
        new_theta = best[1]
        if np.allclose(new_theta, theta, rtol=1e-6, atol=1e-8):
            theta = new_theta
            break
        theta = new_theta

    chi2, theta, active, valid, weight = best
    covariance = np.zeros((npar, npar))
    design = templates[valid][:, active]
    normal = design.T @ (weight[:, None] * design)
    active_cov = np.linalg.pinv(normal)
    covariance[np.ix_(active, active)] = active_cov
    ndof = max(int(np.count_nonzero(valid) - len(active)), 0)
    return theta, covariance, chi2, ndof, valid


def correction_payload(era, theta, covariance):
    content = dict(zip(COMPONENTS, map(float, theta)))
    return {
        "schema_version": 2,
        "description": f"Data-driven DY hard-jet component fit for {era}",
        "corrections": [{
            "name": "dy_012j_reweight",
            "description": "DY normalization for six exclusive reco/PU jet components.",
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


def make_plots(output_dir, data, non_dy, component_hists, theta, era):
    output_dir.mkdir(parents=True, exist_ok=True)
    labels = list(COMPONENTS)
    colors = ["#6b3b00", "#0868df", "cornflowerblue", "#008060", "#bd3d3a", "#8957a1"]
    data_v, _ = hist_arrays(data)
    non_v, _ = hist_arrays(non_dy)
    comp_v = [hist_arrays(hist)[0] for hist in component_hists]
    x = np.arange(len(data_v))
    for tag, scales in (("prefit", np.ones(len(COMPONENTS))), ("postfit", theta)):
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
        fig.savefig(output_dir / f"dy_012j_{tag}.png", bbox_inches="tight")
        fig.savefig(output_dir / f"dy_012j_{tag}.pdf", bbox_inches="tight")
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--era", required=True)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--region", default="Z_sideband_ggF")
    parser.add_argument("--variables", nargs="+", default=["m_mumu", "eta_vs_pt_leadingjet", "eta_vs_pt_subleadingjet"])
    parser.add_argument("--data-sample", default="Data_Muon")
    parser.add_argument("--dy-process", default="DY")
    parser.add_argument("--subtract-samples", nargs="+", default=list(DEFAULT_SUBTRACT))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()

    data_path = args.input_dir / f"{args.data_sample}.root"
    subtract_paths = [
        args.input_dir / f"{sample}.root" for sample in args.subtract_samples
        if (args.input_dir / f"{sample}.root").is_file()
    ]
    data_parts, data_var_parts, non_parts, non_var_parts = [], [], [], []
    component_parts = [[] for _ in COMPONENTS]
    component_var_parts = [[] for _ in COMPONENTS]
    used, plot_inputs = set(), None
    for variable in args.variables:
        root_path = f"{args.region}/{variable}"
        data = open_hist(data_path, root_path, f"data_{variable}")
        non_dy, used_here = sum_hists(subtract_paths, root_path, data)
        used.update(used_here)
        data_values, data_variance = hist_arrays(data)
        non_values, non_variance = hist_arrays(non_dy)
        data_parts.append(data_values); data_var_parts.append(data_variance)
        non_parts.append(non_values); non_var_parts.append(non_variance)
        variable_components = []
        for index, (component, suffix) in enumerate(COMPONENTS.items()):
            hist = open_hist(args.input_dir / f"{args.dy_process}_{suffix}.root", root_path, f"dy_{component}_{variable}")
            values, variance = hist_arrays(hist)
            component_parts[index].append(values); component_var_parts[index].append(variance)
            variable_components.append(hist)
        if plot_inputs is None:
            plot_inputs = (data, non_dy, variable_components)
    if not used:
        raise RuntimeError("No non-DY samples with the requested histograms were found")
    data_v, data_var = np.concatenate(data_parts), np.concatenate(data_var_parts)
    non_v, non_var = np.concatenate(non_parts), np.concatenate(non_var_parts)
    templates = np.column_stack([np.concatenate(parts) for parts in component_parts])
    template_var = np.column_stack([np.concatenate(parts) for parts in component_var_parts])
    theta, covariance, chi2, ndof, valid = solve_nonnegative_wls(
        data_v - non_v, templates, data_var + non_var, template_var
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_root.parent.mkdir(parents=True, exist_ok=True)
    payload = correction_payload(args.era, theta, covariance)
    fit_summary = {
        "era": args.era,
        "parameter_order": list(COMPONENTS),
        "values": theta.tolist(),
        "errors": np.sqrt(np.maximum(np.diag(covariance), 0.0)).tolist(),
        "covariance": covariance.tolist(),
        "region": args.region, "variables": args.variables,
        "subtracted_samples": sorted(used), "chi2": chi2, "ndof": ndof,
        "n_fit_bins": int(np.count_nonzero(valid)),
    }
    args.output_json.write_text(json.dumps(payload, indent=2) + "\n")
    fit_summary_path = args.output_json.with_name(
        f"{args.output_json.stem}_fit.json"
    )
    fit_summary_path.write_text(json.dumps(fit_summary, indent=2) + "\n")

    output = ROOT.TFile.Open(str(args.output_root), "RECREATE")
    data, non_dy, component_hists = plot_inputs
    data.Write("data"); non_dy.Write("non_dy")
    for component, hist in zip(COMPONENTS, component_hists):
        hist.Write(f"dy_{component}")
    n_components = len(COMPONENTS)
    covariance_hist = ROOT.TH2D("covariance", "covariance", n_components, 0, n_components, n_components, 0, n_components)
    for ix in range(n_components):
        for iy in range(n_components):
            covariance_hist.SetBinContent(ix + 1, iy + 1, covariance[ix, iy])
    covariance_hist.Write()
    output.Close()
    make_plots(args.output_dir, data, non_dy, component_hists, theta, args.era)

    errors = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    for component, value, error in zip(COMPONENTS, theta, errors):
        print(f"[FIT] DY {component}: {value:.6g} +/- {error:.6g}")
    print(f"[FIT] chi2/ndof = {chi2:.3f}/{ndof}")
    print(f"[OUTPUT] {args.output_json}")
    print(f"[OUTPUT] {fit_summary_path}")
    print(f"[OUTPUT] {args.output_root}")


if __name__ == "__main__":
    main()
