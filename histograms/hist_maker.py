#!/usr/bin/env python3

import ROOT
import sys
import os
import argparse
import time
import traceback
import subprocess
import copy
from multiprocessing import get_context

ROOT.gROOT.SetBatch(True)
ROOT.EnableThreadSafety()

sys.path.append(os.environ["ANALYSIS_PATH"])

import common.utilities as utilities
from common.helpers import GetModel,GetRdfForDataset,get_root_files,get_valid_root_files,get_segmentation_dict,is_valid_tmp_root
from common.add_vars_to_skim_tuples import (
    DefineHistogramSelections,
    GetSelectionSuffixForSystematic,
    SelectedJetObservablesDef,
    VBFJetObservablesDef,
)
from common.dy_ptll_reweight import (
    ApplyDYAmcatnloNormalization,
    ApplyDYNJetsReweight,
    ApplyDYPtLLReweight,
)
from corrections.qcd_scale import get_qcd_scale_points
HEADERS = ["analysis/AnalysisTools.h"]
for header in HEADERS:
    utilities.DeclareHeader(f"{os.environ['ANALYSIS_PATH']}/{header}")

DNN_SIDEBAND_SHIFTED_PAYLOADS = {
    "Z_sideband": "DNNZSidebandMassShift",
    "H_sideband": "DNNHSidebandMassShift",
}

def chunk_list(items, chunk_size):
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
def safe_mkdir(path):
    if path:
        os.makedirs(path, exist_ok=True)
def remove_file_if_exists(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"[WARNING] Could not remove file {path}: {e}")

def has_usable_events_tree(path):
    root_file = ROOT.TFile.Open(path, "READ")

    if not root_file or root_file.IsZombie():
        return False

    tree = root_file.Get("Events")

    if not tree:
        root_file.Close()
        return False

    has_branches = tree.GetListOfBranches().GetEntries() > 0
    root_file.Close()
    return has_branches

def filter_usable_chunk_files(chunk_files):
    usable_files = []
    skipped_files = []

    for path in chunk_files:
        if has_usable_events_tree(path):
            usable_files.append(path)
        else:
            skipped_files.append(path)

    return usable_files, skipped_files

def print_chunk_error(chunk_index, chunk_files, error):
    print("\n" + "=" * 80)
    print(f"[ERROR] Chunk {chunk_index} failed")
    print("[ERROR] Files in failed chunk:")

    for f in chunk_files:
        print(f"  {f}")

    print(f"[ERROR] Exception: {repr(error)}")
    print("[ERROR] Traceback:")
    traceback.print_exc()
    print("=" * 80 + "\n")

def format_systematic_info(syst_info, scale=None):
    formatted = {}

    for key, value in syst_info.items():
        if isinstance(value, str) and scale is not None:
            formatted[key] = value.replace("{scale}", scale)
        else:
            formatted[key] = value

    return formatted


def nuisance_histogram_name(variable, syst_name, syst_info, era, process):
    if syst_name == "Central":
        return variable

    nuisance_name = syst_info.get("name", syst_name)
    nuisance_name = nuisance_name.format(
        era=era.removeprefix("Run3_"),
        process=process,
        pdf_process=pdf_process_label(syst_info.get("pdf_config", {}), process),
    )
    direction = syst_info.get("direction")
    if direction:
        nuisance_name = f"{nuisance_name}{direction.capitalize()}"
    return f"{variable}_{nuisance_name}"


def unique_metadata_inputs(paths):
    unique_paths = []
    seen = set()

    for path in paths:
        if not path:
            continue
        normalized = os.path.abspath(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_paths.append(path)

    return unique_paths


def get_combined_segmentation_dict(
    input_paths,
    node="gen",
    fallback_to_initial=True,
    warn_if_missing=True,
):
    combined = {}
    metadata_inputs = unique_metadata_inputs(input_paths)

    for input_path in metadata_inputs:
        sums = get_segmentation_dict(
            input_path,
            node=node,
            fallback_to_initial=fallback_to_initial,
            warn_if_missing=False,
        )
        combined.update(sums)

    if not combined and warn_if_missing:
        print(
            "[WARNING] No segmentation JSON information found under: "
            + ", ".join(metadata_inputs)
        )

    return combined


def get_qcd_scale_segmentation_dict(input_paths, point_name, **kwargs):
    warn_if_missing = kwargs.pop("warn_if_missing", True)
    node_candidates = [
        f"qcd_scale__{point_name}",
        f"gen_qcdScale_{point_name}",
    ]

    for node in node_candidates:
        sums = get_combined_segmentation_dict(
            input_paths,
            node=node,
            warn_if_missing=False,
            **kwargs,
        )
        if sums:
            return sums

    if warn_if_missing:
        print(
            "[WARNING] No QCD scale segmentation JSON information found for "
            f"{point_name} under: " + ", ".join(unique_metadata_inputs(input_paths))
        )

    return {}


def get_qcd_scale_variations(qcd_scale_config):
    return qcd_scale_config.get(
        "variations",
        [
            {
                "name": "QCDscaleMuR_{process}",
                "down": "muR0p5_muF1",
                "up": "muR2_muF1",
            },
            {
                "name": "QCDscaleMuF_{process}",
                "down": "muR1_muF0p5",
                "up": "muR1_muF2",
            },
        ],
    )


def get_qcd_scale_source_points(qcd_scale_config):
    points_by_name = {
        point["name"]: point
        for point in get_qcd_scale_points(qcd_scale_config)
    }
    source_names = []

    for variation in get_qcd_scale_variations(qcd_scale_config):
        for direction in ("down", "up"):
            point_name = variation[direction]
            if point_name not in points_by_name:
                raise ValueError(
                    f"QCD scale variation point '{point_name}' is not defined "
                    "in qcd_scale.points."
                )
            if point_name not in source_names:
                source_names.append(point_name)

    return [points_by_name[name] for name in source_names]


def qcd_scale_process_label(qcd_scale_config, process):
    process_labels = qcd_scale_config.get("process_labels", {})
    if process in process_labels:
        return process_labels[process]

    lower_process = process.lower()
    if lower_process.startswith(("dy", "w")) or "ewk" in lower_process:
        return "V"
    if lower_process.startswith(("tt", "st", "tw")):
        return "ttbar"
    if lower_process.startswith("vbf") or "vbfh" in lower_process:
        return "qqH"
    if lower_process.startswith(("gluglu", "ggh")):
        return "ggH"
    if lower_process.startswith("vh") or "zh" in lower_process or "wh" in lower_process:
        return "VH"
    if lower_process.startswith(("tth", "ttH".lower())):
        return "ttH"
    if lower_process.startswith("vvv"):
        return "VVV"
    if lower_process.startswith("vv") or lower_process in {"ww", "wz", "zz"}:
        return "VV"

    return process


def pdf_process_label(pdf_config, process):
    process_labels = pdf_config.get("process_labels", {})
    if process in process_labels:
        return process_labels[process]

    lower_process = process.lower()
    if lower_process.startswith(("dy", "w")) or "ewk" in lower_process:
        return "qqbar"
    if lower_process.startswith("vbf") or "vbfh" in lower_process:
        return "Higgs_qqH"
    if lower_process.startswith(("gluglu", "ggh")):
        return "Higgs_ggH"
    if lower_process.startswith("vh") or "zh" in lower_process or "wh" in lower_process:
        return "Higgs_VH"
    if lower_process.startswith("tth"):
        return "Higgs_ttH"
    if lower_process.startswith("tt"):
        return "gg"
    if lower_process.startswith(("st", "tw")):
        return "gq"
    if lower_process.startswith("vvv"):
        return "qqbar"
    if lower_process.startswith("vv") or lower_process in {"ww", "wz", "zz"}:
        return "qqbar"

    return process


def configure_available_qcd_scale(syst_cfg, input_paths, is_data, mode):
    qcd_config = syst_cfg.get("qcd_scale", {})
    if (
        is_data
        or mode == "central"
        or not qcd_config.get("enabled", False)
    ):
        return syst_cfg

    available_points = []
    missing_points = []
    source_points = get_qcd_scale_source_points(qcd_config)
    for point in source_points:
        point_name = point["name"]
        sums = get_qcd_scale_segmentation_dict(
            input_paths,
            point_name,
            fallback_to_initial=False,
            warn_if_missing=False,
        )
        if sums:
            available_points.append(point)
        else:
            missing_points.append(point_name)

    configured = copy.deepcopy(syst_cfg)
    configured["qcd_scale"]["points"] = available_points
    available_names = {point["name"] for point in available_points}
    configured["qcd_scale"]["variations"] = [
        variation
        for variation in get_qcd_scale_variations(qcd_config)
        if variation["down"] in available_names and variation["up"] in available_names
    ]

    if not missing_points:
        return configured

    missing_policy = qcd_config.get("missing_sums", "error")
    message = (
        "QCD scale sums are missing from the skim reports for: "
        + ", ".join(missing_points)
    )
    if missing_policy == "error":
        raise RuntimeError(
            f"{message}. Reproduce the skim with --want-variations."
        )
    if missing_policy != "skip":
        raise ValueError(
            "qcd_scale.missing_sums must be either 'skip' or 'error'"
        )

    if available_points:
        print(
            f"[WARNING] {message}. Missing QCD scale points will be skipped; "
            f"{len(configured['qcd_scale']['variations'])} QCD scale "
            "variation(s) will still be produced."
        )
    else:
        configured["qcd_scale"]["enabled"] = False
        print(
            f"[WARNING] {message}. QCD scale templates will be skipped; "
            "all other requested systematics will still be produced."
        )
    return configured


def get_systs_to_run(syst_cfg, mode):
    systs_to_run = {
        "Central": syst_cfg["systematics"]["Central"]
    }

    if mode == "central":
        return systs_to_run

    scales = syst_cfg.get("scales", ["up", "down"])

    for syst_name, syst_info in syst_cfg.get("systematics", {}).items():
        if syst_name == "Central":
            continue
        if mode == "jec-jer" and syst_name not in ("JER", "JES_Total"):
            continue

        for scale in scales:
            output_name = f"{syst_name}{scale.capitalize()}"
            formatted = format_systematic_info(syst_info, scale=scale)
            formatted["direction"] = scale
            systs_to_run[output_name] = formatted

    for weight_name, weight_info in syst_cfg.get("weights", {}).items():
        if weight_name == "Central":
            continue
        if weight_info.get("derived_envelope", False):
            continue

        if "{scale}" in weight_name:
            for scale in scales:
                output_name = weight_name.format(scale=scale)
                formatted = format_systematic_info(weight_info, scale=scale)
                formatted["direction"] = scale
                if weight_name.startswith("PDF_"):
                    formatted["pdf_config"] = syst_cfg.get("pdf", {})
                systs_to_run[output_name] = formatted
        else:
            formatted = dict(weight_info)
            for direction in scales:
                if weight_name.endswith(f"_{direction}"):
                    formatted["direction"] = direction
                    break
            if weight_name.startswith("PDF_"):
                formatted["pdf_config"] = syst_cfg.get("pdf", {})
            systs_to_run[weight_name] = formatted

    qcd_scale_config = syst_cfg.get("qcd_scale", {})
    if qcd_scale_config.get("enabled", False):
        for point in get_qcd_scale_source_points(qcd_scale_config):
            point_name = point["name"]
            output_name = f"QCDScale__{point_name}"
            systs_to_run[output_name] = {
                "jet_suffix": "",
                "muon_suffix": "",
                "name": output_name,
                "weight": f"weight__{output_name}",
            }

    return systs_to_run


def write_qcd_scale_variations(
    output_file,
    syst_cfg,
    variables,
    mass_regions,
    categories,
    era,
    process,
):
    qcd_scale_config = syst_cfg.get("qcd_scale", {})
    if not qcd_scale_config.get("enabled", False):
        return

    variations = get_qcd_scale_variations(qcd_scale_config)
    process_label = qcd_scale_process_label(qcd_scale_config, process)
    source_suffixes = sorted(
        {
            f"QCDScale__{variation[direction]}"
            for variation in variations
            for direction in ("down", "up")
        }
    )
    for mass_region in mass_regions:
        for category in categories:
            directory = output_file.GetDirectory(
                f"{mass_region}_{category}"
            )
            if not directory:
                continue
            for variable in variables:
                central = directory.Get(variable)
                if not central or not central.InheritsFrom("TH1"):
                    continue

                for variation in variations:
                    nuisance_name = variation["name"].format(
                        era=era.removeprefix("Run3_"),
                        process=process_label,
                    )
                    for direction, shape_direction in (
                        ("down", "Down"),
                        ("up", "Up"),
                    ):
                        source = directory.Get(
                            f"{variable}_QCDScale__{variation[direction]}"
                        )
                        if source is None or not source.InheritsFrom("TH1"):
                            continue
                        hist = source.Clone(
                            f"{variable}_{nuisance_name}{shape_direction}"
                        )
                        hist.SetDirectory(0)
                        directory.WriteTObject(hist, hist.GetName(), "Overwrite")
                for source_suffix in source_suffixes:
                    directory.Delete(
                        f"{variable}_{source_suffix};*"
                    )

def define_shifted_jet_observables(rdf, systs_to_run):
    defined_suffixes = set()
    available_columns = {str(c) for c in rdf.GetColumnNames()}

    for syst_info in systs_to_run.values():
        jet_suffix = syst_info.get("jet_suffix", "")
        if not jet_suffix or jet_suffix in defined_suffixes:
            continue

        required = {
            f"SelectedJet_idx{jet_suffix}",
            f"SelectedJet_pt{jet_suffix}",
            f"SelectedJet_eta{jet_suffix}",
            f"SelectedJet_phi{jet_suffix}",
            f"SelectedJet_mass{jet_suffix}",
            f"SelectedJet_IsInsideHorn{jet_suffix}",
            f"HasVBF{jet_suffix}",
            f"VBFJetIdx_1{jet_suffix}",
            f"VBFJetIdx_2{jet_suffix}",
        }
        missing = sorted(required - available_columns)
        if missing:
            raise RuntimeError(
                f"Cannot build jet variation '{jet_suffix}'; missing columns: "
                + ", ".join(missing)
            )

        rdf = SelectedJetObservablesDef(rdf, suffix=jet_suffix)
        rdf = VBFJetObservablesDef(rdf, suffix=jet_suffix)
        defined_suffixes.add(jet_suffix)
        available_columns = {str(c) for c in rdf.GetColumnNames()}

    return rdf

def get_histogram_variable(variable, syst_info, available_columns):
    jet_suffix = syst_info.get("jet_suffix", "")
    muon_suffix = syst_info.get("muon_suffix", "")
    candidates = []

    if jet_suffix:
        candidates.append(f"{variable}{jet_suffix}")
    if muon_suffix:
        candidates.append(f"{variable}{muon_suffix}")
    candidates.append(variable)

    return next(
        (candidate for candidate in candidates if candidate in available_columns),
        None,
    )

def should_shift_sideband_dnn_mass(mass_region, variable):
    return mass_region in DNN_SIDEBAND_SHIFTED_PAYLOADS and variable == "DNN_NNOutput"

def get_sideband_shifted_mass_expression(mass_region):
    if mass_region == "Z_sideband":
        return "static_cast<float>(115.0 + 0.5 * (m_mumu - 70.0))"
    if mass_region == "H_sideband":
        return (
            "static_cast<float>(m_mumu < 115.0 ? "
            "115.0 + (m_mumu - 110.0) : 120.0 + (m_mumu - 135.0))"
        )
    raise ValueError(f"Unsupported DNN mass-shift region: {mass_region}")

def apply_sideband_mass_shifted_dnn(rdf, mass_region, btag_algo, era):
    from common.dnn_application import ApplyDNN

    shifted_rdf = rdf.Redefine(
        "m_mumu",
        get_sideband_shifted_mass_expression(mass_region),
    )
    return ApplyDNN(
        shifted_rdf,
        [DNN_SIDEBAND_SHIFTED_PAYLOADS[mass_region]],
        btag_algo=btag_algo,
        era=era,
    )

def process_single_chunk(args_tuple):
    (chunk_index,n_chunks,chunk_files,args,is_data,sel_cfg,syst_cfg,vars_to_make_hist,masses_regions,masses_regions_list,categories,categories_list,hist_cfg,systs_to_run,dnn_payloads,btag_algo) = args_tuple
    tmp_output = f"{args.output_file}.tmp_{chunk_index}.root"
    try:
        print(f"[CHUNK {chunk_index} / {n_chunks}] Starting with {len(chunk_files)} file(s)")
        # for f in chunk_files:
        #     print(f"[CHUNK {chunk_index}]   {f}")
        usable_chunk_files, skipped_empty_files = filter_usable_chunk_files(chunk_files)

        if skipped_empty_files:
            print(
                f"[CHUNK {chunk_index} / {n_chunks}] Skipping "
                f"{len(skipped_empty_files)} file(s) with missing/empty Events branches."
            )

        chunk_seg_dict = get_combined_segmentation_dict(args.metadata_inputs)# ,root_files=usable_chunk_files)
        qcd_scale_seg_dicts = {}
        if (
            not is_data
            and args.systematics != "central"
            and syst_cfg.get("qcd_scale", {}).get("enabled", False)
        ):
            for point in get_qcd_scale_points(syst_cfg["qcd_scale"]):
                point_name = point["name"]
                qcd_scale_seg_dicts[point_name] = get_qcd_scale_segmentation_dict(
                    args.metadata_inputs,
                    point_name,
                    fallback_to_initial=False,
                )
        print(f"[CHUNK {chunk_index} / {n_chunks}] Using {len(chunk_seg_dict)} segmentation entries for {len(usable_chunk_files)} ROOT file(s)")

        if usable_chunk_files:
            rdf_base = GetRdfForDataset(input_dir=args.input,is_data=is_data,weight_dict=syst_cfg["weights"],store_shifted_weights=args.systematics != "central",treeName="Events",explicit_files=usable_chunk_files,seg_dict=chunk_seg_dict,skip_validation=True,dnn_payloads=dnn_payloads,btag_algo=btag_algo,additional_cuts = args.additional_cuts,era=args.era,qcd_scale_config=syst_cfg.get("qcd_scale"),qcd_scale_seg_dicts=qcd_scale_seg_dicts,pdf_config=syst_cfg.get("pdf"))
            # print(rdf_base.GetColumnNames())
        else:
            rdf_base = None
        if rdf_base is None:
            print(f"[CHUNK {chunk_index} / {n_chunks}] WARNING: rdf_base is None. Writing empty histograms.")
        else:
            rdf_base = define_shifted_jet_observables(rdf_base, systs_to_run)
            rdf_base = DefineHistogramSelections(
                rdf_base,
                sel_cfg,
                syst_cfg=syst_cfg,
                want_variations=args.systematics != "central",
            )
            weight_columns = sorted(
                {
                    syst_info["weight"]
                    for syst_info in systs_to_run.values()
                    if "weight" in syst_info
                }
            )
            rdf_base = ApplyDYAmcatnloNormalization(
                rdf_base,
                args.dataset_name,
                weight_columns,
            )
            if args.dy_ptll_njets_reweight_json:
                rdf_base = ApplyDYPtLLReweight(
                    rdf_base,
                    args.dataset_name,
                    args.dy_ptll_njets_reweight_json,
                    weight_columns,
                )
            if args.dy_njets_reweight_json:
                rdf_base = ApplyDYNJetsReweight(
                    rdf_base,
                    args.dataset_name,
                    args.dy_njets_reweight_json,
                    weight_columns,
                )

        outFile = ROOT.TFile(tmp_output, "RECREATE")
        if not outFile or outFile.IsZombie():
            raise RuntimeError(f"Could not create output file: {tmp_output}")
        booked_hists = []
        for syst_name, syst_info in systs_to_run.items():
            weight_name = syst_info["weight"]
            selection_suffix = GetSelectionSuffixForSystematic(syst_name, syst_info)
            for mass_region, mass_info in masses_regions.items():
                if mass_region not in masses_regions_list:
                    continue
                if not mass_info.get("store", False):
                    continue
                for category, cat_info in categories.items():
                    if category not in categories_list:
                        continue
                    if not cat_info.get("store", False):
                        continue
                    rdf_for_category = rdf_base
                    if rdf_for_category is not None:
                        mass_region_column = f"{mass_region}{selection_suffix}"
                        category_column = f"{category}{selection_suffix}"
                        available_columns = set(str(c) for c in rdf_for_category.GetColumnNames())

                        missing_selection_columns = [
                            col
                            for col in (mass_region_column, category_column)
                            if col not in available_columns
                        ]
                        if missing_selection_columns:
                            raise RuntimeError(
                                "Missing histogram selection column(s): "
                                + ", ".join(missing_selection_columns)
                            )

                        rdf_filtered = rdf_for_category.Filter(
                            f"{mass_region_column} && {category_column}",
                            f"{mass_region}_{category}_{syst_name}",
                        )
                    else:
                        rdf_filtered = None
                    dir_ptr = utilities.mkdir_recursive(outFile,f"{mass_region}_{category}")
                    for var in vars_to_make_hist:
                        model = GetModel(hist_cfg, var, dims=1)
                        hist_name = nuisance_histogram_name(
                            var,
                            syst_name,
                            syst_info,
                            args.era,
                            args.process_name,
                        )
                        if rdf_filtered is not None:
                            rdf_for_hist = rdf_filtered
                            available_columns = {
                                str(c) for c in rdf_for_hist.GetColumnNames()
                            }
                            hist_var = get_histogram_variable(
                                var,
                                syst_info,
                                available_columns,
                            )

                            if should_shift_sideband_dnn_mass(mass_region, var):
                                print(f"going to shift in {mass_region}, {var}")
                                rdf_for_hist = apply_sideband_mass_shifted_dnn(
                                    rdf_for_hist,
                                    mass_region,
                                    btag_algo=btag_algo,
                                    era=args.era,
                                )
                                shifted_payload = DNN_SIDEBAND_SHIFTED_PAYLOADS[mass_region]
                                hist_var = f"{shifted_payload}_NNOutput"

                            if hist_var is not None and hist_var not in available_columns:
                                available_columns = set(str(c) for c in rdf_for_hist.GetColumnNames())

                            if hist_var is None or hist_var not in available_columns:
                                print(
                                    f"[CHUNK {chunk_index}] WARNING: variable '{var}' "
                                    f"not found for systematic '{syst_name}'. "
                                    "Booking empty histogram."
                                )
                                hist = ROOT.TH1D(hist_name,hist_name,model.fNbinsX,model.fXLow,model.fXUp)
                                hist.SetDirectory(0)
                                booked_hists.append((dir_ptr, hist_name, hist, False))
                                continue
                            if weight_name not in available_columns:
                                raise RuntimeError(f"Weight column '{weight_name}' not found for systematic '{syst_name}'")
                            hist_ptr = rdf_for_hist.Histo1D(model, hist_var, weight_name)
                            booked_hists.append((dir_ptr, hist_name, hist_ptr, True))
                        else:
                            hist = ROOT.TH1D(hist_name,hist_name,model.fNbinsX,model.fXLow,model.fXUp)
                            hist.SetDirectory(0)
                            booked_hists.append((dir_ptr, hist_name, hist, False))

        print(f"[CHUNK {chunk_index} / {n_chunks}] Booked {len(booked_hists)} histograms. Running event loop...")
        for dir_ptr, hist_name, hist_obj, needs_getvalue in booked_hists:
            hist = hist_obj.GetValue() if needs_getvalue else hist_obj
            hist.SetName(hist_name)
            hist.SetTitle(hist_name)
            hist.SetDirectory(0)
            dir_ptr.cd()
            dir_ptr.WriteTObject(hist, hist_name, "Overwrite")
        outFile.Close()
        print(f"[CHUNK {chunk_index} / {n_chunks}] Done -> {tmp_output}")
        return tmp_output
    except Exception as e:
        print_chunk_error(chunk_index, chunk_files, e)
        remove_file_if_exists(tmp_output)
        raise

def write_failed_chunks_report(output_file, failed_chunks):
    if not failed_chunks:
        return
    failed_report = f"{output_file}.failed_chunks.txt"
    with open(failed_report, "w") as f:
        for chunk_index, chunk_files, err in failed_chunks:
            f.write(f"\nCHUNK {chunk_index}\n")
            f.write(f"ERROR: {err}\n")
            for rf in chunk_files:
                f.write(f"{rf}\n")
    print(f"[WARNING] Failed chunks report written to: {failed_report}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--era", required=True, type=str)
    parser.add_argument("--input", required=True, type=str)
    parser.add_argument(
        "--metadata-input",
        help=(
            "Directory or file used to read skim report/segmentation JSONs. "
            "It is merged with --input and can be used as a temporary metadata patch."
        ),
    )
    parser.add_argument(
        "--extra-metadata-input",
        action="append",
        default=[],
        help=(
            "Additional directory or file with skim report/segmentation JSONs. "
            "Can be passed multiple times."
        ),
    )
    parser.add_argument(
        "--input-files-file",
        help=(
            "Text file containing the ROOT files to process, one per line. "
            "--input is still used for dataset metadata and segmentation JSONs."
        ),
    )
    parser.add_argument("--dataset-name", "--dataset", dest="dataset_name", required=True, type=str)
    parser.add_argument("--output-file", required=True, type=str)
    parser.add_argument(
        "--systematics",
        choices=["central", "jec-jer", "all"],
        default="central",#jec-jer",
        help=(
            "central: nominal only; jec-jer: nominal, JEC/JER shapes and all "
            "configured weight shifts (default); all: every configured variation."
        ),
    )
    parser.add_argument("--chunk-size", type=int, default=6)
    parser.add_argument("--n-cores", type=int, default=4)
    parser.add_argument("--skip-file-validation", action="store_true")
    parser.add_argument("--variables", nargs="+")
    parser.add_argument("--mass-regions", nargs="+", default=["mass_inclusive", "Z_sideband", "Signal_Fit"])
    parser.add_argument("--categories", nargs="+", default=["baseline", "ggF", "VBF"])
    parser.add_argument("--dryrun", action="store_true")
    parser.add_argument("--keep-tmp", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-failed-chunks", action="store_true")
    parser.add_argument("--force-multiprocessing-with-dnn", action="store_true")
    parser.add_argument("--multiprocessing-method", choices=["spawn", "fork"], default="spawn")
    parser.add_argument("--additional-cuts",type=str, default=None)
    parser.add_argument(
        "--dy-ptll-njets-reweight-json",
        "--dy-ptll-njets-reweight",
        "--dy-ptll-reweight-json",
        "--dy-ptll-reweight",
        "--dy-reweight-json",
        dest="dy_ptll_njets_reweight_json",
        default=None,
        help=(
            "JSON produced by histograms/derive_dy_ptll_njets_reweight.py. "
            "When provided, only DY datasets get an extra pt(ll) weight "
            "evaluated with isVBF, N_SelectedJets, and pt_mumu."
        ),
    )
    parser.add_argument(
        "--dy-njets-reweight-json",
        "--dy-njets-reweight",
        dest="dy_njets_reweight_json",
        default=None,
        help=(
            "JSON produced by histograms/derive_dy_njets_reweight.py. "
            "When provided, only DY datasets get an extra NJets weight "
            "evaluated with isVBF and N_SelectedJets."
        ),
    )
    parser.add_argument(
        "--shift-z-sideband-dnn-mass",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    args.metadata_inputs = unique_metadata_inputs(
        [args.input, args.metadata_input, *args.extra_metadata_input]
    )
    startTime = time.time()
    if args.chunk_size < 1:
        raise ValueError("--chunk-size must be >= 1")
    if args.n_cores < 1:
        raise ValueError("--n-cores must be >= 1")
    analysis_path = os.environ["ANALYSIS_PATH"]
    cfg_dir = os.path.join(analysis_path, "config", args.era)
    main_cfg = utilities.get_config(os.path.join(cfg_dir, "maincfg.yaml"))
    samples_cfg = utilities.get_config(os.path.join(cfg_dir, "samples.yaml"))
    dataset_cfg = samples_cfg.get(args.dataset_name, {})
    is_data = dataset_cfg.get("is_data", False) or "data" in args.dataset_name.lower()
    process_cfg = utilities.get_config(os.path.join(cfg_dir, "process_names.yaml"))
    args.process_name = (
        utilities.process_from_dataset(process_cfg, args.dataset_name)
        or args.dataset_name
    )
    sel_cfg = utilities.get_config(os.path.join(cfg_dir, "selections.yaml"))
    syst_cfg = utilities.get_config(os.path.join(cfg_dir, "systematics.yaml"))
    hist_cfg = utilities.get_config(os.path.join(analysis_path, "config", "plot", "histograms.yaml"))
    masses_regions = sel_cfg["masses_regions"]
    categories = sel_cfg["categories"]
    masses_regions_list = args.mass_regions
    categories_list = args.categories
    vars_to_make_hist = list(dict.fromkeys(args.variables or main_cfg["variables"]))

    dnn_payloads = sorted({var.rsplit("_NNOutput", 1)[0]for var in vars_to_make_hist if var.endswith("_NNOutput")})
    btag_algo = main_cfg.get("bTagAlgo", "PNet")
    # if len(dnn_payloads) > 0 and args.n_cores > 1 and not args.force_multiprocessing_with_dnn:
    #     print("[WARNING] DNN payloads requested: forcing n_cores = 1.")
    #     args.n_cores = 1
    syst_cfg = configure_available_qcd_scale(
        syst_cfg,
        args.metadata_inputs,
        is_data,
        args.systematics,
    )
    systs_to_run = get_systs_to_run(syst_cfg, args.systematics)
    if args.input_files_file:
        with open(args.input_files_file) as input_files_handle:
            all_root_files = [
                line.strip()
                for line in input_files_handle
                if line.strip() and not line.lstrip().startswith("#")
            ]
    else:
        all_root_files = get_root_files(args.input)
    if args.skip_file_validation:
        valid_root_files = all_root_files
    else:
        valid_root_files = get_valid_root_files(all_root_files, tree_name="Events")
    valid_root_files = [os.path.abspath(f) for f in valid_root_files]
    if len(valid_root_files) == 0:
        if len(all_root_files) == 0:
            print("[WARNING] No ROOT files found. Producing empty histograms.")
        else:
            print(
                "[WARNING] No ROOT files with a usable Events tree found. "
                "Producing empty histograms."
            )
        chunks = [[]]
    else:
        chunks = chunk_list(valid_root_files, args.chunk_size)
    # print("\n" + "=" * 80)
    # print("[INFO] Histogram maker configuration")
    # print(f"[INFO] Era:              {args.era}")
    # print(f"[INFO] Dataset:          {args.dataset_name}")
    # print(f"[INFO] Is data:          {is_data}")
    # print(f"[INFO] Input:            {args.input}")
    # print(f"[INFO] Output:           {args.output_file}")
    # print(f"[INFO] Systematics:      {args.systematics}")
    # print(f"[INFO] Chunk size:       {args.chunk_size}")
    # print(f"[INFO] Chunks:           {len(chunks)}")
    # print(f"[INFO] Cores:            {args.n_cores}")
    # print(f"[INFO] Resume:           {args.resume}")
    # print(f"[INFO] Skip failed:      {args.skip_failed_chunks}")
    # print(f"[INFO] Variables:        {vars_to_make_hist}")
    # print(f"[INFO] Mass regions:     {masses_regions_list}")
    # print(f"[INFO] Categories:       {categories_list}")
    # print(f"[INFO] DNN payloads:     {dnn_payloads}")
    # print(f"[INFO] bTag algo:        {btag_algo}")
    # print(f"[INFO] Valid files:      {len(valid_root_files)} / {len(all_root_files)}")
    # print("=" * 80 + "\n")
    if args.dryrun:
        print("[DRYRUN] Chunks:")
        for idx, chunk_files in enumerate(chunks):
            print(f"\n[DRYRUN] Chunk {idx}: {len(chunk_files)} file(s)")
            chunk_seg_dict = get_combined_segmentation_dict(args.metadata_inputs)
            print(f"[DRYRUN] Segmentation entries: {len(chunk_seg_dict)}")
            for f in chunk_files:
                print(f"  {f}")
        print("\n[DRYRUN] Exiting.")
        sys.exit(0)
    output_dir = os.path.dirname(args.output_file)
    safe_mkdir(output_dir)
    if os.path.exists(args.output_file):
        print(f"[INFO] Removing existing output file: {args.output_file}")
        os.remove(args.output_file)
    if not args.resume:
        for idx in range(len(chunks)):
            stale_tmp = f"{args.output_file}.tmp_{idx}.root"
            remove_file_if_exists(stale_tmp)
    pool_inputs = []
    n_chunks = len(chunks)
    for idx, chunk_files in enumerate(chunks):
        pool_inputs.append((idx,n_chunks,chunk_files,args,is_data,sel_cfg,syst_cfg,vars_to_make_hist,masses_regions,masses_regions_list,categories,categories_list,hist_cfg,systs_to_run,dnn_payloads,btag_algo))
    tmp_files = []
    failed_chunks = []
    print("\n[INFO] Starting chunk processing...\n")

    def handle_success(tmp):
        tmp_files.append(tmp)
        print(f"[INFO] Finished chunk -> {tmp}")

    if args.n_cores == 1:
        for item in pool_inputs:
            chunk_index = item[0]
            chunk_files = item[2]
            tmp_output = f"{args.output_file}.tmp_{chunk_index}.root"
            if args.resume and is_valid_tmp_root(tmp_output):
                print(f"[RESUME] Chunk {chunk_index} already processed: {tmp_output}")
                tmp_files.append(tmp_output)
                continue
            try:
                tmp = process_single_chunk(item)
                handle_success(tmp)
            except Exception as e:
                failed_chunks.append((chunk_index, chunk_files, repr(e)))
                remove_file_if_exists(tmp_output)

                if args.skip_failed_chunks:
                    print(f"[WARNING] Skipping failed chunk {chunk_index}")
                    continue

                print("[ERROR] Stopping because --skip-failed-chunks was not used.")
                write_failed_chunks_report(args.output_file, failed_chunks)
                sys.exit(1)
    else:
        items_to_run = []
        for item in pool_inputs:
            chunk_index = item[0]
            tmp_output = f"{args.output_file}.tmp_{chunk_index}.root"
            if args.resume and is_valid_tmp_root(tmp_output):
                print(f"[RESUME] Chunk {chunk_index} already processed: {tmp_output}")
                tmp_files.append(tmp_output)
            else:
                items_to_run.append(item)
        ctx = get_context(args.multiprocessing_method)
        try:
            with ctx.Pool(processes=args.n_cores) as pool:
                for tmp in pool.imap_unordered(process_single_chunk, items_to_run, chunksize=1):
                    handle_success(tmp)
        except Exception as e:
            print(f"[ERROR] A multiprocessing chunk failed: {repr(e)}")
            if args.skip_failed_chunks:
                print(
                    "[ERROR] Precise skip of failed chunks is only safe with --n-cores 1. "
                    "Rerun with --n-cores 1 --resume --skip-failed-chunks."
                )
                write_failed_chunks_report(args.output_file, failed_chunks)
                sys.exit(1)
            print("[ERROR] Stopping because --skip-failed-chunks was not used.")
            write_failed_chunks_report(args.output_file, failed_chunks)
            sys.exit(1)
    write_failed_chunks_report(args.output_file, failed_chunks)
    if len(tmp_files) == 0:
        print("[ERROR] No successful temporary files available. Exiting.")
        sys.exit(1)
    print(f"\n[INFO] Merging {len(tmp_files)} successful temporary files into:")
    print(f"[INFO]   {args.output_file}")
    hadd_cmd = ["hadd", "-f", args.output_file] + sorted(tmp_files)
    print("[INFO] Running:")
    print(" ".join(hadd_cmd))
    result = subprocess.run(hadd_cmd)
    if result.returncode != 0:
        print("[ERROR] hadd failed.")
        sys.exit(result.returncode)
    print("[INFO] hadd completed successfully.")
    merged_output = ROOT.TFile.Open(args.output_file, "UPDATE")
    if not merged_output or merged_output.IsZombie():
        raise RuntimeError(
            f"Could not reopen merged output file: {args.output_file}"
        )
    if args.systematics != "central":
        write_qcd_scale_variations(
            merged_output,
            syst_cfg,
            vars_to_make_hist,
            masses_regions_list,
            categories_list,
            args.era,
            args.process_name,
        )
    merged_output.Close()
    if args.keep_tmp:
        print("[INFO] Keeping temporary files because --keep-tmp was used.")
    else:
        print("[INFO] Cleaning temporary files...")
        for tmp_f in tmp_files:
            remove_file_if_exists(tmp_f)
    executionTime = time.time() - startTime
    print("\n" + "=" * 80)
    print("[INFO] Histogram production completed successfully.")
    print(f"[INFO] Output file: {args.output_file}")
    print(f"[INFO] Successful chunks: {len(tmp_files)} / {len(chunks)}")
    print(f"[INFO] Failed chunks:     {len(failed_chunks)}")
    print(f"[INFO] Execution time:    {executionTime:.2f} s")
    print("=" * 80 + "\n")
