import os
import sys
import argparse
import zlib
from pathlib import Path
import ROOT
import json

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])

headers_dir = os.path.dirname(os.path.abspath(__file__))
ROOT.gInterpreter.Declare(
    f'#include "{os.path.join(headers_dir, "AnalysisTools.h")}"'
)
import common.utilities as utilities

parser = argparse.ArgumentParser(description="Run the Hmumu skim.")
parser.add_argument("--era", required=True)
parser.add_argument("--input-file", required=True)
parser.add_argument("--dataset-name", required=True)
parser.add_argument("--output-file", required=True)
parser.add_argument("--want-variations", required=False, action="store_true", help="request for variations from command line")
parser.add_argument(
    "--jerc-2025-mc-mode",
    choices=["2025", "jec2024_jer2025", "2024"],
    default=None,
    help=(
        "JEC/JER payload mode for Run3_2025 MC: 2025, "
        "jec2024_jer2025, or 2024. Overrides config jerc_2025_mc_mode."
    ),
)
parser.add_argument(
    "--use-2024-jerc-for-2025-mc",
    action=argparse.BooleanOptionalAction,
    default=None,
    help="Deprecated alias for --jerc-2025-mc-mode jec2024_jer2025.",
)
args = parser.parse_args()

## all configurations to load ##
config = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "maincfg.yaml"))
if args.use_2024_jerc_for_2025_mc:
    if (
        args.jerc_2025_mc_mode is not None
        and args.jerc_2025_mc_mode != "jec2024_jer2025"
    ):
        parser.error(
            "--use-2024-jerc-for-2025-mc conflicts with "
            f"--jerc-2025-mc-mode {args.jerc_2025_mc_mode}"
        )
    args.jerc_2025_mc_mode = "jec2024_jer2025"
if args.jerc_2025_mc_mode is not None:
    config["jerc_2025_mc_mode"] = args.jerc_2025_mc_mode
dataset_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "samples.yaml"))[args.dataset_name]
sel_config = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "selections.yaml"))
trigger_config = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "triggers.yaml"))
process_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "process_names.yaml"))
systematics_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era, "systematics.yaml"))
xs_cfg = utilities.get_config(config["crossSectionsFile"])

## some utilities definitions ##
nano_version = config.get("nano_version", "v15")
is_data = dataset_cfg.get("is_data", False)
is_signal = dataset_cfg.get("is_signal", False)
process = utilities.process_from_dataset(process_cfg, args.dataset_name) if not is_data else None

want_variations = (config.get("want_variations", False) or args.want_variations) and not is_data
only_default = sel_config.get("only_default", True)
muon_pt_default_suffix = sel_config.get("muon_pt_default_suffix", "")

# columns to save #
cols_to_save = []
# open root file #
root_file = ROOT.TFile.Open(args.input_file)
df = ROOT.RDataFrame(root_file.Get("Events"))
ROOT.RDF.Experimental.AddProgressBar(df)

# useful definitions #
df = df.Define("period", f"static_cast<int>(Period::{config['era']})")
df = df.Define("is_data", "true" if is_data else "false")
df = df.Define("is_data_int", "1" if is_data else "0")
df = df.Define("is_signal", "true" if is_signal else "false")
dataset_crc = zlib.crc32(args.dataset_name.encode()) & 0xFFFF
input_crc = zlib.crc32(args.input_file.encode()) & 0xFFFF
df = df.Define("FullEventId",f"eventId::encodeFullEventId({dataset_crc}, {input_crc}, rdfentry_)")
# default columns to store: #
cols_to_save.extend(utilities.GetObservablesCols("default", is_data, nano_version))

if not is_data:
    from analysis.mc_splitting import ApplyOrthogonalLumiFilter
    df, ortho_cols = ApplyOrthogonalLumiFilter(
        df,
        args.era,
        seed=12345,
        keep_tag_column=True
    )

    cols_to_save.extend(ortho_cols)

    from common.gen_vbf_filter import ApplyGenVBFFilter
    df,cols_to_save = ApplyGenVBFFilter(df,cols_to_save, args.era, args.dataset_name, process)



# define weights #
if not is_data:
    from corrections.general import define_base_weights
    xs_entry = dataset_cfg.get("crossSection", args.dataset_name)
    process_entry = process_cfg[process]
    df,base_weights,json_dict_to_store = define_base_weights(df, config.get("luminosity", ""), xs_entry, xs_cfg,config,dataset_cfg, process_entry,want_variations,systematics_cfg)
    cols_to_save.extend(base_weights)
else:
    from corrections.general import apply_golden_json
    df = apply_golden_json(df, config["lumiFile"])

# apply corrections --> this time also for data (e.g. JEC/ScaRe) #
from corrections.general import apply_corrections
df = apply_corrections(df, config, dataset_cfg, args.dataset_name, want_variations)

# MET FLAGS
if "MET_flags" in config:
    from analysis.other import applyMETFlags
    df = applyMETFlags(df, config, is_data)

## muon definitions ##
from analysis.muons import DefineMuonPtAndP4,ProcessMuonVariables,ApplyMuonTriggerMatching,ProcessExtraMuonVariables,ApplyElectronVeto,DefineMuonSelection
# definitions of p4
df = DefineMuonPtAndP4(df,only_default,want_variations)
# trigger application && matching
df, trigger_cols = ApplyMuonTriggerMatching(df, trigger_config, sel_config.get("apply_trg_filter", True))
cols_to_save.extend(trigger_cols)
# dimuon system definitions
muon_cols_initial = utilities.GetObservablesCols("Muon", is_data, nano_version)
df, new_muon_cols =  ProcessMuonVariables(df,muon_cols_initial,muon_pt_default_suffix,trigger_config,only_default,want_variations,sel_config.get("muon_pt_min", 15.0),sel_config.get("dimuon_mass_min", 50.0),sel_config.get("dimuon_mass_max", 200.0),systematics_cfg)
cols_to_save.extend(new_muon_cols)
# electron veto
df = ApplyElectronVeto(df)
# # muon id/iso weights definitions
if not is_data:
    from corrections.mu import apply_muIDIso_weights
    df, mu_weights = apply_muIDIso_weights(df, config, want_variations)
    cols_to_save.extend(mu_weights)
# # extra lepton inclusion
df, extra_lep_cols = ProcessExtraMuonVariables(df,muon_cols_initial,muon_pt_default_suffix,trigger_config,only_default,want_variations,sel_config.get("muon_pt_min", 15.0))
cols_to_save.extend(extra_lep_cols)
# # muon selection
df,vars_sel = DefineMuonSelection(df,sel_config,only_default,want_variations,systematics_cfg)
cols_to_save.extend(vars_sel)

# ## jet definitions ##
from analysis.jets import ProcessAllJetVariables, SelectJetVars
from corrections.btag_wpValues import getBTagWPValues
# define all varied variables for jets
bTagWPDict = getBTagWPValues(config)
jet_cols_initial = utilities.GetObservablesCols("Jet", is_data, nano_version)
df, jet_cols = ProcessAllJetVariables(df,is_data,jet_cols_initial,sel_config,config.get("bTagAlgo", "PNet"),bTagWPDict,want_variations,systematics_cfg)
cols_to_save.extend(jet_cols)
# apply jet veto map
from corrections.jetVetoMap import ApplyJetVetoMap
df, jet_veto_map_cols = ApplyJetVetoMap(df, config, muon_pt_default_suffix, False, sel_config.get("define_electron_cleaning", False),(nano_version == "v12"), want_variations,systematics_cfg)
cols_to_save.extend(jet_veto_map_cols)
# define selected jet vars
df, selected_jet_cols = SelectJetVars(df,is_data,jet_cols_initial,sel_config,config.get("bTagAlgo", "PNet"),bTagWPDict,want_variations,systematics_cfg)
cols_to_save.extend(selected_jet_cols)

# Final analysis categories, including their shifted versions, are intentionally
# defined at histogram level by DefineHistogramSelections.  The skim stores only
# the nominal/shifted object and selection columns needed to build them.

## additional col to store ##
collections = ["SoftActivityJet"]
if not is_data:
    # Store the complete small-R GenJet collection and a stable per-event index.
    # The flavour and hadron-count branches are useful for reco/gen matching and
    # jet-composition studies; retain only branches available in the input NanoAOD.
    input_columns = {str(column) for column in df.GetColumnNames()}
    genjet_columns = [
        "GenJet_pt",
        "GenJet_eta",
        "GenJet_phi",
        "GenJet_mass",
        "GenJet_partonFlavour",
        "GenJet_hadronFlavour",
        "GenJet_nBHadrons",
        "GenJet_nCHadrons",
    ]
    cols_to_save.extend(
        column for column in genjet_columns if column in input_columns
    )
    if "GenJet_pt" in input_columns:
        df = df.Define("GenJet_idx", "CreateIndexes(GenJet_pt.size())")
        cols_to_save.append("GenJet_idx")

    # Keep the raw reco-to-gen association explicitly.  SelectJetVars also
    # stores SelectedJet_genJetIdx for the nominal and every JER/JES selection.
    if "Jet_genJetIdx" in input_columns:
        cols_to_save.append("Jet_genJetIdx")

    if "LHE_Vpt" in df.GetColumnNames():
        collections.append("LHE")
    if "LHEScaleWeight" in df.GetColumnNames():
        collections.append("LHEWeight")

for c in collections:
    cols_to_save.extend(utilities.GetObservablesCols(c, is_data, nano_version))
cols_to_save = list(set(cols_to_save))

## snapshot + report store ##
df.Snapshot("Events",args.output_file,utilities.ListToVector(cols_to_save))
df, report_json = utilities.SaveReport(df, df.Report().GetValue(), verbose=0)
if not is_data:
    for pu_key,pu_dict in json_dict_to_store.items():
        for xs_key,xs_dict in pu_dict.items():
            value_to_extract = xs_dict['value']
            xs_dict['value']=value_to_extract.GetValue()
            if 'value_unsigned' in xs_dict.keys():
                xs_dict['value_unsigned']=xs_dict['value_unsigned'].GetValue()
    report_json.update(json_dict_to_store)

json_file = os.path.splitext(args.output_file)[0] + "_report.json"
with open(json_file, "w") as f:
    json.dump(report_json, f, indent=4)
out_tfile = ROOT.TFile.Open(args.output_file, "UPDATE")
out_tfile.Close()
