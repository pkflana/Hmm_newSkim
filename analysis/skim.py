import os
import sys
import argparse
import fnmatch
import zlib
from pathlib import Path
import ROOT
import utilities

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])

headers_dir = os.path.dirname(os.path.abspath(__file__))
header_path = os.path.join(headers_dir, "AnalysisTools.h")
ROOT.gInterpreter.Declare(f'#include "{header_path}"')

parser = argparse.ArgumentParser(description="Run the Hmumu skim.")
parser.add_argument(
    "--config-file",
    required=True,
    type=str,
    help="Path to the main skim configuration YAML.",
)
parser.add_argument(
    "--input-file",
    required=True,
    type=str,
    help="Input ROOT file or XRootD URI.",
)
parser.add_argument(
    "--dataset-name",
    required=True,
    type=str,
    help="Dataset key in the samples YAML.",
)
parser.add_argument(
    "--output-file",
    required=True,
    type=str,
    help='Output ROOT file.',
)
args = parser.parse_args()

config_file = args.config_file
input_file = args.input_file
dataset_name = args.dataset_name
output_file = args.output_file

config = utilities.get_config(config_file)
dataset_cfg = utilities.get_config(config["samplesFile"])[dataset_name]
sel_config = utilities.get_config(config["sel_file"])
xs_cfg = utilities.get_config(config["crossSectionsFile"])
trigger_config = utilities.get_config(config.get("triggerFile"))

cols_to_save = []

period = config["era"]
lumi = config["luminosity"]
nano_version = config.get("nano_version", "v15")
is_data = dataset_cfg.get("is_data", False)
is_signal = dataset_cfg.get("is_signal", False)

root_file = ROOT.TFile.Open(input_file)
tree = root_file.Get("Events")
df = ROOT.RDataFrame(tree)


if "MET_flags" in config:
    from analysis.other import applyMETFlags
    df = applyMETFlags(df, config, is_data)

df = df.Define("period", f"static_cast<int>(Period::{period})")
is_data_str = "true" if is_data else "false"
df = df.Define(f"is_data", is_data_str)
is_data_int = "1" if is_data else "0"
df = df.Define(f"is_data_int", is_data_int)

is_signal_str = "true" if is_signal else "false"
df = df.Define(f"is_signal", is_signal_str)

dataset_name_crc = zlib.crc32(dataset_name.encode()) & 0xFFFF
input_file_crc = zlib.crc32(input_file.encode()) & 0xFFFF
df = df.Define(
    fullEventIdColumn := "FullEventId",
    f"eventId::encodeFullEventId({dataset_name_crc}, {input_file_crc}, rdfentry_)",
)

default_col_to_store = utilities.GetObservablesCols("default", is_data, nano_version)
cols_to_save.extend(default_col_to_store)

from corrections.general import define_base_weights, apply_corrections
df, base_weights_to_store = define_base_weights(df, config, dataset_name, xs_cfg)
cols_to_save.extend(base_weights_to_store)

df, pu_branches = apply_corrections(df, config, dataset_cfg, dataset_name)
if pu_branches:
    cols_to_save.extend(pu_branches)

from analysis.muons import DefineMuonPtAndP4, ApplyMuonTriggerMatching, ProcessMuonVariables, ApplyElectronVeto,DefineMuonSelection,ProcessExtraMuonVariables
only_default = config.get("only_default", True)
want_variations = config.get("want_variations", False)
pt_cut = config.get("muon_pt_min", 15.0)
m_cut = config.get("dimuon_mass_min", 50.0)
apply_trg_filter = config.get("apply_trg_filter", True)
default_suffix = sel_config.get("default_suffix", "")
df = DefineMuonPtAndP4(df, is_data, only_default=only_default, want_variations=want_variations)
df, trigger_event_cols = ApplyMuonTriggerMatching(df, trigger_config, apply_filter=apply_trg_filter)
cols_to_save.extend(trigger_event_cols)
muon_cols_initial = utilities.GetObservablesCols("Muon", is_data, nano_version)
df, new_muon_cols = ProcessMuonVariables(
    df=df,
    is_data=is_data,
    default_suffix=default_suffix,
    muon_columns=muon_cols_initial,
    trigger_config=trigger_config,
    only_default=only_default,
    want_variations=want_variations,
    pt_min=pt_cut,
    mass_cut=m_cut
)
cols_to_save.extend(new_muon_cols)

df = ApplyElectronVeto(df)


df,extra_lep_cols = ProcessExtraMuonVariables(df, is_data, muon_cols_initial, default_suffix, trigger_config, only_default, want_variations, pt_min=pt_cut)

df,muon_selection_cols=DefineMuonSelection(df,sel_config, only_default, is_data, want_variations=False)
cols_to_save.extend(muon_selection_cols)

from corrections.jetVetoMap import ApplyJetVetoMap
df,jet_veto_map_cols = ApplyJetVetoMap(df, config, apply_filter=False, defineElectronCleaning=False, isV12=nano_version=="v12")
cols_to_save.extend(jet_veto_map_cols)

from corrections.btag_wpValues import getBTagWPValues
bTagWPDict = getBTagWPValues(config)

jet_cols = utilities.GetObservablesCols(
    "Jet",
    is_data,
    nano_version,
)
cols_to_save.extend(jet_cols)

LHE_weight_cols = utilities.GetObservablesCols(
    "LHEWeight", is_data, nano_version
)
cols_to_save.extend(LHE_weight_cols)
SoftActivityJet_cols = utilities.GetObservablesCols(
    "SoftActivityJet", is_data, nano_version
)
cols_to_save.extend(SoftActivityJet_cols)
FsrPhoton_cols = utilities.GetObservablesCols(
    "FsrPhoton", is_data, nano_version
)
cols_to_save.extend(FsrPhoton_cols)
cols_to_save= list(set(cols_to_save))
# print("Columns configured to be saved:")
# print(cols_to_save)

df.Snapshot("Events", output_file, utilities.ListToVector(cols_to_save))
output_file = ROOT.TFile.Open(output_file, "UPDATE")
cutflow_report = df.Report()
hist_rep = utilities.SaveReport(cutflow_report.GetValue(), reportName="Report",verbose=0)
output_file.WriteTObject(hist_rep, f"Report", "Overwrite")
output_file.Close()