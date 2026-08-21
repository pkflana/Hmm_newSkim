#!/usr/bin/env python3
"""Fit data-driven DY 0J/1J/2J normalizations from 2D jet templates."""

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
import mplhep as hep
import numpy as np
import ROOT

ROOT.gROOT.SetBatch(True)
plt.style.use(hep.style.CMS)

COMPONENTS = {
    "0J": ("2J_PU2", "DY 0J Hard"),
    "1J": ("2J_PU1", "DY 1J Hard"),
    "2J": ("2J_Hard", "DY 2J Hard"),
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
    if not hist or not hist.InheritsFrom("TH2"):
        root_file.Close()
        raise KeyError(f"Missing TH2 {root_path} in {path}")
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
    """Small bounded WLS solver; enumerate active sets for three parameters."""
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
                "The three DY templates are linearly dependent in the valid "
                "fit bins; the 0J/1J/2J normalizations cannot be identified."
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
    content = [float(theta[0]), float(theta[1]), float(theta[2])]
    return {
        "schema_version": 2,
        "description": f"Data-driven DY hard-jet component fit for {era}",
        "corrections": [{
            "name": "dy_012j_reweight",
            "description": "DY component normalization versus hard-jet multiplicity.",
            "version": 1,
            "inputs": [{
                "name": "n_hard_jets", "type": "real",
                "description": "Number of hard jets among the selected VBF pair.",
            }],
            "output": {"name": "weight", "type": "real"},
            "data": {
                "nodetype": "binning", "input": "n_hard_jets",
                "edges": [-0.5, 0.5, 1.5, 2.5], "content": content,
                "flow": "clamp",
            },
        }],
    }


def make_plots(output_dir, data, non_dy, component_hists, theta, era):
    output_dir.mkdir(parents=True, exist_ok=True)
    labels = list(COMPONENTS)
    colors = ["#6b3b00", "#0868df", "cornflowerblue"]
    data_v, _ = hist_arrays(data)
    non_v, _ = hist_arrays(non_dy)
    comp_v = [hist_arrays(hist)[0] for hist in component_hists]
    x = np.arange(len(data_v))
    for tag, scales in (("prefit", np.ones(3)), ("postfit", theta)):
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
        rax.set_xlabel("flattened $|\\eta(j_1)| \\times p_T(j_1)$ bin")
        ax.set_ylabel("Events")
        ax.set_yscale("log")
        ax.legend(ncol=3, fontsize=10)
        hep.cms.label(ax=ax, data=True, label="Preliminary", com=13.6)
        fig.savefig(output_dir / f"dy_012j_{tag}.png", bbox_inches="tight")
        fig.savefig(output_dir / f"dy_012j_{tag}.pdf", bbox_inches="tight")
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--era", required=True)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--region", default="Z_sideband_VBF")
    parser.add_argument("--variable", default="eta_vs_pt_leadingjet")
    parser.add_argument("--data-sample", default="Data_Muon")
    parser.add_argument("--dy-process", default="DY")
    parser.add_argument("--subtract-samples", nargs="+", default=list(DEFAULT_SUBTRACT))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()

    inclusive_root_path = f"{args.region}/{args.variable}"
    component_root_path = f"{args.region}/{args.variable}"
    data_path = args.input_dir / f"{args.data_sample}.root"
    data = open_hist(data_path, inclusive_root_path, "data")
    component_hists = []
    for component, (suffix, _) in COMPONENTS.items():
        path = args.input_dir / f"{args.dy_process}_{suffix}.root"
        component_hists.append(
            open_hist(path, component_root_path, f"dy_{component}")
        )

    subtract_paths = [
        args.input_dir / f"{sample}.root" for sample in args.subtract_samples
        if (args.input_dir / f"{sample}.root").is_file()
    ]
    non_dy, used = sum_hists(subtract_paths, inclusive_root_path, data)
    if not used:
        raise RuntimeError("No non-DY samples with the requested TH2 were found")

    data_v, data_var = hist_arrays(data)
    non_v, non_var = hist_arrays(non_dy)
    component_arrays = [hist_arrays(hist) for hist in component_hists]
    templates = np.column_stack([entry[0] for entry in component_arrays])
    template_var = np.column_stack([entry[1] for entry in component_arrays])
    theta, covariance, chi2, ndof, valid = solve_nonnegative_wls(
        data_v - non_v, templates, data_var + non_var, template_var
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_root.parent.mkdir(parents=True, exist_ok=True)
    payload = correction_payload(args.era, theta, covariance)
    fit_summary = {
        "era": args.era,
        "parameter_order": ["0J", "1J", "2J"],
        "values": theta.tolist(),
        "errors": np.sqrt(np.maximum(np.diag(covariance), 0.0)).tolist(),
        "covariance": covariance.tolist(),
        "region": args.region, "variable": args.variable,
        "subtracted_samples": used, "chi2": chi2, "ndof": ndof,
        "n_fit_bins": int(np.count_nonzero(valid)),
    }
    args.output_json.write_text(json.dumps(payload, indent=2) + "\n")
    fit_summary_path = args.output_json.with_name(
        f"{args.output_json.stem}_fit.json"
    )
    fit_summary_path.write_text(json.dumps(fit_summary, indent=2) + "\n")

    output = ROOT.TFile.Open(str(args.output_root), "RECREATE")
    data.Write("data")
    non_dy.Write("non_dy")
    for component, hist in zip(COMPONENTS, component_hists):
        hist.Write(f"dy_{component}")
    covariance_hist = ROOT.TH2D("covariance", "covariance", 3, 0, 3, 3, 0, 3)
    for ix in range(3):
        for iy in range(3):
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
