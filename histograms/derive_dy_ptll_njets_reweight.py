#!/usr/bin/env python3

import argparse
import array
import json
import math
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/vdamante/matplotlib")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplhep as hep
import numpy as np
import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.gStyle.SetOptStat(0)
plt.style.use(hep.style.CMS)

import common.utilities as utilities
from common.dy_ptll_reweight import DY_AMCATNLO_NORMALIZATION
from common.helpers import RebinHisto, findBinEntry, findNewBins, getNewBins


DEFAULT_CATEGORIES = ["ggF_0J", "ggF_1J", "ggF_ge2J", "VBF_ge2J"]
NON_DY_SUBTRACT_SAMPLES = [
    "EWK",
    "H_mainBckg",
    "ST",
    "TT",
    "TTX",
    "TW",
    "VV",
    "VVV",
    "W_NJets",
    "W",
]
FIT_FORMULA = (
    "[0]"
    " + [1]*TMath::Gaus(x,[2],[3],false)"
    " + [4]*TMath::Gaus(x,[5],[6],false)"
    " + [7]*TMath::Power(TMath::Max(x,[8])/[8],-[9])"
)
PARAMETER_NAMES = [
    "constant",
    "gaus1_norm",
    "gaus1_mean",
    "gaus1_sigma",
    "gaus2_norm",
    "gaus2_mean",
    "gaus2_sigma",
    "power_norm",
    "power_x0",
    "power_exponent",
]

CORRECTIONLIB_PTLL_FORMULA = (
    "[0]"
    " + [1]*exp(-0.5*((x-[2])/[3])^2)"
    " + [4]*exp(-0.5*((x-[5])/[6])^2)"
    " + [7]*pow(max(x,[8])/[8],-[9])"
)


def set_cms_style():
    ROOT.gStyle.SetOptStat(0)
    ROOT.gStyle.SetPadTickX(1)
    ROOT.gStyle.SetPadTickY(1)
    ROOT.gStyle.SetTitleBorderSize(0)
    ROOT.gStyle.SetTitleFillColor(0)
    ROOT.gStyle.SetLegendBorderSize(0)


def format_lumi_label(luminosity_pb):
    if luminosity_pb is None:
        return ""
    return f"{luminosity_pb / 1000.0:.1f} fb^{{-1}} (13.6 TeV)"


def format_lumi_fb(luminosity_pb):
    if luminosity_pb is None:
        return None
    return float(luminosity_pb) / 1000.0


def get_luminosity_fb(era):
    analysis_path = os.environ.get("ANALYSIS_PATH", os.getcwd())
    cfg_path = os.path.join(analysis_path, "config", era, "maincfg.yaml")
    if not os.path.exists(cfg_path):
        return None
    cfg = utilities.get_config(cfg_path)
    return format_lumi_fb(cfg.get("luminosity"))


def get_luminosity_label(era):
    analysis_path = os.environ.get("ANALYSIS_PATH", os.getcwd())
    cfg_path = os.path.join(analysis_path, "config", era, "maincfg.yaml")
    if not os.path.exists(cfg_path):
        return ""
    cfg = utilities.get_config(cfg_path)
    return format_lumi_label(cfg.get("luminosity"))


def draw_cms_label(lumi_label="", extra_label=""):
    latex = ROOT.TLatex()
    latex.SetNDC()
    latex.SetTextFont(42)
    latex.SetTextAlign(11)
    latex.SetTextSize(0.052)
    latex.DrawLatex(0.12, 0.94, "#bf{CMS}")
    latex.SetTextSize(0.043)
    latex.DrawLatex(0.235, 0.94, "#it{Preliminary}")
    if extra_label:
        latex.SetTextSize(0.037)
        latex.DrawLatex(0.405, 0.94, extra_label)
    if lumi_label:
        latex.SetTextSize(0.044)
        latex.SetTextAlign(31)
        latex.DrawLatex(0.94, 0.94, lumi_label)
    return latex


def hist_to_arrays(hist, x_min=None, x_max=None):
    centers = []
    xerr_low = []
    xerr_high = []
    values = []
    errors = []

    for bin_idx in range(1, hist.GetNbinsX() + 1):
        low = hist.GetXaxis().GetBinLowEdge(bin_idx)
        high = hist.GetXaxis().GetBinUpEdge(bin_idx)
        center = hist.GetBinCenter(bin_idx)
        if x_min is not None and high <= x_min:
            continue
        if x_max is not None and low >= x_max:
            continue
        value = hist.GetBinContent(bin_idx)
        error = hist.GetBinError(bin_idx)
        if not (math.isfinite(value) and math.isfinite(error)):
            continue
        centers.append(center)
        xerr_low.append(center - low)
        xerr_high.append(high - center)
        values.append(value)
        errors.append(error)

    return (
        np.asarray(centers),
        np.asarray([xerr_low, xerr_high]),
        np.asarray(values),
        np.asarray(errors),
    )


def draw_mplhep_cms_label(ax, lumi_fb, region, category):
    label = f"Preliminary"
    kwargs = {"ax": ax, "data": True, "label": label, "com": 13.6, 'fontsize':20}
    if lumi_fb is not None:
        kwargs["lumi"] = round(lumi_fb, 2)
    try:
        hep.cms.label(**kwargs)
        ax.text(0.04, 0.95, category,
        transform=ax.transAxes,
        verticalalignment='top',
        horizontalalignment='left',
        fontsize=14)

    except TypeError:
        kwargs.pop("label", None)
        hep.cms.label(label, **kwargs)


def correctionlib_variable(name, var_type, description):
    return {
        "name": name,
        "type": var_type,
        "description": description,
    }


def constant_node(value):
    return float(value)


def formula_node(category_payload):
    return {
        "nodetype": "formula",
        "expression": CORRECTIONLIB_PTLL_FORMULA,
        "parser": "TFormula",
        "variables": ["ptll"],
        "parameters": [
            float(value)
            for value in category_payload["fit"]["parameters"]
        ],
    }


def ptll_category_node(categories, category_name):
    category_payload = categories.get(category_name)
    if category_payload is None:
        return constant_node(1.0)
    return formula_node(category_payload)


def make_ptll_correctionlib_payload(legacy_payload):
    categories = legacy_payload["categories"]
    ggF_node = {
        "nodetype": "binning",
        "input": "N_selectedJets",
        "edges": [-0.5, 0.5, 1.5, 999.5],
        "content": [
            ptll_category_node(categories, "ggF_0J"),
            ptll_category_node(categories, "ggF_1J"),
            ptll_category_node(categories, "ggF_ge2J"),
        ],
        "flow": "clamp",
    }
    vbf_node = {
        "nodetype": "binning",
        "input": "N_selectedJets",
        "edges": [-0.5, 0.5, 1.5, 999.5],
        "content": [
            constant_node(1.0),
            constant_node(1.0),
            ptll_category_node(categories, "VBF_ge2J"),
        ],
        "flow": "clamp",
    }

    return {
        "schema_version": 2,
        "corrections": [
            {
                "name": "dy_ptll_reweight",
                "description": "DY pt(ll) reweighting from (Data - nonDY) / DY.",
                "version": 1,
                "inputs": [
                    correctionlib_variable(
                        "isVBF",
                        "int",
                        "VBF category flag: 1 for VBF, 0 for ggF.",
                    ),
                    correctionlib_variable(
                        "N_selectedJets",
                        "real",
                        "Number of selected jets.",
                    ),
                    correctionlib_variable(
                        "ptll",
                        "real",
                        "Dilepton transverse momentum.",
                    ),
                ],
                "output": {
                    "name": "weight",
                    "type": "real",
                    "description": "DY pt(ll) event weight.",
                },
                "data": {
                    "nodetype": "category",
                    "input": "isVBF",
                    "content": [
                        {"key": 0, "value": ggF_node},
                        {"key": 1, "value": vbf_node},
                    ],
                    "default": 1.0,
                },
            }
        ],
    }


def root_path(input_dir, sample):
    return os.path.join(input_dir, f"{sample}.root")


def get_sample_names(input_dir):
    return sorted(
        path.stem
        for path in Path(input_dir).glob("*.root")
        if path.is_file()
    )


def get_non_dy_subtract_samples(samples, input_dir):
    missing_samples = [
        sample for sample in NON_DY_SUBTRACT_SAMPLES
        if sample not in samples
    ]
    # if missing_samples:
    #     raise RuntimeError(
    #         f"Samples listed in NON_DY_SUBTRACT_SAMPLES not found in {input_dir}: "
    #         f"{missing_samples}"
    #     )
    return [x for x in list(NON_DY_SUBTRACT_SAMPLES) if x not in missing_samples]


def open_sample(input_dir, sample):
    path = root_path(input_dir, sample)
    root_file = ROOT.TFile.Open(path, "READ")
    if not root_file or root_file.IsZombie():
        raise RuntimeError(f"Cannot open ROOT file for sample {sample}: {path}")
    return root_file


def find_hist_in_directory(directory, variable):
    direct = directory.Get(variable)
    if direct and direct.InheritsFrom("TH1"):
        return direct

    for key in directory.GetListOfKeys():
        obj = key.ReadObj()
        if obj.InheritsFrom("TDirectory"):
            found = find_hist_in_directory(obj, variable)
            if found:
                return found
    return None


def clone_hist(root_file, directory_path, variable, name):
    hist = root_file.Get(f"{directory_path}/{variable}")
    if not hist:
        directory = root_file.Get(directory_path)
        if directory and directory.InheritsFrom("TDirectory"):
            hist = find_hist_in_directory(directory, variable)

    if not hist or not hist.InheritsFrom("TH1"):
        return None

    out = hist.Clone(name)
    out.SetDirectory(0)
    return out


def parse_rebin_edges(edges):
    if not edges:
        return None
    values = [float(item) for item in edges.split(",") if item.strip()]
    if len(values) < 2:
        raise ValueError("--rebin-edges needs at least two comma-separated edges")
    if any(high <= low for low, high in zip(values, values[1:])):
        raise ValueError("--rebin-edges must be strictly increasing")
    return values


def get_config_rebin_edges(hist_cfg, variable, directory_path):
    if not hist_cfg:
        return None

    var_entry = findBinEntry(hist_cfg, variable)
    bins_to_compute = findNewBins(
        hist_cfg,
        var_entry,
        dir_name=directory_path,
    )
    return getNewBins(bins_to_compute)


def rebin_hist(hist, name, rebin_factor=1, rebin_edges=None):
    if rebin_edges:
        bins = array.array("d", rebin_edges)
        rebinned = hist.Rebin(len(rebin_edges) - 1, name, bins)
    elif rebin_factor and rebin_factor > 1:
        rebinned = hist.Rebin(int(rebin_factor), name)
    else:
        rebinned = hist.Clone(name)

    rebinned.SetDirectory(0)
    return rebinned


def apply_rebin(hist, name, rebin_factor=1, rebin_edges=None):
    if rebin_edges:
        rebinned = RebinHisto(
            hist,
            rebin_edges,
            name,
            wantOverflow=False,
        )
        rebinned.SetDirectory(0)
        return rebinned

    return rebin_hist(
        hist,
        name,
        rebin_factor=rebin_factor,
        rebin_edges=None,
    )


def bin_edges(hist):
    axis = hist.GetXaxis()
    return [axis.GetBinLowEdge(idx) for idx in range(1, axis.GetNbins() + 2)]


def extend_rebin_edges_to_xmax(edges, hist, x_max):
    if not edges:
        return edges

    last_edge = float(edges[-1])
    target_edge = min(float(x_max), float(hist.GetXaxis().GetXmax()))
    if target_edge <= last_edge:
        return edges

    extended_edges = list(edges)
    extended_edges.append(target_edge)
    return extended_edges


def ratio_bin_quality(data, dy, other, data_err2, dy_err2, other_err2, min_dy):
    if dy <= min_dy:
        return None, None

    target = data - other
    target_err = math.sqrt(max(data_err2 + other_err2, 0.0))
    dy_err = math.sqrt(max(dy_err2, 0.0))

    value = target / dy
    if target != 0.0:
        error = abs(value) * math.sqrt(
            (target_err / target) ** 2 + (dy_err / dy) ** 2
        )
    else:
        error = target_err / dy

    rel_unc = abs(error / value) if value != 0.0 else float("inf")
    return value, rel_unc


def make_smart_rebin_edges(
    data_hist,
    dy_hist,
    other_hist,
    min_dy,
    min_target,
    max_rel_unc,
):
    edges = bin_edges(data_hist)
    smart_edges = [edges[0]]

    data = dy = other = 0.0
    data_err2 = dy_err2 = other_err2 = 0.0

    for bin_idx in range(1, data_hist.GetNbinsX() + 1):
        data += data_hist.GetBinContent(bin_idx)
        dy += dy_hist.GetBinContent(bin_idx)
        other += other_hist.GetBinContent(bin_idx)
        data_err2 += data_hist.GetBinError(bin_idx) ** 2
        dy_err2 += dy_hist.GetBinError(bin_idx) ** 2
        other_err2 += other_hist.GetBinError(bin_idx) ** 2

        target = data - other
        _, rel_unc = ratio_bin_quality(
            data,
            dy,
            other,
            data_err2,
            dy_err2,
            other_err2,
            min_dy,
        )
        high_edge = edges[bin_idx]
        is_last_bin = bin_idx == data_hist.GetNbinsX()
        passes = (
            dy >= min_dy
            and abs(target) >= min_target
            and rel_unc is not None
            and rel_unc <= max_rel_unc
        )

        if passes:
            smart_edges.append(high_edge)
            data = dy = other = 0.0
            data_err2 = dy_err2 = other_err2 = 0.0
        elif is_last_bin:
            if len(smart_edges) > 1:
                smart_edges[-1] = high_edge
            else:
                smart_edges.append(high_edge)

    return smart_edges


def empty_like(reference, name):
    hist = reference.Clone(name)
    hist.Reset("ICES")
    hist.SetDirectory(0)
    return hist


def sum_samples(input_dir, samples, directory_path, variable, reference, name, rebin_factor, rebin_edges):
    total = empty_like(reference, name)
    used = []

    for sample in samples:
        root_file = ROOT.TFile.Open(root_path(input_dir, sample), "READ")
        if not root_file or root_file.IsZombie():
            continue

        hist = clone_hist(root_file, directory_path, variable, f"{name}_{sample}")
        if hist:
            hist = apply_rebin(
                hist,
                f"{name}_{sample}_rebinned",
                rebin_factor=rebin_factor,
                rebin_edges=rebin_edges,
            )
            total.Add(hist)
            used.append(sample)

        root_file.Close()

    return total, used


def build_ratio_hist(data_hist, dy_hist, other_hist, name, min_dy):
    target = data_hist.Clone(f"{name}_target")
    target.SetDirectory(0)
    target.Add(other_hist, -1.0)

    ratio = data_hist.Clone(name)
    ratio.Reset("ICES")
    ratio.SetDirectory(0)
    ratio.GetYaxis().SetTitle("(Data - non-DY MC) / DY")

    for bin_idx in range(1, data_hist.GetNbinsX() + 1):
        dy = dy_hist.GetBinContent(bin_idx)
        if dy <= min_dy:
            continue

        data = data_hist.GetBinContent(bin_idx)
        other = other_hist.GetBinContent(bin_idx)
        target_content = data - other

        data_err = data_hist.GetBinError(bin_idx)
        other_err = other_hist.GetBinError(bin_idx)
        dy_err = dy_hist.GetBinError(bin_idx)
        target_err = math.sqrt(data_err * data_err + other_err * other_err)

        value = target_content / dy
        if target_content != 0.0:
            error = abs(value) * math.sqrt(
                (target_err / target_content) ** 2 + (dy_err / dy) ** 2
            )
        else:
            error = target_err / dy

        ratio.SetBinContent(bin_idx, value)
        ratio.SetBinError(bin_idx, error)

    return target, ratio


def make_fit_function(name, x_min, x_max):
    func = ROOT.TF1(name, FIT_FORMULA, x_min, x_max)
    initial = [1.0, 0.2, 20.0, 20.0, 0.1, 80.0, 60.0, 0.1, 20.0, 2.0]

    for idx, value in enumerate(initial):
        func.SetParameter(idx, value)
        func.SetParName(idx, PARAMETER_NAMES[idx])

    func.SetParLimits(3, 1.0, 200.0)
    func.SetParLimits(6, 1.0, 300.0)
    func.SetParLimits(8, 1.0, 100.0)
    func.SetParLimits(9, 0.0, 10.0)

    return func


def fit_ratio(ratio_hist, category, x_min, x_max):
    fit_func = make_fit_function(f"fit_{category}", x_min, x_max)
    status = ratio_hist.Fit(fit_func, "QRS0")

    params = [float(fit_func.GetParameter(i)) for i in range(fit_func.GetNpar())]
    errors = [float(fit_func.GetParError(i)) for i in range(fit_func.GetNpar())]

    return fit_func, {
        "formula": "constant + gaus1 + gaus2 + power_fall",
        "root_formula": FIT_FORMULA,
        "parameter_names": PARAMETER_NAMES,
        "parameters": params,
        "errors": errors,
        "status": int(status),
        "x_min": float(x_min),
        "x_max": float(x_max),
    }


def clipped_weight(value, min_weight, max_weight):
    if not math.isfinite(value):
        return 1.0
    return min(max(value, min_weight), max_weight)


def solve_shape_only_scale(category_entries, min_weight, max_weight):
    target = sum(
        entry["normalization_hist"].Integral(0, entry["normalization_hist"].GetNbinsX() + 1)
        for entry in category_entries
    )
    if target <= 0.0:
        return 1.0, target, target

    def weighted_yield(scale):
        total = 0.0
        for entry in category_entries:
            hist = entry["normalization_hist"]
            fit_func = entry["fit_func"]
            for bin_idx in range(0, hist.GetNbinsX() + 2):
                total += hist.GetBinContent(bin_idx) * clipped_weight(
                    scale * fit_func.Eval(hist.GetBinCenter(bin_idx)),
                    min_weight,
                    max_weight,
                )
        return total

    low = 0.0
    high = 1.0
    while weighted_yield(high) < target and high < 1.0e6:
        high *= 2.0

    for _ in range(100):
        middle = 0.5 * (low + high)
        if weighted_yield(middle) < target:
            low = middle
        else:
            high = middle

    scale = 0.5 * (low + high)
    return scale, target, weighted_yield(scale)


def scale_fit_payload(entry, scale):
    # The fit is linear in the constant and three component normalizations.
    for parameter_index in (0, 1, 4, 7):
        entry["fit_func"].SetParameter(
            parameter_index,
            scale * entry["fit_func"].GetParameter(parameter_index),
        )
        entry["fit_payload"]["parameters"][parameter_index] *= scale
        entry["fit_payload"]["errors"][parameter_index] *= abs(scale)
    entry["fit_payload"]["shape_only_scale"] = float(scale)


def make_after_reweight_ratio(ratio_hist, fit_func, name):
    after = ratio_hist.Clone(name)
    after.Reset("ICES")
    after.SetDirectory(0)

    for bin_idx in range(1, ratio_hist.GetNbinsX() + 1):
        x = ratio_hist.GetBinCenter(bin_idx)
        ratio = ratio_hist.GetBinContent(bin_idx)
        ratio_err = ratio_hist.GetBinError(bin_idx)
        weight = fit_func.Eval(x)
        if weight <= 0.0 or not math.isfinite(weight):
            continue

        after.SetBinContent(bin_idx, ratio / weight)
        after.SetBinError(bin_idx, ratio_err / weight)

    return after


def plot_fit_ratio(
    output_dir,
    era,
    region,
    category,
    ratio_hist,
    fit_func,
    lumi_label="",
    lumi_fb=None,
    x_min=0.0,
    x_max=200.0,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    x, xerr, y, yerr = hist_to_arrays(ratio_hist, x_min=x_min, x_max=x_max)
    x_fit = np.linspace(x_min, x_max, 600)
    y_fit = np.asarray([fit_func.Eval(float(value)) for value in x_fit])

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.errorbar(
        x,
        y,
        xerr=xerr,
        yerr=yerr,
        fmt="o",
        color="black",
        markersize=4,
        linewidth=1,
        label="(Data - non-DY) / DY",
    )
    ax.plot(x_fit, y_fit, color="blue", linewidth=2, label="Fit")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(0.5, max(1.5, 1.2 * float(np.nanmax(y)) if y.size else 1.5))
    ax.set_xlabel(r"$p_{T}(\ell\ell)$ [GeV]", fontsize=15)
    ax.set_ylabel("(Data - non-DY) / DY", fontsize=15)
    ax.legend(loc="upper right",fontsize='xx-small')
    draw_mplhep_cms_label(ax, lumi_fb, region, category)
    # fig.tight_layout()
    fig.savefig(output_dir / f"{category}_ptll_ratio_fit.png")
    fig.savefig(output_dir / f"{category}_ptll_ratio_fit.pdf")
    plt.close(fig)


def plot_reweighting_factor(
    output_dir,
    era,
    region,
    category,
    ratio_hist,
    fit_func,
    lumi_label="",
    lumi_fb=None,
    x_min=0.0,
    x_max=200.0,
):
    before = ratio_hist.Clone(f"before_reweight_{category}")
    before.SetDirectory(0)
    after = make_after_reweight_ratio(
        ratio_hist,
        fit_func,
        f"after_reweight_{category}",
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    x, xerr, y, yerr = hist_to_arrays(ratio_hist, x_min=x_min, x_max=x_max)
    x_fit = np.linspace(x_min, x_max, 600)
    y_fit = np.asarray([fit_func.Eval(float(value)) for value in x_fit])
    xb, xerrb, yb, yerrb = hist_to_arrays(before, x_min=x_min, x_max=x_max)
    xa, xerra, ya, yerra = hist_to_arrays(after, x_min=x_min, x_max=x_max)

    fig, (ax_top, ax_bottom) = plt.subplots(
        2,
        1,
        figsize=(9, 9),
        sharex=True,
        gridspec_kw={"height_ratios": [1.05, 1.0], "hspace": 0.08},
    )
    ax_top.errorbar(
        x,
        y,
        xerr=xerr,
        yerr=yerr,
        fmt="o",
        color="black",
        markersize=4,
        linewidth=1,
        label="(Data - non-DY) / DY",
    )
    ax_top.plot(x_fit, y_fit, color="blue", linewidth=2, label="Fit")
    ax_top.set_xlim(x_min, x_max)
    ax_top.set_ylim(0.5, max(1.5, 1.2 * float(np.nanmax(y)) if y.size else 1.5))
    ax_top.set_ylabel("(Data - non-DY) / DY", fontsize=15)
    ax_top.legend(loc="upper right", fontsize='xx-small')
    draw_mplhep_cms_label(ax_top, lumi_fb, region, category)

    ax_bottom.errorbar(
        xb,
        yb,
        xerr=xerrb,
        yerr=yerrb,
        fmt="o",
        color="black",
        markersize=4,
        linewidth=1,
        label="Before",
    )
    ax_bottom.errorbar(
        xa,
        ya,
        xerr=xerra,
        yerr=yerra,
        fmt="o",
        color="blue",
        markersize=4,
        linewidth=1,
        label="After",
    )
    ax_bottom.axhline(1.0, color="gray", linestyle="--", linewidth=1)
    ax_bottom.set_ylim(0.3, 1.7)
    ax_bottom.set_xlabel(r"$p_{T}(\ell\ell)$ [GeV]", fontsize=15)
    ax_bottom.set_ylabel("Closure ratio", fontsize=15)
    ax_bottom.legend(loc="upper left", fontsize='xx-small')
    # fig.tight_layout()
    fig.savefig(output_dir / f"{category}_ptll_reweight_diagnostic.png")
    fig.savefig(output_dir / f"{category}_ptll_reweight_diagnostic.pdf")
    plt.close(fig)


def derive(args):
    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)
    categories = args.categories
    lumi_label = get_luminosity_label(args.era)
    lumi_fb = get_luminosity_fb(args.era)
    manual_rebin_edges = parse_rebin_edges(args.rebin_edges)
    hist_cfg = None
    hist_cfg_source = None

    if args.use_config_rebin and manual_rebin_edges is None:
        hist_cfg_path = args.histogram_config
        if hist_cfg_path is None:
            analysis_path = os.environ.get("ANALYSIS_PATH", os.getcwd())
            hist_cfg_path = os.path.join(
                analysis_path,
                "config",
                "plot",
                "histograms.yaml",
            )
        hist_cfg_source = hist_cfg_path
        hist_cfg = utilities.get_config(hist_cfg_path)

    samples = get_sample_names(input_dir)
    if args.data_sample not in samples:
        raise RuntimeError(f"Data sample '{args.data_sample}' not found in {input_dir}")
    if args.dy_sample not in samples:
        raise RuntimeError(f"DY sample '{args.dy_sample}' not found in {input_dir}")

    other_samples = get_non_dy_subtract_samples(samples, input_dir)

    payload = {
        "type": "dy_ptll_njets_reweight",
        "era": args.era,
        "x_variable": args.variable,
        "inputs": [
            {
                "name": "isVBF",
                "type": "bool",
                "description": "VBF category flag passed at evaluate time.",
            },
            {
                "name": "N_selectedJets",
                "type": "int",
                "description": "N_SelectedJets passed at evaluate time.",
            },
            {
                "name": "ptll",
                "type": "real",
                "description": "pt_mumu passed at evaluate time.",
            },
        ],
        "category_mapping": {
            "ggF": {
                "0": "ggF_0J",
                "1": "ggF_1J",
                "ge2": "ggF_ge2J",
            },
            "VBF": {
                "ge2": "VBF_ge2J",
            },
        },
        "fit_model": "two_gaussians_plus_falling_power",
        "min_weight": args.min_weight,
        "max_weight": args.max_weight,
        "data_sample": args.data_sample,
        "dy_sample": args.dy_sample,
        "dy_scale": args.dy_scale,
        "preserve_yield": args.preserve_yield,
        "subtracted_samples": other_samples,
        "rebin": {
            "histogram_config": hist_cfg_source,
            "manual_edges": manual_rebin_edges,
            "fallback_factor": args.rebin,
            "smart": {
                "enabled": args.smart_rebin,
                "min_dy": args.smart_min_dy,
                "min_target": args.smart_min_target,
                "max_rel_unc": args.smart_max_rel_unc,
            },
        },
        "categories": {},
    }

    Path(args.output_root).parent.mkdir(parents=True, exist_ok=True)
    output_root = ROOT.TFile.Open(args.output_root, "RECREATE")
    if not output_root or output_root.IsZombie():
        raise RuntimeError(f"Cannot create output ROOT file: {args.output_root}")

    data_file = open_sample(input_dir, args.data_sample)
    dy_file = open_sample(input_dir, args.dy_sample)
    normalization_entries = {}

    for category in categories:
        directory_path = f"{args.region}_{category}"
        if manual_rebin_edges is not None:
            rebin_edges = manual_rebin_edges
            rebin_source = "command_line"
        elif hist_cfg is not None:
            rebin_edges = get_config_rebin_edges(hist_cfg, args.variable, directory_path)
            rebin_source = hist_cfg_source
        else:
            rebin_edges = None
            rebin_source = "integer_factor" if args.rebin > 1 else "none"

        data_hist = clone_hist(data_file, directory_path, args.variable, f"data_{category}")
        dy_hist = clone_hist(dy_file, directory_path, args.variable, f"dy_{category}")

        if data_hist is None or dy_hist is None:
            print(f"[WARNING] Missing histograms for {category}: {directory_path}/{args.variable}")
            continue

        dy_hist.Scale(args.dy_scale)
        normalization_hist = dy_hist.Clone(f"dy_{category}_normalization")
        normalization_hist.SetDirectory(0)

        rebin_edges = extend_rebin_edges_to_xmax(rebin_edges, data_hist, args.fit_max)

        original_bins = data_hist.GetNbinsX()
        config_data = apply_rebin(
            data_hist,
            f"data_{category}_config_rebin",
            rebin_factor=args.rebin,
            rebin_edges=rebin_edges,
        )
        config_dy = apply_rebin(
            dy_hist,
            f"dy_{category}_config_rebin",
            rebin_factor=args.rebin,
            rebin_edges=rebin_edges,
        )
        config_other, _ = sum_samples(
            input_dir,
            other_samples,
            directory_path,
            args.variable,
            config_data,
            f"other_{category}_config_rebin",
            args.rebin,
            rebin_edges,
        )

        final_rebin_edges = rebin_edges
        final_rebin_source = rebin_source
        if args.smart_rebin:
            final_rebin_edges = make_smart_rebin_edges(
                config_data,
                config_dy,
                config_other,
                args.smart_min_dy,
                args.smart_min_target,
                args.smart_max_rel_unc,
            )
            final_rebin_source = f"{rebin_source}+smart"

        config_bins = config_data.GetNbinsX()
        data_hist = apply_rebin(
            data_hist,
            f"data_{category}_rebinned",
            rebin_factor=args.rebin,
            rebin_edges=final_rebin_edges,
        )
        dy_hist = apply_rebin(
            dy_hist,
            f"dy_{category}_rebinned",
            rebin_factor=args.rebin,
            rebin_edges=final_rebin_edges,
        )
        other_hist, used_samples = sum_samples(
            input_dir,
            other_samples,
            directory_path,
            args.variable,
            data_hist,
            f"other_{category}",
            args.rebin,
            final_rebin_edges,
        )
        target_hist, ratio_hist = build_ratio_hist(
            data_hist,
            dy_hist,
            other_hist,
            f"ratio_{category}",
            args.min_dy,
        )
        final_bins = data_hist.GetNbinsX()
        print(
            f"[REBIN] {category}: original={original_bins}, "
            f"hist_plotter_like={config_bins}, final_fit={final_bins}, "
            f"source={final_rebin_source}"
        )
        fit_func, fit_payload = fit_ratio(
            ratio_hist,
            category,
            args.fit_min,
            args.fit_max,
        )

        plot_fit_ratio(
            output_dir,
            args.era,
            args.region,
            category,
            ratio_hist,
            fit_func,
            lumi_label=lumi_label,
            lumi_fb=lumi_fb,
            x_min=args.fit_min,
            x_max=args.fit_max,
        )
        plot_reweighting_factor(
            output_dir,
            args.era,
            args.region,
            category,
            ratio_hist,
            fit_func,
            lumi_label=lumi_label,
            lumi_fb=lumi_fb,
            x_min=args.fit_min,
            x_max=args.fit_max,
        )

        output_root.cd()
        category_dir = output_root.mkdir(category)
        category_dir.cd()
        fit_func.Write("fit")

        payload["categories"][category] = {
            "root_path": f"{directory_path}/{args.variable}",
            "rebin": {
                "source": final_rebin_source,
                "factor": args.rebin if final_rebin_edges is None else None,
                "edges": final_rebin_edges,
                "n_original_bins": original_bins,
                "n_config_bins": config_bins,
                "n_final_bins": final_bins,
            },
            "subtracted_samples": used_samples,
            "fit": fit_payload,
        }
        normalization_group = "VBF" if category.startswith("VBF") else "ggF"
        normalization_entries.setdefault(normalization_group, []).append(
            {
                "category": category,
                "normalization_hist": normalization_hist,
                "fit_func": fit_func,
                "fit_payload": fit_payload,
                "root_directory": category_dir,
            }
        )

    payload["shape_only_normalization"] = {}
    if args.preserve_yield:
        for normalization_group, entries in normalization_entries.items():
            scale, yield_before, yield_after = solve_shape_only_scale(
                entries,
                args.min_weight,
                args.max_weight,
            )
            for entry in entries:
                scale_fit_payload(entry, scale)
                entry["root_directory"].cd()
                entry["fit_func"].Write("fit_shape_only", ROOT.TObject.kOverwrite)

            payload["shape_only_normalization"][normalization_group] = {
                "enabled": True,
                "scale": float(scale),
                "yield_before": float(yield_before),
                "yield_after": float(yield_after),
            }
            print(
                f"[PRESERVE YIELD] {normalization_group}: scale={scale:.12g}, "
                f"yield={yield_before:.12g} -> {yield_after:.12g}"
            )
    else:
        for normalization_group, entries in normalization_entries.items():
            yield_before = sum(
                entry["normalization_hist"].Integral(
                    0,
                    entry["normalization_hist"].GetNbinsX() + 1,
                )
                for entry in entries
            )
            payload["shape_only_normalization"][normalization_group] = {
                "enabled": False,
                "scale": 1.0,
                "yield_before": float(yield_before),
                "yield_after": None,
            }
            print(
                f"[PRESERVE YIELD disabled] {normalization_group}: "
                "using unnormalized pt(ll) fit weights"
            )

    data_file.Close()
    dy_file.Close()
    output_root.Close()

    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, "w") as handle:
        json.dump(make_ptll_correctionlib_payload(payload), handle, indent=2, sort_keys=True)

    print(f"[INFO] Wrote JSON: {args.output_json}")
    print(f"[INFO] Wrote ROOT: {args.output_root}")
    print(f"[INFO] Wrote plots under: {output_dir}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--era", required=True)
    parser.add_argument("--input-dir", required=True, help="Hadded histogram directory")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--region", default="Z_sideband")
    parser.add_argument("--variable", default="pt_mumu")
    parser.add_argument("--data-sample", default="Data_Muon")
    parser.add_argument("--dy-sample", default="DY")
    parser.add_argument("--categories", nargs="+", default=DEFAULT_CATEGORIES)
    parser.add_argument(
        "--histogram-config",
        default=None,
        help=(
            "Histogram YAML config used to get x_rebin. "
            "Defaults to $ANALYSIS_PATH/config/plot/histograms.yaml."
        ),
    )
    parser.add_argument(
        "--no-config-rebin",
        dest="use_config_rebin",
        action="store_false",
        help="Disable x_rebin from the histogram config.",
    )
    parser.set_defaults(use_config_rebin=True)
    parser.add_argument(
        "--rebin",
        type=int,
        default=1,
        help=(
            "Integer rebin factor used only when config rebin is disabled "
            "or no config/manual edges are available."
        ),
    )
    parser.add_argument(
        "--rebin-edges",
        default=None,
        help="Comma-separated variable bin edges overriding the histogram config",
    )
    parser.add_argument(
        "--smart-rebin",
        dest="smart_rebin",
        action="store_true",
        help=(
            "After the histogram-config rebinning, merge neighboring bins "
            "until the ratio has enough statistics. Disabled by default so "
            "the nominal binning matches hist_plotter --rebin."
        ),
    )
    parser.set_defaults(smart_rebin=False)
    parser.add_argument(
        "--smart-min-dy",
        type=float,
        default=100.0,
        help="Minimum DY yield required in each smart-rebinned fit bin.",
    )
    parser.add_argument(
        "--smart-min-target",
        type=float,
        default=20.0,
        help="Minimum absolute Data-nonDY yield required in each smart-rebinned fit bin.",
    )
    parser.add_argument(
        "--smart-max-rel-unc",
        type=float,
        default=0.15,
        help="Maximum relative uncertainty allowed for each ratio fit bin.",
    )
    parser.add_argument("--fit-min", type=float, default=0.0)
    parser.add_argument("--fit-max", type=float, default=200.0)
    parser.add_argument("--min-dy", type=float, default=1e-9)
    parser.add_argument(
        "--dy-scale",
        type=float,
        default=1.0,
        help=(
            "Scale applied to the input DY histogram before deriving the correction. "
            "Histograms produced by hist_maker.py already contain the standard "
            f"DY amc@nlo normalization ({DY_AMCATNLO_NORMALIZATION:.16g}); "
            "use this option only for historical unnormalized inputs."
        ),
    )
    parser.add_argument("--min-weight", type=float, default=0.0)
    parser.add_argument("--max-weight", type=float, default=5.0)
    preserve_yield_group = parser.add_mutually_exclusive_group()
    preserve_yield_group.add_argument(
        "--preserve-yield",
        dest="preserve_yield",
        action="store_true",
        help=(
            "Normalize the derived pt(ll) weights so the DY yield is preserved. "
            "Enabled by default."
        ),
    )
    preserve_yield_group.add_argument(
        "--no-preserve-yield",
        dest="preserve_yield",
        action="store_false",
        help=(
            "Do not normalize the derived pt(ll) weights; the correction is allowed "
            "to change the DY yield."
        ),
    )
    parser.set_defaults(preserve_yield=True)
    return parser.parse_args()


if __name__ == "__main__":
    derive(parse_args())
