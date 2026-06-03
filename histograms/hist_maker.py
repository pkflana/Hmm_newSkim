#!/usr/bin/env python3

import ROOT
import sys
import os
import argparse
import time

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])

import common.utilities as utilities

HEADERS = ["analysis/AnalysisTools.h"]
for header in HEADERS:
    utilities.DeclareHeader(f"{os.environ['ANALYSIS_PATH']}/{header}")

from common.helpers import GetModel,GetRdfForDataset



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

masses_regions = sel_cfg["masses_regions"]
categories = sel_cfg["categories"]
masses_regions_list = ["Z_sideband"]#,"Signal_Fit","H_sideband"]
categories_list = ["baseline","ggF","VBF"]
vars_to_make_hist = main_cfg["variables"]

rdf_base =  GetRdfForDataset(args.input, is_data, syst_cfg['weights'], store_shifted_weights=False, treeName="Events")


systs_to_run = {
        "Central": syst_cfg["systematics"]["Central"]
    }
if args.systematics != 'central':
    syst_to_run = syst_cfg['systematics']
    syst_to_run.update(syst_cfg['weights'])

# up to here it is totally general for every kind of manipulation

outFile = ROOT.TFile(args.output_file,"RECREATE")

for syst_name, syst_info in systs_to_run.items():
    mu_suffix = syst_info["muon_suffix"]
    jet_suffix = syst_info["jet_suffix"]
    weight_name = syst_info["weight"]
    suffix_for_hist = syst_info["name"]

    rdf = rdf_base
    for mass_region, mass_info in masses_regions.items():
        if mass_region not in masses_regions_list: continue
        if not mass_info["store"]: continue
        for category, cat_info in categories.items():
            if category not in categories_list: continue
            if not cat_info["store"]: continue
            print(f"Processing: {mass_region} / {category}")
            dir_ptr = utilities.mkdir_recursive(outFile,f"{mass_region}_{category}")
            for var in vars_to_make_hist:
                model = GetModel(hist_cfg,var,dims=1)
                hist_name = var if syst_name == "Central" else f"{var}_{syst_name}"
                if rdf is not None:
                    hist = rdf.Filter(f"{mass_region} && {category}").Histo1D(model,var,weight_name).GetValue()
                else:
                    hist = ROOT.TH1D(hist_name,hist_name,model.fNbinsX,model.fXLow,model.fXUp)
                hist.SetName(hist_name)
                hist.SetDirectory(0)
                dir_ptr.WriteTObject(hist,hist_name,"Overwrite")

outFile.Close()
executionTime = time.time() - startTime
print(f"\nExecution time: {executionTime:.2f} s")

