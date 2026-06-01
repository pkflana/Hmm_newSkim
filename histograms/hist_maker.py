#!/usr/bin/env python3

import ROOT
import sys
import os
import argparse
import time
import json

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])

import analysis.utilities as utilities

HEADERS = ["analysis/AnalysisTools.h"]
for header in HEADERS:
    utilities.DeclareHeader(f"{os.environ['ANALYSIS_PATH']}/{header}")

from histograms.helpers import GetModel
from histograms.add_vars import *
from histograms.defineTriggerWeights import AddTriggerWeightsAndErrors

parser = argparse.ArgumentParser()
parser.add_argument( "--era", required=True, type=str)
parser.add_argument( "--input", required=True, type=str, help="ROOT file or dataset directory")
parser.add_argument( "--dataset-name", required=True, type=str)
parser.add_argument( "--output-file", required=True, type=str)
parser.add_argument( "--systematics", choices=["central", "all"], default="central")
args = parser.parse_args()

startTime = time.time()

cfg_dir = os.path.join( os.environ["ANALYSIS_PATH"],"config",args.era)
main_cfg = utilities.get_config(os.path.join(cfg_dir, "maincfg.yaml"))
dataset_cfg = utilities.get_config(os.path.join(cfg_dir, "samples.yaml"))[args.dataset_name]
is_data = dataset_cfg.get("is_data", False)
sel_cfg = utilities.get_config(os.path.join(cfg_dir, "selections.yaml"))
syst_cfg = utilities.get_config(os.path.join(cfg_dir, "systematics.yaml"))
hist_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"],"config","plot","histograms.yaml"))

def is_valid_root_file(filename, tree_name="Events"):
    try:
        f = ROOT.TFile.Open(filename)
        if not f or f.IsZombie():
            return False
        tree = f.Get(tree_name)
        if tree is None:
            f.Close()
            return False
        if tree.GetEntries() == 0:
            f.Close()
            return False
        f.Close()
        return True
    except Exception:
        return False

def get_valid_root_files(files, tree_name="Events"):
    valid_files = []
    for f in files:
        if is_valid_root_file(f, tree_name):
            valid_files.append(f)
        else:
            print(f"[WARNING] Skipping invalid file: {f}")
    return valid_files

def get_root_files(path):
    if path.endswith(".root"):
        return [path]
    files = []
    for root, _, fnames in os.walk(path):
        for f in fnames:
            if not f.endswith(".root"):
                continue
            files.append(
                os.path.join(root, f)
            )
    return sorted(files)

input_files = get_root_files(args.input)
input_files = get_valid_root_files(input_files,"Events")
has_valid_input = len(input_files) > 0

if not has_valid_input:
    print(
        "[WARNING] No valid ROOT files with "
        "non-empty Events tree found."
    )
def get_n_orig(input_dir):
    n_orig = 0.
    for root, _, files in os.walk(input_dir):
        for f in files:
            if not f.endswith(".json"):
                continue
            with open(os.path.join(root, f)) as jf:
                info = json.load(jf)
            if "Initial" not in info:
                continue
            value = info["Initial"]
            if isinstance(value, dict):
                n_orig += sum(value.values())
            else:
                n_orig += float(value)
    # print(f"N_orig is {n_orig}")
    return n_orig

N_orig = get_n_orig(args.input)

def build_rdf(input_files, is_data):
    rdf = ROOT.RDataFrame("Events",utilities.ListToVector(input_files))
    if not is_data:
        rdf = AddTriggerWeightsAndErrors(
            rdf,
            WantErrors=False
        )
    rdf = SelectedJetObservablesDef(rdf)
    rdf = VBFJetObservablesDef(rdf)
    rdf = GetAllMuonsObservablesNew(rdf)
    rdf = VBFJetMuonsObservablesDef(rdf)
    rdf = SoftJetCollectionCleaningInVBF(rdf)
    return rdf

rdf_base = None

if has_valid_input:
    rdf_base = build_rdf(input_files,is_data)
    rdf_base = rdf_base.Define("N_orig",f"{N_orig}")

masses_regions = sel_cfg["masses_regions"]
categories = sel_cfg["categories"]
masses_regions_list = ["Z_sideband"]#,"Signal_Fit"]
categories_list = ["baseline","ggF","VBF"]
vars_to_make_hist = main_cfg["variables"]

for weight_name, weight_info in syst_cfg["weights"].items():
    if weight_name != "Central":
        continue
    expr = "1.f" if is_data else f"({weight_info['expression']}) / N_orig"
    rdf_base = rdf_base.Define(f"weight__{weight_name}",expr)

if args.systematics == "central":
    systs_to_run = {
        "Central": syst_cfg["systematics"]["Central"]
    }
else:
    systs_to_run = syst_cfg["systematics"]

outFile = ROOT.TFile(args.output_file,"RECREATE")

for syst_name, syst_info in systs_to_run.items():
    # print("\n========================================")
    # print(f"Running systematic: {syst_name}")
    # print("========================================")
    mu_suffix = syst_info["muon_suffix"]
    jet_suffix = syst_info["jet_suffix"]
    weight_name = syst_info["weight"]

    rdf = rdf_base
    for mass_region, mass_info in masses_regions.items():
        if mass_region not in masses_regions_list: continue
        if not mass_info["store"]: continue
        for category, cat_info in categories.items():
            if category not in categories_list: continue
            if not cat_info["store"]: continue
            print(f"Processing: {mass_region} / {category}")
            rdf_sel = rdf.Filter(f"{mass_region} && {category}")
            dir_ptr = utilities.mkdir_recursive(outFile,f"{mass_region}_{category}")
            for var in vars_to_make_hist:
                model = GetModel(hist_cfg,var,dims=1)
                hist_name = var if syst_name == "Central" else f"{var}_{syst_name}"
                if has_valid_input:
                    hist = rdf_sel.Histo1D(model,var,weight_name).GetValue()
                else:
                    hist = ROOT.TH1D(hist_name,hist_name,model.fNbinsX,model.fXLow,model.fXUp)
                # hist = rdf_sel.Histo1D(model,var,f"{weight_name}").GetValue()
                hist.SetName(hist_name)
                hist.SetDirectory(0)
                dir_ptr.WriteTObject(hist,hist_name,"Overwrite")



outFile.Close()
executionTime = time.time() - startTime
print(f"\nExecution time: "f"{executionTime:.2f} s")