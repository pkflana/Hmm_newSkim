import ROOT
import sys
import os
import argparse
import time

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])

import analysis.utilities as utilities

# ============================================
# Headers
# ============================================

HEADERS = [
    "analysis/AnalysisTools.h"
]

for header in HEADERS:
    utilities.DeclareHeader(
        f"{os.environ['ANALYSIS_PATH']}/{header}"
    )

# ============================================
# Trigger weights
# ============================================

from histograms.defineTriggerWeights import AddTriggerWeightsAndErrors

# ============================================
# CLI
# ============================================

parser = argparse.ArgumentParser()

parser.add_argument(
    "--era",
    required=True,
    type=str
)

parser.add_argument(
    "--input-file",
    required=True,
    type=str
)

parser.add_argument(
    "--dataset-name",
    required=True,
    type=str
)

parser.add_argument(
    "--output-file",
    required=True,
    type=str
)

args = parser.parse_args()

startTime = time.time()

# ============================================
# Configs
# ============================================

cfg_dir = os.path.join(
    os.environ["ANALYSIS_PATH"],
    "config",
    args.era
)

main_cfg = utilities.get_config(
    os.path.join(cfg_dir, "maincfg.yaml")
)

dataset_cfg = utilities.get_config(
    os.path.join(cfg_dir, "samples.yaml")
)[args.dataset_name]

sel_cfg = utilities.get_config(
    os.path.join(cfg_dir, "selections.yaml")
)

weights_cfg = utilities.get_config(
    os.path.join(cfg_dir, "weights.yaml")
)

hist_cfg = utilities.get_config(
    os.path.join(
        os.environ["ANALYSIS_PATH"],
        "config",
        "plot",
        "histograms.yaml"
    )
)

# ============================================
# Selections
# ============================================

masses_regions = sel_cfg["masses_regions"]
categories = sel_cfg["categories"]

# masses_regions.keys()
masses_regions_list = ["Z_sideband","Signal_Fit"]
#  categories.keys()
categories_list = ["baseline","ggF","VBF"]

# ============================================
# RDF
# ============================================

rdf = ROOT.RDataFrame(
    "Events",
    args.input_file
)

# ============================================
# Additional variables
# ============================================

from histograms.add_vars import *

rdf = SelectedJetObservablesDef(rdf)
rdf = VBFJetObservablesDef(rdf)
rdf = VBFJetMuonsObservablesDef(rdf)
rdf = SoftJetCollectionCleaningInVBF(rdf)
rdf = GetAllMuonsObservablesNew(rdf)

# ============================================
# Trigger weights
# ============================================

rdf = AddTriggerWeightsAndErrors(
    rdf,
    WantErrors=True
)

# ============================================
# Define all weight columns
# ============================================

for weight_name, weight_info in weights_cfg["weights"].items():

    rdf = rdf.Define(
        f"weight__{weight_name}",
        weight_info["expression"]
    )

# ============================================
# Histograms
# ============================================

vars_to_make_hist = main_cfg["variables"]

from histograms.helpers import GetModel

outFile = ROOT.TFile(
    args.output_file,
    "RECREATE"
)

for mass_region, mass_info in masses_regions.items():
    if mass_region not in masses_regions_list: continue
    if not mass_info["store"]:
        continue

    for category, cat_info in categories.items():
        if category not in categories_list: continue
        if not cat_info["store"]:
            continue

        print(
            f"Processing: "
            f"{mass_region} / {category}"
        )

        rdf_sel = rdf.Filter(
            f"{mass_region} && {category}"
        )

        dir_ptr = utilities.mkdir_recursive(
            outFile,
            f"{mass_region}_{category}"
        )

        for var in vars_to_make_hist:

            model = GetModel(
                hist_cfg,
                var,
                dims=1
            )

            for weight_name in weights_cfg["weights"]:

                hist_name = (
                    var
                    if weight_name == "Central"
                    else f"{var}_{weight_name}"
                )

                hist = rdf_sel.Histo1D(
                    model,
                    var,
                    f"weight__{weight_name}"
                ).GetValue()

                hist.SetName(hist_name)
                hist.SetDirectory(0)

                dir_ptr.WriteTObject(
                    hist,
                    hist_name,
                    "Overwrite"
                )

outFile.Close()

executionTime = time.time() - startTime

print(
    f"Execution time: {executionTime:.2f} s"
)


# import ROOT
# import sys
# import os
# import argparse
# import time
# if __name__ == "__main__":
#     sys.path.append(os.environ["ANALYSIS_PATH"])
# import analysis.utilities as utilities

# HEADERS = [
#     "analysis/AnalysisTools.h"
# ]

# for header in HEADERS:
#     utilities.DeclareHeader(f"{os.environ['ANALYSIS_PATH']}/{header}")



# # --- CLI Arguments Parsing ---
# parser = argparse.ArgumentParser(description="Run the Hmumu skim.")
# parser.add_argument("--era", required=True, type=str, help="Main skim YAML.")
# parser.add_argument("--input-file", required=True, type=str, help="Input ROOT file.")
# parser.add_argument("--dataset-name", required=True, type=str, help="Dataset key.")
# parser.add_argument("--output-file", required=True, type=str, help="Output ROOT file.")
# # parser.add_argument("--var", required=True, type=str, help="Output ROOT file.")

# args = parser.parse_args()
# startTime = time.time()
# # --- Config Initialization ---
# main_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "maincfg.yaml"))
# dataset_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "samples.yaml"))[args.dataset_name]
# sel_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "selections.yaml"))
# hist_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", "plot","histograms.yaml"))

# masses_regions = sel_cfg["masses_regions"]
# categories = sel_cfg["categories"]

# rdf_initial = ROOT.RDataFrame("Events", args.input_file)
# from histograms.add_vars import *
# rdf_initial = SelectedJetObservablesDef(rdf_initial)
# rdf_initial = VBFJetObservablesDef(rdf_initial)
# rdf_initial = VBFJetMuonsObservablesDef(rdf_initial)
# rdf_initial = SoftJetCollectionCleaningInVBF(rdf_initial)
# rdf_initial = GetAllMuonsObservablesNew(rdf_initial)
# # print(rdf_initial.GetColumnNames())
# vars_to_make_hist = main_cfg["variables"]

# outFile = ROOT.TFile(args.output_file, "RECREATE")

# all_models = {}
# from histograms.helpers import GetModel

# # masses_regions.keys()
# masses_regions_list = ["Z_sideband","Signal_Fit"]
# #  categories.keys()
# categories_list = ["baseline","ggF","VBF"]


# for mass_region in masses_regions_list:
#     if not masses_regions[mass_region]["store"]: continue
#     for category in categories_list:
#         if not categories[category]["store"]: continue
#         rdf_cat_reg = rdf_initial.Filter(f"{mass_region} && {category}")
#         # print(f"Processing {mass_region} - {category}")
#         for var in vars_to_make_hist:
#             # print(f"Making histogram for {var}")
#             hist_cat_reg = rdf_cat_reg.Histo1D(GetModel(hist_cfg, var, dims=1), var).GetValue()
#             dir_ptr= utilities.mkdir_recursive(outFile, f"{mass_region}_{category}")
#             hist_cat_reg.SetDirectory(0)  # evita che ROOT lo chiuda prematuramente
#             dir_ptr.WriteTObject(hist_cat_reg, f"{var}", "UPDATE")
# outFile.Close()
# executionTime = time.time() - startTime
# print("Execution time in seconds: " + str(executionTime))