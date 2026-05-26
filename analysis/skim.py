import os
import sys
import argparse
import fnmatch
import zlib
from pathlib import Path
import ROOT
import utilities

# Ensure local packages can be imported when running this script directly.
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

headers_dir = os.path.dirname(os.path.abspath(__file__))
header_path = os.path.join(headers_dir, "AnalysisTools.h")
ROOT.gInterpreter.Declare(f'#include "{header_path}"')



def _none_if_string(value):
    if value is None:
        return None
    if value.lower() in ["none", "null", ""]:
        return None
    return value


def _parse_args():
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
    return parser.parse_args()


def _column_name(column):
    if isinstance(column, (tuple, list)):
        return column[0]
    return column


def _add_existing_columns(columns, requested_columns, available_columns):
    for requested_column in requested_columns:
        column = _column_name(requested_column)
        if any(wildcard in column for wildcard in "*?["):
            matches = sorted(fnmatch.filter(available_columns, column))
        else:
            matches = [column] if column in available_columns else []

        for match in matches:
            if match not in columns:
                columns.append(match)


def _get_new_muon_cols(df):
    available_columns = {str(column) for column in df.GetColumnNames()}
    muon_patterns = [
        # "Muon_pt_noCorr*",
        # "Muon_pt_scale*",
        # "Muon_pt_ScaRe*",
        # "Muon_pt_resol*",
        # "good_muons*",
        # "good_muon_idx*",
        # "sorted_good_muon_idx*",
        "mu1_idx*",
        "mu2_idx*",
        "mu1_pt*",
        "mu2_pt*",
        "mu1_eta*",
        "mu2_eta*",
        "mu1_phi*",
        "mu2_phi*",
        "mu1_mass*",
        "mu2_mass*",
        "mu1_charge*",
        "mu2_charge*",
        "mu1_bsConstrainedChi2*",
        "mu2_bsConstrainedChi2*",
        "mu1_dxy*",
        "mu2_dxy*",
        "mu1_dz*",
        "mu2_dz*",
        "mu1_pfIsoId*",
        "mu2_pfIsoId*",
        "mu1_mediumId*",
        "mu2_mediumId*",
        # "mu1_p4*",
        # "mu2_p4*",
        "m_mumu*",
        "pt_mumu*",
        "eta_mumu*",
        "phi_mumu*",
        "y_mumu*",
        "dR_mumu*",
    ]

    muon_cols = []
    _add_existing_columns(muon_cols, muon_patterns, available_columns)
    return muon_cols



# 1. open dataframe and apply selection
args = _parse_args()
config_file = args.config_file
input_file = args.input_file
dataset_name = args.dataset_name
output_file = args.output_file

# input_file = "root://cms-xrd-global.cern.ch//store/data/Run2024F/Muon1/NANOAOD/MINIv6NANOv15-v1/2530000/8fb5af30-f050-4468-a224-c9527356dc4d.root"
# dataset_name = "Muon1_Run2024F"

config = utilities.get_config(config_file)

period = config["era"]
lumi = config["luminosity"]

dataset_cfg = utilities.get_config(config["samplesFile"])[dataset_name]
xs_cfg = utilities.get_config(config["crossSectionsFile"])
is_data = dataset_cfg.get("is_data", False)
is_signal = dataset_cfg.get("is_signal", False)

trigger_config = utilities.get_config(config.get("triggerFile"))

root_file = ROOT.TFile.Open(input_file)
tree = root_file.Get("Events")
df = ROOT.RDataFrame(tree)


# 1. add corrections
from corrections.general import define_base_weights,apply_corrections
if "MET_flags" in config:
    from analysis.other import applyMETFlags
    df = applyMETFlags(df, config, is_data)

is_data_str = "true" if is_data else "false"
df = df.Define(f"is_data", is_data_str)
df = df.Define("period", f"static_cast<int>(Period::{period})")
is_data_int = "1" if is_data else "0"
df = df.Define(f"is_data_int", is_data_int)
# print(f"before there were {df.Count().GetValue()} entries")
df,base_weights_to_store = define_base_weights(df,config,dataset_name,xs_cfg)
df = apply_corrections(df, config, dataset_cfg, dataset_name)

### now define the muon selection and dimuon observables
from analysis.muons import ApplyMuonSelection

df = ApplyMuonSelection(df, is_data, want_variations=True, dimuon_mass_cut=50.0)


from corrections.jetVetoMap import ApplyJetVetoMap
df = ApplyJetVetoMap(df, config, apply_filter=False, defineElectronCleaning=False, isV12=False)

fullEventIdColumn = "FullEventId"
dataset_name_crc = zlib.crc32(dataset_name.encode()) & 0xFFFF
input_file_crc = zlib.crc32(input_file.encode()) & 0xFFFF

df = df.Define(
    fullEventIdColumn,
    f"""eventId::encodeFullEventId({dataset_name_crc}, {input_file_crc}, rdfentry_)""",
)

nano_version = config.get("nano_version", "v15")
available_columns = {str(column) for column in df.GetColumnNames()}

default_col_to_store = utilities.GetObservablesCols(
    "default",
    is_data,
    nano_version,
)
jet_cols = utilities.GetObservablesCols(
    "Jet",
    is_data,
    nano_version,
)
muon_cols = utilities.GetObservablesCols(
    "Muon",
    is_data,
    nano_version,
)
muon_cols.extend(_get_new_muon_cols(df))

LHE_weight_cols = utilities.GetObservablesCols(
    "LHEWeight", is_data, nano_version
)
SoftActivityJet_cols = utilities.GetObservablesCols(
    "SoftActivityJet", is_data, nano_version
)
FsrPhoton_cols = utilities.GetObservablesCols(
    "FsrPhoton", is_data, nano_version
)

# if not is_data

vars_to_save_list = []
_add_existing_columns(
    vars_to_save_list,
    default_col_to_store + jet_cols + muon_cols + base_weights_to_store,
    available_columns,
)
vars_to_save = utilities.ListToVector(vars_to_save_list)

if output_file:
    df.Snapshot("Events", output_file, vars_to_save)

# # 3. HLT matching def
# gen_weight_name = "weight_gen"

# if not isData:
#     for data_frame in [df, df_not_selected]:
#         if data_frame is None:
#             continue
#         genWeight_def = (
#             "std::copysign<float>(1.f, genWeight)"
#             if use_genWeight_sign_only
#             else "genWeight"
#         )
#         data_frame = data_frame.Define(gen_weight_name, genWeight_def)
#         if "pu" in corrections.to_apply:
#             data_frame = corrections.pu.getWeight(data_frame)
#         updateDenomEntry(data_frame)
# # if isData: json_dict_for_cache['RunLumi'] = unique_run_lumi

# if isData and "lumiFile" in config:
# applyTriggerFilter = dataset_cfg.get("applyTriggerFilter", True)



# # df = df.Define("isData", is_data)
# # df = Baseline.CreateRecoP4(df, nano_version=config["nano_version"])
# # df = Baseline.DefineGenObjects(df, isData=isData, isHH=isHH)

# # if isData:
# #     syst_dict = {"nano": "Central"}
# #     ana_reco_objects = Baseline.ana_reco_object_collections[
# #         config["nano_version"]
# #     ]
# #     df, syst_dict = corrections.applyScaleUncertainties(df, ana_reco_objects)
# # else:
# #     ana_reco_objects = Baseline.ana_reco_object_collections[
# #         config["nano_version"]
# #     ]
# #     df, syst_dict = corrections.applyScaleUncertainties(df, ana_reco_objects)
# # df_empty = df

# # outfile_prefix = inFile.split("/")[-1]
# # outfile_prefix = outfile_prefix.split(".")[0]
# # outFileName = os.path.join(outDir, f"{outfile_prefix}_reference.root")
# # report["reference_file"] = outFileName
# # treeName = "Events"
# # report["tree_name"] = treeName
# # report["full_event_id_column"] = fullEventIdColumn
# # outfilesNames = [outFileName]
# # handles_to_run.append(
# #     df.Snapshot(treeName, outFileName, [fullEventIdColumn], snapshotOptions)
# # )
# # selection_reports = [df.Report()]

# # print(f"syst_dict={syst_dict}")
# # for syst_name, (unc_source, unc_scale) in syst_dict.items():
# #     if unc_source not in uncertainties and "all" not in uncertainties:
# #         continue
# #     is_central = syst_name in ["Central", "nano"]
# #     if not is_central and not compute_unc_variations:
# #         continue
# #     suffix = "" if is_central else f"_{syst_name}"
# #     if len(suffix) and not store_noncentral:
# #         continue
# #     columns_to_save = anaTupleDef.getDefaultColumnsToSave(isData)
# #     dfw = Utilities.DataFrameWrapper(df_empty, columns_to_save)
# #     dfw.Apply(
# #         Baseline.SelectRecoP4,
# #         syst_name,
# #         config["nano_version"],
# #         config["met_type"],
# #     )
# #     # https://twiki.cern.ch/twiki/bin/view/CMS/MissingETOptionalFilters#Analysis_Recommendations_for_any
# #     if "MET_flags" in config:
# #         dfw.Apply(
# #             Baseline.applyMETFlags,
# #             config["MET_flags"],
# #             config.get("badMET_flag_runs", []),
# #             isData,
# #         )

# #     anaTupleDef.addAllVariables(
# #         dfw,
# #         syst_name,
# #         isData,
# #         trigger_class,
# #         lepton_legs,
# #         isSignal,
# #         applyTriggerFilter,
# #         config,
# #         channels,
# #         dataset_cfg,
# #     )

# #     if not isData:
# #         triggers_to_use = set()
# #         for channel in channels:
# #             trigger_list = config.get("triggers", {}).get(channel, [])
# #             for trigger in trigger_list:
# #                 if trigger not in trigger_class.trigger_dict.keys():
# #                     raise RuntimeError(
# #                         f"Trigger does not exist in triggers.yaml, {trigger}"
# #                     )
# #                 triggers_to_use.add(trigger)

# #         weight_branches = dfw.Apply(
# #             corrections.getNormalisationCorrections,
# #             lepton_legs=lepton_legs,
# #             offline_legs=offline_legs,
# #             trigger_names=triggers_to_use,
# #             unc_source=unc_source,
# #             unc_scale=unc_scale,
# #             ana_caches=None,
# #             return_variations=is_central and compute_unc_variations,
# #             use_genWeight_sign_only=use_genWeight_sign_only,
# #         )
# #         dfw.colToSave.extend(weight_branches)

# #     # Analysis anaTupleDef should define a legType as a leg obj
# #     # But to save with RDF, it needs to be converted to an int
# #     for leg_name in lepton_legs:
# #         branch_name = f"{leg_name}_legType"
# #         if branch_name in dfw.colToSave:
# #             dfw.Redefine(branch_name, f"static_cast<int>({branch_name})")
# #     varToSave = Utilities.ListToVector(dfw.colToSave)
# #     outfile_prefix = inFile.split("/")[-1]
# #     outfile_prefix = outfile_prefix.split(".")[0]
# #     outFileName = os.path.join(outDir, f"{outfile_prefix}{suffix}.root")
# #     outfilesNames.append(outFileName)
# #     report["output_files"].append(
# #         {
# #             "unc_source": unc_source,
# #             "unc_scale": unc_scale,
# #             "file_name": outFileName,
# #         }
# #     )
# #     selection_reports.append(dfw.df.Report())
# #     handles_to_run.append(
# #         dfw.df.Snapshot(treeName, outFileName, varToSave, snapshotOptions)
# #     )

# # ROOT.RDF.RunGraphs(handles_to_run)

# # runLumiRanges_cpp = runLumiTracker.getRunLumiRanges()
# # runLumiRanges = {}
# # for run, lumi_ranges in runLumiRanges_cpp:
# #     run_str = str(run)
# #     if run_str not in runLumiRanges:
# #         runLumiRanges[run_str] = []
# #     for lumi_range in lumi_ranges:
# #         runLumiRanges[run_str].append([lumi_range.first, lumi_range.second])

# # report["run_lumi_ranges"] = runLumiRanges

# # for shape_unc_source in shape_sources:
# #     for shape_unc_scale in getScales(shape_unc_source):
# #         for p_name, p_instance in processor_instances.items():
# #             report["denominator"][shape_unc_source][shape_unc_scale][p_name] = (
# #                 p_instance.onAnaCache_materializeDenomEntry(
# #                     report["denominator"][shape_unc_source][shape_unc_scale][p_name]
# #                 )
# #             )
# #             report["denominator"][shape_unc_source][shape_unc_scale][p_name] = (
# #                 p_instance.onAnaCache_finalizeDenomEntry(
# #                     report["denominator"][shape_unc_source][shape_unc_scale][p_name]
# #                 )
# #             )

# # hist_time = ROOT.TH1D(f"time", f"time", 1, 0, 1)
# # end_time = datetime.datetime.now()
# # hist_time.SetBinContent(1, (end_time - start_time).total_seconds())
# # for index, fileName in enumerate(outfilesNames):
# #     outputRootFile = ROOT.TFile(fileName, "UPDATE", "", compression_settings)
# #     rep = ReportTools.SaveReport(
# #         selection_reports[index].GetValue(), reportName=f"Report"
# #     )
# #     outputRootFile.WriteTObject(rep, f"Report", "Overwrite")
# #     if index == 0:
# #         outputRootFile.WriteTObject(hist_time, f"runtime", "Overwrite")
# #     outputRootFile.Close()
# #     # if print_cutflow:
# #     #     report.Print()

# # if reportOutput is not None:
# #     with open(reportOutput, "w") as f:
# #         json.dump(report, f)
# # # 2.
