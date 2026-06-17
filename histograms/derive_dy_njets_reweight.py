#!/usr/bin/env python3

import argparse
import json
import math
import os
from pathlib import Path

import ROOT

ROOT.gROOT.SetBatch(True)


DEFAULT_CATEGORIES = ["ggF", "VBF"]
CORRECTIONLIB_NJETS_MAX_EDGE = 999.5
NON_DY_SUBTRACT_SAMPLES = [
    "EWK",
    # "EWK_2Mu2J_MLL_105to160_herwig",
    # "EWK_2Mu2J_MLL_105to160_pythia",
    # "EWK_2Mu2J_MLL_105to160_pythia_Flashsim",
    "H_mainBckg",
    "ST",
    "TT",
    "TTX",
    "TW",
    "VV",
    "VVV",
    "W",
    # "GluGluHto2Mu",
    # "GluGluHto2Mu_amcatnlo",
    # "GluGluHto2Mu_M120",
    # "GluGluHto2Mu_M130",
    # "GluGluHto2Mu_MiNNLO",
    # "GluGluHto2Mu_tuneDown",
    # "GluGluHto2Mu_tuneUp",
    # "VBFHto2Mu_M125_amcatnlo",
    # "VBFHto2Mu_M125_powheg",
    # "VBFHto2Mu_m120",
    # "VBFHto2Mu_m125_Flashsim",
    # "VBFHto2Mu_m125_tuneDown",
    # "VBFHto2Mu_m125_tuneUp",
    # "VBFHto2Mu_m130",
    # "TTH_inclusive",
    # "TTHto2Mu",
    # "VH_inclusive",
    # "VHto2Mu",
]


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
    if missing_samples:
        raise RuntimeError(
            f"Samples listed in NON_DY_SUBTRACT_SAMPLES not found in {input_dir}: "
            f"{missing_samples}"
        )

    return list(NON_DY_SUBTRACT_SAMPLES)


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


def plot_data_mc(output_dir, category, data_hist, dy_hist, other_hist, total_mc_hist, ratio_hist):
    ROOT.gStyle.SetOptStat(0)
    canvas = ROOT.TCanvas(f"c_njets_{category}", category, 900, 900)
    canvas.Divide(1, 2)

    upper = canvas.cd(1)
    upper.SetPad(0.0, 0.35, 1.0, 1.0)
    upper.SetBottomMargin(0.02)
    upper.SetLogy()

    data_hist.SetMarkerStyle(20)
    data_hist.SetMarkerColor(ROOT.kBlack)
    data_hist.SetLineColor(ROOT.kBlack)
    dy_hist.SetLineColor(ROOT.kAzure + 1)
    dy_hist.SetFillColorAlpha(ROOT.kAzure + 1, 0.25)
    other_hist.SetLineColor(ROOT.kOrange + 7)
    other_hist.SetFillColorAlpha(ROOT.kOrange + 7, 0.25)

    stack = ROOT.THStack(f"stack_njets_{category}", "")
    stack.Add(dy_hist, "HIST")
    stack.Add(other_hist, "HIST")

    ymax = max(data_hist.GetMaximum(), total_mc_hist.GetMaximum(), 1.0)
    stack.SetMinimum(0.1)
    stack.SetMaximum(100.0 * ymax)
    stack.Draw("HIST")
    stack.SetTitle(f"{category};N_{{selected jets}};Events")
    stack.GetYaxis().SetTitle("Events")
    stack.GetXaxis().SetTitle("N_{selected jets}")
    data_hist.Draw("E SAME")

    legend = ROOT.TLegend(0.58, 0.62, 0.88, 0.88)
    legend.SetBorderSize(0)
    legend.SetFillStyle(0)
    legend.AddEntry(data_hist, "Data", "lep")
    legend.AddEntry(dy_hist, "DY", "f")
    legend.AddEntry(other_hist, "non-DY MC", "f")
    legend.Draw()

    lower = canvas.cd(2)
    lower.SetPad(0.0, 0.0, 1.0, 0.35)
    lower.SetTopMargin(0.03)
    lower.SetBottomMargin(0.3)

    ratio_hist.SetMarkerStyle(20)
    ratio_hist.SetMarkerColor(ROOT.kBlack)
    ratio_hist.SetLineColor(ROOT.kBlack)
    ratio_hist.SetTitle(";N_{selected jets};Data/all MC")
    ratio_hist.GetYaxis().SetTitleSize(0.08)
    ratio_hist.GetYaxis().SetTitleOffset(0.55)
    ratio_hist.GetYaxis().SetLabelSize(0.07)
    ratio_hist.GetXaxis().SetTitleSize(0.09)
    ratio_hist.GetXaxis().SetLabelSize(0.08)
    ratio_hist.SetMinimum(0.0)
    ratio_hist.SetMaximum(max(2.0, 1.4 * ratio_hist.GetMaximum()))
    ratio_hist.Draw("E")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    canvas.SaveAs(str(output_dir / f"{category}_njets_data_mc.png"))
    canvas.SaveAs(str(output_dir / f"{category}_njets_data_mc.pdf"))


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


def plot_diagnostic(output_dir, category, ratio_hist, after_hist):
    ROOT.gStyle.SetOptStat(0)
    canvas = ROOT.TCanvas(f"c_njets_diagnostic_{category}", category, 900, 900)
    canvas.Divide(1, 2)

    upper = canvas.cd(1)
    upper.SetPad(0.0, 0.52, 1.0, 1.0)
    upper.SetBottomMargin(0.03)

    ratio_hist.SetMarkerStyle(20)
    ratio_hist.SetMarkerColor(ROOT.kBlack)
    ratio_hist.SetLineColor(ROOT.kBlack)
    ratio_hist.SetTitle(f"Reweighting factor {category};N_{{selected jets}};Data / DY")
    ratio_hist.GetXaxis().SetLabelSize(0.0)
    ratio_hist.GetYaxis().SetTitleSize(0.055)
    ratio_hist.GetYaxis().SetTitleOffset(0.85)
    ratio_hist.SetMinimum(0.0)
    ratio_hist.SetMaximum(max(2.0, 1.4 * ratio_hist.GetMaximum()))
    ratio_hist.Draw("E")

    before = ratio_hist.Clone(f"before_reweight_{category}")
    before.SetDirectory(0)

    lower = canvas.cd(2)
    lower.SetPad(0.0, 0.0, 1.0, 0.48)
    lower.SetTopMargin(0.06)
    lower.SetBottomMargin(0.16)

    before.SetMarkerStyle(20)
    before.SetMarkerColor(ROOT.kBlack)
    before.SetLineColor(ROOT.kBlack)
    before.SetTitle(";N_{selected jets};Reweighted Data / MC")
    before.GetXaxis().SetTitleSize(0.055)
    before.GetXaxis().SetLabelSize(0.045)
    before.GetYaxis().SetTitleSize(0.055)
    before.GetYaxis().SetTitleOffset(0.85)
    before.SetMinimum(0.5)
    before.SetMaximum(1.5)
    before.Draw("E")

    after_hist.SetMarkerStyle(20)
    after_hist.SetMarkerColor(ROOT.kRed)
    after_hist.SetLineColor(ROOT.kRed)
    after_hist.Draw("E SAME")

    legend = ROOT.TLegend(0.12, 0.78, 0.32, 0.94)
    legend.SetBorderSize(1)
    legend.SetFillStyle(0)
    legend.AddEntry(before, "Before", "lep")
    legend.AddEntry(after_hist, "After", "lep")
    legend.Draw()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    canvas.SaveAs(str(output_dir / f"{category}_njets_reweight_diagnostic.png"))
    canvas.SaveAs(str(output_dir / f"{category}_njets_reweight_diagnostic.pdf"))


def derive(args):
    input_dir = os.path.abspath(args.input_dir)
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
        "data_sample": args.data_sample,
        "dy_sample": args.dy_sample,
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
            category,
            data_hist,
            dy_hist,
            other_hist,
            total_mc_hist,
            data_over_mc_hist,
        )
        plot_diagnostic(args.output_dir, category, ratio_hist, after_hist)

        output_root.cd()
        category_dir = output_root.mkdir(category)
        category_dir.cd()
        for hist in [
            data_hist,
            dy_hist,
            other_hist,
            total_mc_hist,
            target_hist,
            ratio_hist,
            data_over_mc_hist,
            after_hist,
        ]:
            hist.Write()

        payload["categories"][category] = {
            "root_path": hist_path,
            "subtracted_samples": used_samples,
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
    parser.add_argument("--min-weight", type=float, default=0.0)
    parser.add_argument("--max-weight", type=float, default=5.0)
    return parser.parse_args()


if __name__ == "__main__":
    derive(parse_args())
