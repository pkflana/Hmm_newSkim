import os
import sys
import argparse
import zlib
from pathlib import Path
import ROOT
import utilities

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])

# --- ROOT Environment Configuration ---
headers_dir = os.path.dirname(os.path.abspath(__file__))
ROOT.gInterpreter.Declare(f'#include "{os.path.join(headers_dir, "AnalysisTools.h")}"')

# --- CLI Arguments Parsing ---
parser = argparse.ArgumentParser(description="Run the Hmumu skim.")
parser.add_argument("--era", required=True, type=str, help="Main skim YAML.")
parser.add_argument("--input-file", required=True, type=str, help="Input ROOT file.")
parser.add_argument("--dataset-name", required=True, type=str, help="Dataset key.")
parser.add_argument("--output-file", required=True, type=str, help="Output ROOT file.")
args = parser.parse_args()

# --- Config Initialization ---
config = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "maincfg.yaml"))
dataset_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "samples.yaml"))[args.dataset_name]
sel_config = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "selections.yaml"))
trigger_config = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "triggers.yaml"))
xs_cfg = utilities.get_config(config["crossSectionsFile"])

# Setup parameters
nano_version = config.get("nano_version", "v15")
is_data = dataset_cfg.get("is_data", False)
is_signal = dataset_cfg.get("is_signal", False)
want_variations = config.get("want_variations", False)
only_default = config.get("only_default", True)

cols_to_save = []

# --- Dataframe Instantiation ---
root_file = ROOT.TFile.Open(args.input_file)
df = ROOT.RDataFrame(root_file.Get("Events"))

# 🚀 ACTIVATE PROGRESS BAR (Will update dynamically during Snapshot)
ROOT.RDF.Experimental.AddProgressBar(df)

# --- Base Metadata & Event Filters ---
if "MET_flags" in config:
    from analysis.other import applyMETFlags
    df = applyMETFlags(df, config, is_data)

df = df.Define("period", f"static_cast<int>(Period::{config['era']})")
df = df.Define("is_data", "true" if is_data else "false")
df = df.Define("is_data_int", "1" if is_data else "0")
df = df.Define("is_signal", "true" if is_signal else "false")

# Event ID Encoding
dataset_crc = zlib.crc32(args.dataset_name.encode()) & 0xFFFF
input_crc = zlib.crc32(args.input_file.encode()) & 0xFFFF
df = df.Define("FullEventId", f"eventId::encodeFullEventId({dataset_crc}, {input_crc}, rdfentry_)")

cols_to_save.extend(utilities.GetObservablesCols("default", is_data, nano_version))

# --- Weights & Corrections Block ---
from corrections.general import define_base_weights, apply_corrections
df, base_weights = define_base_weights(df, config, args.dataset_name, xs_cfg)
cols_to_save.extend(base_weights)

df, weight_branches = apply_corrections(df, config, dataset_cfg, args.dataset_name)
if weight_branches:
    cols_to_save.extend(weight_branches)

# --- Muon & Lepton Processing Selection Chain ---
from analysis.muons import (
    DefineMuonPtAndP4, ApplyMuonTriggerMatching, ProcessMuonVariables,
    ApplyElectronVeto, DefineMuonSelection, ProcessExtraMuonVariables
)

df = DefineMuonPtAndP4(df, is_data, only_default=only_default, want_variations=want_variations)

df, trigger_event_cols = ApplyMuonTriggerMatching(df, trigger_config, apply_filter=config.get("apply_trg_filter", True))
cols_to_save.extend(trigger_event_cols)

muon_cols_initial = utilities.GetObservablesCols("Muon", is_data, nano_version)
df, new_muon_cols = ProcessMuonVariables(
    df=df, is_data=is_data, default_suffix=sel_config.get("default_suffix", ""),
    muon_columns=muon_cols_initial, trigger_config=trigger_config,
    only_default=only_default, want_variations=want_variations,
    pt_min=config.get("muon_pt_min", 15.0), mass_cut=config.get("dimuon_mass_min", 50.0)
)
cols_to_save.extend(new_muon_cols)

df = ApplyElectronVeto(df)

# # Muon SF Weights evaluation
from corrections.mu import apply_muIDIso_weights
df, mu_weights = apply_muIDIso_weights(df, config, return_variations=want_variations)
valid_mu_weights = [w for w in config.get("mu_weights_to_store", mu_weights) if w in mu_weights]
cols_to_save.extend(valid_mu_weights)

df, extra_lep_cols = ProcessExtraMuonVariables(
    df, is_data, muon_cols_initial, sel_config.get("default_suffix", ""),
    trigger_config, only_default, want_variations, pt_min=config.get("muon_pt_min", 15.0)
)
cols_to_save.extend(extra_lep_cols)

df, muon_selection_cols = DefineMuonSelection(df, sel_config, only_default, is_data, want_variations=False)
cols_to_save.extend(muon_selection_cols)

# --- Jet & Miscellaneous Global Columns ---
from corrections.jetVetoMap import ApplyJetVetoMap
df, jet_veto_map_cols = ApplyJetVetoMap(df, config, apply_filter=False, defineElectronCleaning=False, isV12=(nano_version == "v12"))
cols_to_save.extend(jet_veto_map_cols)

from analysis.jets import ProcessAllJetVariables

# Load additional background/signal collections
from corrections.btag_wpValues import getBTagWPValues
bTagWPDict = getBTagWPValues(config)
jet_cols_initial = utilities.GetObservablesCols("Jet", is_data, nano_version)
df, jet_columns_to_store = ProcessAllJetVariables(df, is_data, jet_cols_initial, config=sel_config, bTagAlgo=config.get("bTagAlgo","particleNet"), bTagDict=bTagWPDict, want_variations=want_variations, mu_suff="")
cols_to_save.extend(jet_columns_to_store)

from analysis.other import DefineCategoryBooleans
df, cat_vars = DefineCategoryBooleans(df, sel_config, is_data, want_variations)
cols_to_save.extend(cat_vars)

for collection in ["LHEWeight", "SoftActivityJet"]:
    cols_to_save.extend(utilities.GetObservablesCols(collection, is_data, nano_version))

# # Ensure uniqueness of columns
cols_to_save = list(set(cols_to_save))

# --- Snapshot Execution & Cutflow reporting ---
# The progress bar will output to standard error here while the entries loop runs
df.Snapshot("Events", args.output_file, utilities.ListToVector(cols_to_save))

# Write Cutflow Report Object back into the file
out_tfile = ROOT.TFile.Open(args.output_file, "UPDATE")
hist_rep = utilities.SaveReport(df.Report().GetValue(), reportName="Report", verbose=0)
out_tfile.WriteTObject(hist_rep, "Report", "Overwrite")
out_tfile.Close()
