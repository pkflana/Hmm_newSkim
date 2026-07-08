#!/usr/bin/env python3

import argparse
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


DEFAULT_CATEGORIES = ["ggF", "VBF"]
CORRECTIONLIB_NJETS_MAX_EDGE = 999.5
NON_DY_SUBTRACT_SAMPLES = [
    "EWK",
    "H_mainBckg",
    "ST",
    "TT",
    "TTX",
    # "TW",
    "VV",
    "VVV",
    # "W_NJets",
    "W",
]


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


def hist_to_arrays(hist):
    edges = []
    values = []
    errors = []
    for bin_idx in range(1, hist.GetNbinsX() + 1):
        if bin_idx == 1:
            edges.append(hist.GetXaxis().GetBinLowEdge(bin_idx))
        edges.append(hist.GetXaxis().GetBinUpEdge(bin_idx))
        value = hist.GetBinContent(bin_idx)
        error = hist.GetBinError(bin_idx)
        values.append(value if math.isfinite(value) else 0.0)
        errors.append(error if math.isfinite(error) else 0.0)
    return np.asarray(edges), np.asarray(values), np.asarray(errors)


def hist_to_points(hist):
    edges, values, errors = hist_to_arrays(hist)
    centers = 0.5 * (edges[:-1] + edges[1:])
    xerr = np.asarray([centers - edges[:-1], edges[1:] - centers])
    return centers, xerr, values, errors


def draw_mplhep_cms_label(ax, lumi_fb, region, category):
    label = f"Preliminary {region}/{category}"
    kwargs = {"ax": ax, "data": True, "label": label, "com": 13.6}
    if lumi_fb is not None:
        kwargs["lumi"] = lumi_fb
    try:
        hep.cms.label(**kwargs)
    except TypeError:
        kwargs.pop("label", None)
        hep.cms.label(label, **kwargs)


def correctionlib_variable(name, var_type, description):
    return {
        "name": name,
        "type": var_type,
        "description": description,
    }


def root_path(input_dir, sample):
    return os.path.join(input_dir, f"{sample}.root")


def get_sample_names(input_dir):
    return sorted(path.stem for path in Path(input_dir).glob("*.root") if path.is_file())


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


def clone_hist(root_file, hist_path, name):
    hist = root_file.Get(hist_path)
    if not hist or not hist.InheritsFrom("TH1"):
        return None
    out = hist.Clone(name)
    out.SetDirectory(0)
    return out


def empty_like(reference, name):
    hist = reference.Clone(name)
    hist.Reset("ICES")
    hist.SetDirectory(0)
    return hist


def sum_samples(input_dir, samples, hist_path, reference, name):
    total = empty_like(reference, name)
    used = []

    for sample in samples:
        root_file = ROOT.TFile.Open(root_path(input_dir, sample), "READ")
        if not root_file or root_file.IsZombie():
            continue

        hist = root_file.Get(hist_path)
        if hist and hist.InheritsFrom("TH1"):
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

    bins = []
    for bin_idx in range(1, data_hist.GetNbinsX() + 1):
        dy = dy_hist.GetBinContent(bin_idx)
        if dy <= min_dy:
            weight = 1.0
            error = 0.0
            ratio.SetBinContent(bin_idx, weight)
            ratio.SetBinError(bin_idx, error)
            bins.append(bin_payload(data_hist, bin_idx, weight, error, dy, 0.0))
            continue

        data = data_hist.GetBinContent(bin_idx)
        other = other_hist.GetBinContent(bin_idx)
        target_content = data - other
        data_err = data_hist.GetBinError(bin_idx)
        other_err = other_hist.GetBinError(bin_idx)
        dy_err = dy_hist.GetBinError(bin_idx)
        target_err = math.sqrt(data_err * data_err + other_err * other_err)

        weight = target_content / dy
        if target_content != 0.0:
            error = abs(weight) * math.sqrt(
                (target_err / target_content) ** 2 + (dy_err / dy) ** 2
            )
        else:
            error = target_err / dy

        ratio.SetBinContent(bin_idx, weight)
        ratio.SetBinError(bin_idx, error)
        bins.append(bin_payload(data_hist, bin_idx, weight, error, dy, target_content))

    return target, ratio, bins


def normalize_bins_shape_only(bins, dy_hist, min_weight, max_weight):
    target = dy_hist.Integral(0, dy_hist.GetNbinsX() + 1)
    if target <= 0.0:
        return 1.0, target, target

    def weighted_yield(scale):
        total = 0.0
        for bin_idx, bin_info in enumerate(bins, start=1):
            weight = scale * float(bin_info["weight"])
            weight = min(max(weight, min_weight), max_weight)
            total += dy_hist.GetBinContent(bin_idx) * weight
            if bin_idx == 1:
                total += dy_hist.GetBinContent(0) * weight
            if bin_idx == len(bins):
                total += dy_hist.GetBinContent(dy_hist.GetNbinsX() + 1) * weight
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
    yield_after = weighted_yield(scale)
    for bin_info in bins:
        bin_info["weight"] = min(
            max(scale * float(bin_info["weight"]), min_weight),
            max_weight,
        )
        bin_info["shape_only_scale"] = float(scale)

    return scale, target, yield_after


def build_data_over_mc_hist(data_hist, dy_hist, other_hist, name, min_mc):
    total_mc = dy_hist.Clone(f"{name}_total_mc")
    total_mc.SetDirectory(0)
    total_mc.Add(other_hist)

    ratio = data_hist.Clone(name)
    ratio.Reset("ICES")
    ratio.SetDirectory(0)
    ratio.GetYaxis().SetTitle("Data / all MC")

    for bin_idx in range(1, data_hist.GetNbinsX() + 1):
        mc = total_mc.GetBinContent(bin_idx)
        if mc <= min_mc:
            continue

        data = data_hist.GetBinContent(bin_idx)
        data_err = data_hist.GetBinError(bin_idx)
        mc_err = total_mc.GetBinError(bin_idx)

        value = data / mc
        if data != 0.0:
            error = abs(value) * math.sqrt(
                (data_err / data) ** 2 + (mc_err / mc) ** 2
            )
        else:
            error = data_err / mc

        ratio.SetBinContent(bin_idx, value)
        ratio.SetBinError(bin_idx, error)

    return total_mc, ratio


def bin_payload(hist, bin_idx, weight, error, dy, target):
    axis = hist.GetXaxis()
    low = float(axis.GetBinLowEdge(bin_idx))
    high = None
    if bin_idx < hist.GetNbinsX():
        high = float(axis.GetBinUpEdge(bin_idx))
    return {
        "low": low,
        "high": high,
        "weight": float(weight),
        "error": float(error),
        "dy": float(dy),
        "target": float(target),
    }


def make_njets_binning_node(bins):
    if not bins:
        return 1.0

    edges = [float(bins[0]["low"])]
    content = []
    for bin_info in bins:
        high = bin_info.get("high")
        if high is None:
            high = CORRECTIONLIB_NJETS_MAX_EDGE
        edges.append(float(high))
        content.append(float(bin_info["weight"]))

    return {
        "nodetype": "binning",
        "input": "nSelectedJets",
        "edges": edges,
        "content": content,
        "flow": "clamp",
    }


def make_njets_correctionlib_payload(category_payloads):
    return {
        "schema_version": 2,
        "corrections": [
            {
                "name": "dy_njets_reweight",
                "description": "DY N_selected jets bin-by-bin reweighting from (Data - nonDY) / DY.",
                "version": 1,
                "inputs": [
                    correctionlib_variable(
                        "isVBF",
                        "int",
                        "VBF category flag: 1 for VBF, 0 for ggF.",
                    ),
                    correctionlib_variable(
                        "nSelectedJets",
                        "real",
                        "Number of selected jets.",
                    ),
                ],
                "output": {
                    "name": "weight",
                    "type": "real",
                    "description": "DY N_selected jets event weight.",
                },
                "data": {
                    "nodetype": "category",
                    "input": "isVBF",
                    "content": [
                        {
                            "key": 0,
                            "value": make_njets_binning_node(
                                category_payloads.get("ggF", {}).get("bins", [])
                            ),
                        },
                        {
                            "key": 1,
                            "value": make_njets_binning_node(
                                category_payloads.get("VBF", {}).get("bins", [])
                            ),
                        },
                    ],
                    "default": 1.0,
                },
            }
        ],
    }


def plot_data_mc(output_dir, era, region, category, data_hist, dy_hist, other_hist, total_mc_hist, ratio_hist, lumi_label="", lumi_fb=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    edges, dy_vals, _ = hist_to_arrays(dy_hist)
    _, other_vals, _ = hist_to_arrays(other_hist)
    data_x, data_xerr, data_vals, data_errs = hist_to_points(data_hist)
    ratio_x, ratio_xerr, ratio_vals, ratio_errs = hist_to_points(ratio_hist)

    fig, (ax_top, ax_bottom) = plt.subplots(
        2,
        1,
        figsize=(9, 9),
        sharex=True,
        gridspec_kw={"height_ratios": [2.0, 1.0], "hspace": 0.08},
    )
    widths = np.diff(edges)
    ax_top.bar(edges[:-1], dy_vals, widths, align="edge", color="#8ecaff", edgecolor="#2b7bff", label="DY")
    ax_top.bar(
        edges[:-1],
        other_vals,

        widths,
        align="edge",
        bottom=dy_vals,
        color="#ffbf91",
        edgecolor="#ff7f0e",
        label="non-DY MC",
    )
    ax_top.errorbar(data_x, data_vals, xerr=data_xerr, yerr=data_errs, fmt="o", color="black", label="Data")
    ax_top.set_yscale("log")
    ax_top.set_ylabel("Events")
    ax_top.set_ylim(0.1, max(1.0, 100.0 * max(np.max(data_vals), np.max(dy_vals + other_vals))))
    ax_top.legend(loc="upper right")
    draw_mplhep_cms_label(ax_top, lumi_fb, region, category)

    ax_bottom.errorbar(
        ratio_x,
        ratio_vals,
        xerr=ratio_xerr,
        yerr=ratio_errs,
        fmt="o",
        color="black",
        markersize=4,
    )
    ax_bottom.axhline(1.0, color="gray", linestyle="--", linewidth=1)
    ax_bottom.set_ylabel("Data/all MC")
    ax_bottom.set_xlabel(r"$N_{\mathrm{selected\ jets}}$")
    ax_bottom.set_ylim(0.0, max(2.0, 1.4 * float(np.nanmax(ratio_vals)) if ratio_vals.size else 2.0))
    fig.tight_layout()
    fig.savefig(output_dir / f"{category}_njets_data_mc.png")
    fig.savefig(output_dir / f"{category}_njets_data_mc.pdf")
    plt.close(fig)


def make_after_reweight_ratio(ratio_hist, name):
    after = ratio_hist.Clone(name)
    after.Reset("ICES")
    after.SetDirectory(0)

    for bin_idx in range(1, ratio_hist.GetNbinsX() + 1):
        weight = ratio_hist.GetBinContent(bin_idx)
        error = ratio_hist.GetBinError(bin_idx)
        if weight == 0.0 or not math.isfinite(weight):
            continue

        after.SetBinContent(bin_idx, 1.0)
        after.SetBinError(bin_idx, error / abs(weight))

    return after


def plot_diagnostic(output_dir, era, region, category, ratio_hist, after_hist, lumi_label="", lumi_fb=None):
    before = ratio_hist.Clone(f"before_reweight_{category}")
    before.SetDirectory(0)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    x, xerr, y, yerr = hist_to_points(ratio_hist)
    xb, xerrb, yb, yerrb = hist_to_points(before)
    xa, xerra, ya, yerra = hist_to_points(after_hist)

    fig, (ax_top, ax_bottom) = plt.subplots(
        2,
        1,
        figsize=(9, 9),
        sharex=True,
        gridspec_kw={"height_ratios": [1.05, 1.0], "hspace": 0.08},
    )
    ax_top.errorbar(x, y, xerr=xerr, yerr=yerr, fmt="o", color="black", markersize=5)
    ax_top.set_ylabel("(Data - non-DY) / DY")
    ax_top.set_ylim(0.0, max(2.0, 1.4 * float(np.nanmax(y)) if y.size else 2.0))
    draw_mplhep_cms_label(ax_top, lumi_fb, region, category)

    ax_bottom.errorbar(xb, yb, xerr=xerrb, yerr=yerrb, fmt="o", color="black", markersize=5, label="Before")
    ax_bottom.errorbar(xa, ya, xerr=xerra, yerr=yerra, fmt="o", color="red", markersize=5, label="After")
    ax_bottom.axhline(1.0, color="gray", linestyle="--", linewidth=1)
    ax_bottom.set_ylabel("Closure ratio")
    ax_bottom.set_xlabel(r"$N_{\mathrm{selected\ jets}}$")
    ax_bottom.set_ylim(0.5, 1.5)
    ax_bottom.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(output_dir / f"{category}_njets_reweight_diagnostic.png")
    fig.savefig(output_dir / f"{category}_njets_reweight_diagnostic.pdf")
    plt.close(fig)


def derive(args):
    input_dir = os.path.abspath(args.input_dir)
    lumi_label = get_luminosity_label(args.era)
    lumi_fb = get_luminosity_fb(args.era)
    samples = get_sample_names(input_dir)
    if args.data_sample not in samples:
        raise RuntimeError(f"Data sample '{args.data_sample}' not found in {input_dir}")
    if args.dy_sample not in samples:
        raise RuntimeError(f"DY sample '{args.dy_sample}' not found in {input_dir}")

    other_samples = get_non_dy_subtract_samples(samples, input_dir)

    payload = {
        "type": "dy_njets_reweight",
        "era": args.era,
        "variable": args.variable,
        "inputs": [
            {
                "name": "isVBF",
                "type": "bool",
                "description": "VBF category flag passed at evaluate time.",
            },
            {
                "name": "nSelectedJets",
                "type": "int",
                "description": "N_SelectedJets passed at evaluate time.",
            },
        ],
        "min_weight": args.min_weight,
        "max_weight": args.max_weight,
        "preserve_yield": args.preserve_yield,
        "data_sample": args.data_sample,
        "dy_sample": args.dy_sample,
        "dy_scale": args.dy_scale,
        "subtracted_samples": other_samples,
        "categories": {},
    }

    Path(args.output_root).parent.mkdir(parents=True, exist_ok=True)
    output_root = ROOT.TFile.Open(args.output_root, "RECREATE")
    if not output_root or output_root.IsZombie():
        raise RuntimeError(f"Cannot create output ROOT file: {args.output_root}")

    data_file = open_sample(input_dir, args.data_sample)
    dy_file = open_sample(input_dir, args.dy_sample)

    for category in args.categories:
        hist_path = f"{args.region}_{category}/{args.variable}"
        data_hist = clone_hist(data_file, hist_path, f"data_{category}")
        dy_hist = clone_hist(dy_file, hist_path, f"dy_{category}")
        if data_hist is None or dy_hist is None:
            print(f"[WARNING] Missing histograms for {category}: {hist_path}")
            continue

        dy_hist.Scale(args.dy_scale)

        other_hist, used_samples = sum_samples(
            input_dir,
            other_samples,
            hist_path,
            data_hist,
            f"other_{category}",
        )
        target_hist, ratio_hist, bins = build_ratio_hist(
            data_hist,
            dy_hist,
            other_hist,
            f"ratio_{category}",
            args.min_dy,
        )
        yield_before = dy_hist.Integral(0, dy_hist.GetNbinsX() + 1)
        if args.preserve_yield:
            normalization_scale, yield_before, yield_after = normalize_bins_shape_only(
                bins,
                dy_hist,
                args.min_weight,
                args.max_weight,
            )
            for bin_idx, bin_info in enumerate(bins, start=1):
                ratio_hist.SetBinContent(bin_idx, bin_info["weight"])
            print(
                f"[PRESERVE YIELD] {category}: scale={normalization_scale:.12g}, "
                f"yield={yield_before:.12g} -> {yield_after:.12g}"
            )
        else:
            normalization_scale = 1.0
            yield_after = None
            for bin_info in bins:
                bin_info["weight"] = min(
                    max(float(bin_info["weight"]), args.min_weight),
                    args.max_weight,
                )
            print(
                f"[PRESERVE YIELD disabled] {category}: "
                "using unnormalized nJet bin weights"
            )
        total_mc_hist, data_over_mc_hist = build_data_over_mc_hist(
            data_hist,
            dy_hist,
            other_hist,
            f"data_over_mc_{category}",
            args.min_dy,
        )
        after_hist = make_after_reweight_ratio(
            ratio_hist,
            f"after_reweight_{category}",
        )
        plot_data_mc(
            args.output_dir,
            args.era,
            args.region,
            category,
            data_hist,
            dy_hist,
            other_hist,
            total_mc_hist,
            data_over_mc_hist,
            lumi_label=lumi_label,
            lumi_fb=lumi_fb,
        )
        plot_diagnostic(
            args.output_dir,
            args.era,
            args.region,
            category,
            ratio_hist,
            after_hist,
            lumi_label=lumi_label,
            lumi_fb=lumi_fb,
        )

        output_root.cd()
        output_root.mkdir(category)

        payload["categories"][category] = {
            "root_path": hist_path,
            "subtracted_samples": used_samples,
            "shape_only_normalization": {
                "enabled": args.preserve_yield,
                "scale": float(normalization_scale),
                "yield_before": float(yield_before),
                "yield_after": float(yield_after) if yield_after is not None else None,
            },
            "bins": bins,
        }

    data_file.Close()
    dy_file.Close()
    output_root.Close()

    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, "w") as handle:
        json.dump(make_njets_correctionlib_payload(payload["categories"]), handle, indent=2, sort_keys=True)

    print(f"[INFO] Wrote JSON: {args.output_json}")
    print(f"[INFO] Wrote ROOT: {args.output_root}")
    print(f"[INFO] Wrote plots under: {args.output_dir}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--era", required=True)
    parser.add_argument("--input-dir", required=True, help="Hadded histogram directory")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--region", default="Z_sideband")
    parser.add_argument("--variable", default="N_SelectedJets")
    parser.add_argument("--data-sample", default="Data_Muon")
    parser.add_argument("--dy-sample", default="DY")
    parser.add_argument("--categories", nargs="+", default=DEFAULT_CATEGORIES)
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
            "Normalize the derived nJet weights so the DY yield is preserved. "
            "Enabled by default."
        ),
    )
    preserve_yield_group.add_argument(
        "--no-preserve-yield",
        dest="preserve_yield",
        action="store_false",
        help=(
            "Do not normalize the derived nJet weights; the correction is allowed "
            "to change the DY yield."
        ),
    )
    parser.set_defaults(preserve_yield=True)
    return parser.parse_args()


if __name__ == "__main__":
    derive(parse_args())
