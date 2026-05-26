import os
import sys
from pathlib import Path
import ROOT
import utilities

# Ensure local packages can be imported when running this script directly.
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

# 1. open dataframe and apply selection

config_file = "/afs/cern.ch/work/v/vdamante/Hmm_newSkim/config/maincfg_2024.yaml"
input_file = "root://cms-xrd-global.cern.ch//store/mc/RunIII2024Summer24NanoAODv15/VBFH-Hto2Mu_Par-M-125_TuneCP5_13p6TeV_powheg-pythia8/NANOAODSIM/150X_mcRun3_2024_realistic_v2-v2/100000/f05fbcb1-50b6-4d4e-9923-19678675ee4a.root"
dataset_name = "VBFHto2Mu_M125_powheg"
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
is_data_int = "1" if is_data else "0"
df = df.Define(f"is_data_int", is_data_int)
# print(f"before there were {df.Count().GetValue()} entries")
df = define_base_weights(df,config,dataset_name,xs_cfg)
df = apply_corrections(df, config, dataset_cfg, dataset_name)

### now define the muon selection

ROOT.gInterpreter.ProcessLine("""
                    using RVecF = ROOT::VecOps::RVec<float>;
                    RVecF Muon_pt_sel(const RVecF& Muon_nano_pt, const RVecF& Muon_bsc_pt, const RVecF& Muon_bsc_chi2){{
                        RVecF Muon_pt_sel(Muon_nano_pt.size());
                        for(size_t muon_idx = 0 ; muon_idx < Muon_pt_sel.size(); muon_idx++){{
                            Muon_pt_sel[muon_idx] = Muon_bsc_chi2[muon_idx] < 30 ? Muon_bsc_pt[muon_idx] : Muon_nano_pt[muon_idx];
                        }}
                        return Muon_pt_sel;
                    }}
                    """)

muon_sel_dict = {
    "Muon_pt_noCorr": ['Muon_pt', 'Muon_bsConstrainedPt'],
    "Muon_pt_scale": ['Muon_pt_scale_corr','Muon_bsc_pt_scale_corr'],
    "Muon_pt_ScaRe": ['Muon_pt_corr', 'Muon_bsc_pt_corr'],
    "Muon_pt_noCorr_FSR": ['Muon_pt_nano_FSR','Muon_pt_bsc_FSR'],
    "Muon_pt_scale_FSR":['Muon_pt_nano_scale_corr_FSR',"Muon_bsc_pt_nano_scale_corr_FSR"]
    "Muon_pt_ScaRe_FSR":["Muon_pt_nano_scare_FSR",'Muon_bsc_pt_nano_scare_FSR']
}
muon_sel_dict_shifted = {
    "Muon_pt_scale_up": ['Muon_pt_scale_corr_up', 'Muon_bsc_pt_scale_corr_up'],
    "Muon_pt_scale_down": ['Muon_pt_scale_corr_down', 'Muon_bsc_pt_scale_corr_down'],
    "Muon_pt_resol_up": ['Muon_pt_corr_resol_up', 'Muon_bsc_pt_corr_resol_up'],
    "Muon_pt_resol_down": ['Muon_pt_corr_resol_down', 'Muon_bsc_pt_corr_resol_down'],
    "Muon_pt_scale_FSR_up": ['Muon_pt_nano_scale_corr_FSR_up', 'Muon_bsc_pt_nano_scale_corr_FSR_up'],
    "Muon_pt_scale_FSR_down": ['Muon_pt_nano_scale_corr_FSR_down', 'Muon_bsc_pt_nano_scale_corr_FSR_down'],
    "Muon_pt_resol_FSR_up": ['Muon_pt_nano_corr_resol_FSR_up', 'Muon_bsc_pt_nano_corr_resol_FSR_up'],
    "Muon_pt_resol_FSR_down": ['Muon_pt_nano_corr_resol_FSR_down', 'Muon_bsc_pt_nano_corr_resol_FSR_down'],
}
if not is_data:
    muon_sel_dict.extend(muon_sel_dict_shifted)
for mu_pt_final_name,muons_pt_orig in muon_sel_dict.items():
    df = df.Define(mu_pt_final_name, f"Muon_pt_sel({muons_pt_orig[0]},{muons_pt_orig[1]},Muon_bsConstrainedChi2)")


muon_pt_for_sel = ["Muon_pt_ScaRe_FSR"]
if not is_data:
    muon_pt_for_sel.extend(["Muon_pt_scale_FSR_up","Muon_pt_scale_FSR_down","Muon_pt_resol_FSR_up","Muon_pt_resol_FSR_down"])
muon_presel = "{} > 15 && abs(Muon_eta) < 2.4 && Muon_mediumId && "
# df = LeptonsSelection(df)

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