#!/usr/bin/env python3

import argparse
import copy
import os
import subprocess
import sys
import time
import traceback
from multiprocessing import get_context
from pathlib import Path

import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.EnableThreadSafety()

sys.path.append(os.environ["ANALYSIS_PATH"])

import common.utilities as utilities
from common.failed_chunk_policy import (
    metadata_for_root_files,
    resolve_skip_failed_chunks,
    validate_skip_failed_chunks,
)
from common.add_vars_to_skim_tuples import (
    GetSelectionSuffixForSystematic,
    SelectedJetObservablesDef,
    VBFJetObservablesDef,
)
from common.histogram_pipeline import finalize_histogram_dataframe
from common.jet_component_splitting import (
    DY_COMPONENT_FILE_LABELS,
    GGF_COMPONENT_VARIABLES,
    VBF_COMPONENTS,
    VBF_ETA_REGIONS,
    add_jet_component_categories,
    add_vbf_eta_region_categories,
    define_jet_gen_matching,
    expanded_jet_component_categories,
    variable_for_component,
)
from common.manifests import read_manifest
from common.runtime import initialize_root_runtime
from common.helpers import (
    GetModel,
    GetRdfForDataset,
    findBinEntry,
    get_root_files,
    get_segmentation_dict,
    is_valid_tmp_root,
)
from corrections.qcd_scale import get_qcd_scale_points

initialize_root_runtime()

DNN_SIDEBAND_SHIFTED_PAYLOADS = {
    "Z_sideband": "DNNZSidebandMassShift",
    "H_sideband": "DNNHSidebandMassShift",
}


_WORKER_SEG_DICT = None
_WORKER_QCD_SCALE_SEG_DICTS = None


def initialize_worker_metadata(seg_dict, qcd_scale_seg_dicts):
    global _WORKER_SEG_DICT
    global _WORKER_QCD_SCALE_SEG_DICTS

    _WORKER_SEG_DICT = seg_dict
    _WORKER_QCD_SCALE_SEG_DICTS = qcd_scale_seg_dicts
    print(
        f"[WORKER {os.getpid()}] Installed dataset metadata: "
        f"{len(seg_dict)} central entries, "
        f"{len(qcd_scale_seg_dicts)} QCD-scale dictionaries"
    )

_METADATA_CACHE = {}


def profile_log(chunk_index, phase, started_at):
    elapsed = time.perf_counter() - started_at
    print(f"[PROFILE][CHUNK {chunk_index}] {phase}: {elapsed:.3f} s", flush=True)
    return time.perf_counter()


def chunk_list(items, chunk_size):
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def chunk_output_path(args, chunk_index):
    return str(Path(args.tmp_output_dir) / f"chunk_{chunk_index + 1}.root")


def safe_mkdir(path):
    if path:
        os.makedirs(path, exist_ok=True)


def remove_file_if_exists(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"[WARNING] Could not remove file {path}: {e}")


def histogram_directory_path(mass_region, category):
    if category.startswith("VBF_eta_"):
        eta_region = category.removeprefix("VBF_eta_")
        return f"{mass_region}_VBF/{eta_region}"
    return f"{mass_region}_{category}"


def copy_root_directory(source_file, source_path, target_file, target_path):
    """Copy all objects from one ROOT directory into a nested target directory."""
    source = source_file.GetDirectory(source_path)
    if not source:
        return False
    target = utilities.mkdir_recursive(target_file, target_path)
    for key in source.GetListOfKeys():
        obj = key.ReadObj()
        target.cd()
        target.WriteTObject(obj, obj.GetName(), "Overwrite")
    return True


def split_dy_jet_component_outputs(output_file, mass_regions):
    """Create the inclusive and per-component DY files with fit-ready layout."""
    output_path = Path(output_file)
    source = ROOT.TFile.Open(str(output_path), "READ")
    if not source or source.IsZombie():
        raise RuntimeError(f"Could not open DY component staging file: {output_file}")

    inclusive_tmp = output_path.with_name(f".{output_path.name}.inclusive.tmp.root")
    inclusive = ROOT.TFile.Open(str(inclusive_tmp), "RECREATE")
    component_files = {}
    try:
        for component, label in DY_COMPONENT_FILE_LABELS.items():
            component_path = output_path.with_name(
                f"{output_path.stem}_{label}{output_path.suffix}"
            )
            component_files[component] = (
                component_path,
                ROOT.TFile.Open(str(component_path), "RECREATE"),
            )

        for mass_region in mass_regions:
            copy_root_directory(
                source,
                f"{mass_region}_DY_inclusive_ggF",
                inclusive,
                f"{mass_region}_ggF/incl",
            )
            for eta_region in VBF_ETA_REGIONS:
                copy_root_directory(
                    source,
                    f"{mass_region}_DY_inclusive_VBF_{eta_region}",
                    inclusive,
                    f"{mass_region}_VBF/{eta_region}",
                )

            for component in GGF_COMPONENT_VARIABLES:
                _, target = component_files[component]
                copy_root_directory(
                    source,
                    f"{mass_region}_{component}",
                    target,
                    f"{mass_region}_ggF/incl",
                )
            for component in VBF_COMPONENTS:
                _, target = component_files[component]
                for eta_region in VBF_ETA_REGIONS:
                    copy_root_directory(
                        source,
                        f"{mass_region}_{component}_{eta_region}",
                        target,
                        f"{mass_region}_VBF/{eta_region}",
                    )
    finally:
        source.Close()
        inclusive.Close()
        for _, target in component_files.values():
            target.Close()

    os.replace(inclusive_tmp, output_path)
    print("[INFO] DY inclusive/component outputs:")
    print(f"[INFO]   inclusive: {output_path}")
    for component in DY_COMPONENT_FILE_LABELS:
        print(f"[INFO]   {component}: {component_files[component][0]}")


def has_usable_events_tree(path, retries=3, retry_delay=2.0):
    last_error = None

    for attempt in range(1, retries + 1):
        root_file = None
        try:
            root_file = ROOT.TFile.Open(path, "READ")
            if not root_file or root_file.IsZombie():
                raise OSError("cannot open ROOT file or file is a zombie")

            tree = root_file.Get("Events")
            if not tree:
                raise KeyError("missing Events tree")

            return tree.GetListOfBranches().GetEntries() > 0
        except Exception as error:
            last_error = error
            if attempt < retries:
                print(
                    f"[WARNING] Could not validate {path} "
                    f"(attempt {attempt}/{retries}): {error}. Retrying..."
                )
                time.sleep(retry_delay)
        finally:
            if root_file:
                root_file.Close()

    print(
        f"[WARNING] Giving up opening {path} after {retries} attempt(s): "
        f"{last_error}"
    )
    return False


def filter_usable_chunk_files(chunk_files, retries=3, retry_delay=2.0):
    usable_files = []
    skipped_files = []

    for path in chunk_files:
        if has_usable_events_tree(path, retries=retries, retry_delay=retry_delay):
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
    metadata_inputs = unique_metadata_inputs(input_paths)
    cache_key = (
        tuple(os.path.abspath(path) for path in metadata_inputs),
        node,
        bool(fallback_to_initial),
    )
    if cache_key in _METADATA_CACHE:
        return _METADATA_CACHE[cache_key]

    combined = get_segmentation_dict(
        metadata_inputs,
        node=node,
        fallback_to_initial=fallback_to_initial,
        warn_if_missing=warn_if_missing,
    )

    _METADATA_CACHE[cache_key] = combined
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


def normalization_for_root_files(
    metadata_inputs,
    root_files,
    syst_cfg,
    systematics_mode,
):
    """Rebuild central and QCD-scale denominators for surviving ROOT files."""
    filtered_metadata = metadata_for_root_files(metadata_inputs, root_files)
    central = get_combined_segmentation_dict(filtered_metadata)
    qcd_scale = {}
    if (
        systematics_mode != "central"
        and syst_cfg.get("qcd_scale", {}).get("enabled", False)
    ):
        for point in get_qcd_scale_points(syst_cfg["qcd_scale"]):
            point_name = point["name"]
            qcd_scale[point_name] = get_qcd_scale_segmentation_dict(
                filtered_metadata,
                point_name,
                fallback_to_initial=False,
            )
    return central, qcd_scale


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


def parse_requested_systematics(values):
    if not values:
        return []

    requested = []
    for value in values:
        for item in str(value).replace(",", " ").split():
            if item:
                requested.append(item)

    return list(dict.fromkeys(requested))


def expand_systematic_group_alias(requested_name, available_systematics):
    normalized_name = requested_name.lower().replace("_", "").replace("-", "")
    aliases = {
        "jerc": (
            "JERUp",
            "JERDown",
            "JES_TotalUp",
            "JES_TotalDown",
        ),
        "qcdscale": tuple(
            name
            for name in available_systematics
            if name.startswith("QCDScale__")
        ),
        "qcdscales": tuple(
            name
            for name in available_systematics
            if name.startswith("QCDScale__")
        ),
        "pdf": tuple(
            name
            for name in available_systematics
            if name.startswith("PDF_")
        ),
        "scaleweight": tuple(
            name
            for name in available_systematics
            if name.startswith("QCDScale__") or name.startswith("PDF_")
        ),
        "scare": (
            "MuonScaleUp",
            "MuonScaleDown",
            "MuonResUp",
            "MuonResDown",
        ),
        "muon": (
            "MuonID_up",
            "MuonID_down",
            "MuonIso_up",
            "MuonIso_down",
            "singleMuTrigger_up",
            "singleMuTrigger_down",
        ),
        "pu": (
            "PU_up",
            "PU_down",
        ),
    }

    return [
        name
        for name in aliases.get(normalized_name, ())
        if name in available_systematics
    ]


def filter_systs_to_run(systs_to_run, requested_systematics):
    requested_raw = parse_requested_systematics(requested_systematics)
    requested = []

    for name in requested_raw:
        expanded = expand_systematic_group_alias(name, systs_to_run)
        if expanded:
            requested.extend(expanded)
        else:
            requested.append(name)

    requested = list(dict.fromkeys(requested))

    if not requested:
        return systs_to_run

    missing = [name for name in requested if name not in systs_to_run]
    if missing:
        available = ", ".join(sorted(systs_to_run))
        raise ValueError(
            "Unknown requested systematic(s): "
            + ", ".join(missing)
            + ". Available systematics: "
            + available
        )

    return {name: systs_to_run[name] for name in requested}


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
                histogram_directory_path(mass_region, category)
            )
            if not directory:
                continue
            for variable in variables:
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
                        if not source or not source.InheritsFrom(ROOT.TH1.Class()):
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

def apply_sideband_mass_shifted_dnn(
    rdf, mass_region, btag_algo, era, dnn_model_set
):
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
        model_set=dnn_model_set,
    )

def process_single_chunk(args_tuple):
    (
        chunk_index,
        n_chunks,
        chunk_files,
        args,
        is_data,
        sel_cfg,
        syst_cfg,
        vars_to_make_hist,
        masses_regions,
        masses_regions_list,
        categories,
        categories_list,
        hist_cfg,
        systs_to_run,
        dnn_payloads,
        btag_algo,
    ) = args_tuple
    tmp_output = chunk_output_path(args, chunk_index)
    out_file = None

    try:
        if args.rdf_threads > 1 and not ROOT.IsImplicitMTEnabled():
            ROOT.EnableImplicitMT(args.rdf_threads)
        print(
            f"[CHUNK {chunk_index} / {n_chunks}] Starting with "
            f"{len(chunk_files)} file(s)"
        )
        phase_started = time.perf_counter()
        usable_chunk_files = chunk_files
        profile_log(chunk_index, "chunk setup", phase_started)

        global _WORKER_SEG_DICT
        global _WORKER_QCD_SCALE_SEG_DICTS

        if not is_data and _WORKER_SEG_DICT is None:
            raise RuntimeError(
                "Dataset segmentation metadata was not initialized in this worker"
            )

        # MC normalization denominators are global to the dataset, not to the
        # chunk. Data do not need segmentation metadata at all.
        chunk_seg_dict = None if is_data else _WORKER_SEG_DICT
        qcd_scale_seg_dicts = (
            {} if is_data else (_WORKER_QCD_SCALE_SEG_DICTS or {})
        )
        if is_data:
            print(
                f"[CHUNK {chunk_index} / {n_chunks}] Data dataset: "
                "segmentation metadata disabled"
            )
        else:
            print(
                f"[CHUNK {chunk_index} / {n_chunks}] Using "
                f"{len(chunk_seg_dict)} segmentation entries for "
                f"{len(usable_chunk_files)} ROOT file(s)"
            )

        rdf_started = time.perf_counter()
        rdf_base = None
        if usable_chunk_files:
            rdf_base = GetRdfForDataset(
                input_dir=args.root_input,
                is_data=is_data,
                weight_dict=syst_cfg["weights"],
                store_shifted_weights=args.systematics_mode != "central",
                treeName="Events",
                explicit_files=usable_chunk_files,
                seg_dict=chunk_seg_dict,
                skip_validation=True,
                dnn_payloads=dnn_payloads,
                btag_algo=btag_algo,
                additional_cuts=args.additional_cuts,
                era=args.era,
                dnn_model_set=args.dnn_model_set,
                qcd_scale_config=syst_cfg.get("qcd_scale"),
                qcd_scale_seg_dicts=qcd_scale_seg_dicts,
                pdf_config=syst_cfg.get("pdf"),
            )

        profile_log(chunk_index, "RDataFrame construction", rdf_started)

        dataframe_finalize_started = time.perf_counter()
        if rdf_base is None:
            print(
                f"[CHUNK {chunk_index} / {n_chunks}] WARNING: no usable input "
                "events. Writing empty histograms."
            )
        else:
            rdf_base = define_shifted_jet_observables(rdf_base, systs_to_run)
            if args.dy_jet_components:
                rdf_base = define_jet_gen_matching(
                    rdf_base,
                    {
                        GetSelectionSuffixForSystematic(name, info)
                        for name, info in systs_to_run.items()
                    },
                )
            weight_columns = sorted({
                syst_info["weight"]
                for syst_info in systs_to_run.values()
                if "weight" in syst_info
            })
            rdf_base = finalize_histogram_dataframe(
                rdf_base,
                args.dataset_name,
                sel_cfg,
                syst_cfg,
                weight_columns,
                want_variations=args.systematics_mode != "central",
                dy_ptll_reweight_json=args.dy_ptll_njets_reweight_json,
                dy_njets_reweight_json=args.dy_njets_reweight_json,
            )

        profile_log(chunk_index, "dataframe definitions/finalization", dataframe_finalize_started)

        booking_setup_started = time.perf_counter()
        stored_regions = [
            name
            for name, info in masses_regions.items()
            if name in masses_regions_list and info.get("store", False)
        ]
        stored_categories = [
            name
            for name, info in categories.items()
            if name in categories_list and info.get("store", False)
        ]
        hist_specs = {}
        for variable in vars_to_make_hist:
            config_key = findBinEntry(hist_cfg, variable)
            configured_columns = hist_cfg[config_key].get("var_list")
            columns = tuple(configured_columns or (variable,))
            hist_specs[variable] = {
                "columns": columns,
                "model": GetModel(hist_cfg, variable, dims=len(columns)),
            }

        base_columns = (
            {str(column) for column in rdf_base.GetColumnNames()}
            if rdf_base is not None
            else set()
        )
        selection_suffixes = {
            GetSelectionSuffixForSystematic(name, info)
            for name, info in systs_to_run.items()
        }
        required_selection_columns = {
            f"{selection}{suffix}"
            for suffix in selection_suffixes
            for selection in (*stored_regions, *stored_categories)
        }
        missing_selection_columns = sorted(required_selection_columns - base_columns)
        if rdf_base is not None and missing_selection_columns:
            raise RuntimeError(
                "Missing histogram selection column(s): "
                + ", ".join(missing_selection_columns)
            )

        # Apply each sideband DNN once per distinct selection suffix, before any
        # histograms are booked. ApplyDNN materializes its inputs; doing this in
        # the booking loop would otherwise trigger repeated RDF event loops.
        shifted_rdfs = {}
        if rdf_base is not None and "DNN_NNOutput" in vars_to_make_hist:
            for mass_region in stored_regions:
                if not should_shift_sideband_dnn_mass(
                    mass_region, "DNN_NNOutput"
                ):
                    continue
                for selection_suffix in selection_suffixes:
                    mass_column = f"{mass_region}{selection_suffix}"
                    region_rdf = rdf_base.Filter(
                        mass_column,
                        f"{mass_region}_{selection_suffix or 'central'}_dnn_input",
                    )
                    shifted_rdf = apply_sideband_mass_shifted_dnn(
                        region_rdf,
                        mass_region,
                        btag_algo=btag_algo,
                        era=args.era,
                        dnn_model_set=args.dnn_model_set,
                    )
                    shifted_rdfs[(mass_region, selection_suffix)] = (
                        shifted_rdf,
                        {str(column) for column in shifted_rdf.GetColumnNames()},
                    )

        # Weight-only systematics share their selection suffix. Cache each
        # region/category filter so its predicate is evaluated once per event,
        # rather than once for every weight variation.
        filtered_rdfs = {}
        if rdf_base is not None:
            for selection_suffix in selection_suffixes:
                for mass_region in stored_regions:
                    mass_column = f"{mass_region}{selection_suffix}"
                    shifted_entry = shifted_rdfs.get(
                        (mass_region, selection_suffix)
                    )
                    region_rdf = (
                        shifted_entry[0]
                        if shifted_entry is not None
                        else rdf_base.Filter(mass_column)
                    )
                    for category in stored_categories:
                        category_column = f"{category}{selection_suffix}"
                        cache_key = (
                            mass_region,
                            category,
                            selection_suffix,
                        )
                        if shifted_entry is not None:
                            _, available_columns = shifted_entry
                        else:
                            available_columns = base_columns
                        filtered_rdf = region_rdf.Filter(category_column)
                        filtered_rdfs[cache_key] = (
                            filtered_rdf,
                            available_columns,
                        )

        profile_log(chunk_index, "selection and DNN graph construction", booking_setup_started)

        output_open_started = time.perf_counter()
        out_file = ROOT.TFile(tmp_output, "RECREATE")
        if not out_file or out_file.IsZombie():
            raise RuntimeError(f"Could not create output file: {tmp_output}")

        directories = {
            (mass_region, category): utilities.mkdir_recursive(
                out_file, histogram_directory_path(mass_region, category)
            )
            for mass_region in stored_regions
            for category in stored_categories
        }
        profile_log(chunk_index, "temporary output open/directory creation", output_open_started)
        histogram_booking_started = time.perf_counter()
        booked_hists = []
        for syst_name, syst_info in systs_to_run.items():
            weight_name = syst_info["weight"]
            selection_suffix = GetSelectionSuffixForSystematic(
                syst_name, syst_info
            )
            if rdf_base is not None and weight_name not in base_columns:
                raise RuntimeError(
                    f"Weight column '{weight_name}' not found for systematic "
                    f"'{syst_name}'"
                )

            for mass_region in stored_regions:
                for category in stored_categories:
                    rdf_filtered = None
                    available_columns = base_columns
                    filtered_entry = filtered_rdfs.get(
                        (mass_region, category, selection_suffix)
                    )
                    if filtered_entry is not None:
                        rdf_filtered, available_columns = filtered_entry

                    directory = directories[(mass_region, category)]
                    category_variables = set(
                        variable_for_component(
                            category, args.vbf_component_variables
                        )
                        if args.dy_jet_components
                        else vars_to_make_hist
                    )
                    for variable, spec in hist_specs.items():
                        if variable not in category_variables:
                            continue
                        model = spec["model"]
                        hist_name = nuisance_histogram_name(
                            variable,
                            syst_name,
                            syst_info,
                            args.era,
                            args.process_name,
                        )
                        hist_columns = tuple(
                            get_histogram_variable(
                                column, syst_info, available_columns
                            )
                            for column in spec["columns"]
                        )
                        if should_shift_sideband_dnn_mass(mass_region, variable):
                            shifted_payload = DNN_SIDEBAND_SHIFTED_PAYLOADS[
                                mass_region
                            ]
                            hist_columns = (f"{shifted_payload}_NNOutput",)

                        if (
                            rdf_filtered is not None
                            and all(
                                column in available_columns
                                for column in hist_columns
                            )
                        ):
                            if len(hist_columns) == 1:
                                hist_ptr = rdf_filtered.Histo1D(
                                    model, hist_columns[0], weight_name
                                )
                            elif len(hist_columns) == 2:
                                hist_ptr = rdf_filtered.Histo2D(
                                    model,
                                    hist_columns[0],
                                    hist_columns[1],
                                    weight_name,
                                )
                            else:
                                raise RuntimeError(
                                    f"Unsupported histogram dimension for "
                                    f"{variable}: {len(hist_columns)}"
                                )
                            booked_hists.append(
                                (directory, hist_name, hist_ptr, True)
                            )
                            continue

                        if rdf_filtered is not None:
                            print(
                                f"[CHUNK {chunk_index}] WARNING: variable "
                                f"'{variable}' not found for systematic "
                                f"'{syst_name}'. Booking empty histogram."
                            )
                        hist = model.GetHistogram().Clone(hist_name)
                        hist.SetTitle(hist_name)
                        hist.Reset("ICES")
                        hist.SetDirectory(0)
                        booked_hists.append((directory, hist_name, hist, False))

        profile_log(
            chunk_index,
            f"histogram booking ({len(booked_hists)} histograms)",
            histogram_booking_started,
        )
        print(
            f"[CHUNK {chunk_index} / {n_chunks}] Booked "
            f"{len(booked_hists)} histograms. Running event loop..."
        )
        histogram_actions = [
            hist_obj
            for _, _, hist_obj, needs_getvalue in booked_hists
            if needs_getvalue
        ]
        event_loop_started = time.perf_counter()
        if histogram_actions:
            ROOT.RDF.RunGraphs(histogram_actions)
        profile_log(chunk_index, "ROOT event loop (RunGraphs)", event_loop_started)

        output_write_started = time.perf_counter()
        for directory, hist_name, hist_obj, needs_getvalue in booked_hists:
            hist = hist_obj.GetValue() if needs_getvalue else hist_obj
            hist.SetName(hist_name)
            hist.SetTitle(hist_name)
            hist.SetDirectory(0)
            directory.cd()
            directory.WriteTObject(hist, hist_name, "Overwrite")
        out_file.Close()
        out_file = None
        profile_log(chunk_index, "histogram materialization/write/close", output_write_started)
        print(f"[CHUNK {chunk_index} / {n_chunks}] Done -> {tmp_output}")
        return tmp_output
    except Exception as error:
        if out_file:
            out_file.Close()
        print_chunk_error(chunk_index, chunk_files, error)
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
    parser = argparse.ArgumentParser(
        description="Produce histograms from validated skimmed ROOT ntuples."
    )
    parser.add_argument("--era", required=True, help="Era, e.g. Run3_2022EE")
    parser.add_argument(
        "--root-input",
        "--input",
        dest="root_input",
        default=None,
        help=(
            "Skimmed ROOT ntuple file or directory. Required only when "
            "--input-manifest is not provided."
        ),
    )
    parser.add_argument(
        "--json-input",
        "--metadata-input",
        dest="json_input",
        default=None,
        help=(
            "Skim-report/segmentation JSON file or directory. Required only "
            "when --input-manifest is not provided; it may equal --root-input."
        ),
    )
    parser.add_argument(
        "--additional-metadata-input",
        "--extra-metadata-input",
        dest="additional_metadata_inputs",
        action="append",
        default=[],
        help=(
            "Optional extra metadata JSON file/directory. May be repeated; "
            "later inputs override duplicate segmentation keys."
        ),
    )
    parser.add_argument(
        "--input-files-file",
        help="Optional text file listing ROOT files, one per line.",
    )
    parser.add_argument(
        "--input-manifest",
        help="Optional validation manifest containing known-good ROOT/JSON files.",
    )
    parser.add_argument(
        "--file-open-retries",
        "--validation-retries",
        dest="file_open_retries",
        type=int,
        default=3,
        help="Number of attempts when ROOT opens fail during processing.",
    )
    parser.add_argument(
        "--file-open-retry-delay",
        type=float,
        default=2.0,
        help="Seconds between file-open attempts (default: 2).",
    )
    parser.add_argument(
        "--dataset-name", "--dataset", dest="dataset_name", required=True
    )
    parser.add_argument("--output-file", required=True)
    parser.add_argument(
        "--systematics",
        nargs="+",
        default=["Central"],
        help=(
            "One or more systematic keys/groups to calculate. Examples: "
            "Central; Central JERUp JERDown; JERC Muon PU; all. "
            "Comma-separated values are also accepted."
        ),
    )
    parser.add_argument(
        "--list-systematics",
        action="store_true",
        help="Print all available systematic keys and exit.",
    )
    parser.add_argument("--chunk-size", type=int, default=6)
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help=(
            "Process at most the first N validated ROOT files. Intended for "
            "quick technical tests; dataset normalization still uses the "
            "complete manifest metadata."
        ),
    )
    parser.add_argument("--n-cores", type=int, default=4)
    parser.add_argument(
        "--rdf-threads",
        type=int,
        default=1,
        help="ROOT RDataFrame worker threads per histogram process.",
    )
    parser.add_argument("--variables", nargs="+")
    parser.add_argument(
        "--mass-regions",
        nargs="+",
        default=["mass_inclusive", "Z_sideband", "Signal_Fit"],
    )
    parser.add_argument(
        "--categories", nargs="+", default=["baseline", "ggF", "VBF"]
    )
    parser.add_argument("--additional-cuts", default=None)
    parser.add_argument("--dryrun", action="store_true")
    parser.add_argument("--keep-tmp", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--skip-failed-chunks",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Skip failed MC chunks and renormalize surviving chunks. Default: "
            "enabled for serial MC, disabled for data and parallel processing."
        ),
    )
    parser.add_argument(
        "--dy-jet-components",
        action="store_true",
        help=(
            "Split DY MC into exclusive reco-jet/gen-matching components and "
            "book the prescribed 0J m_mumu, 1J eta(j1):pt(j1), and "
            "2J eta(j2):pt(j2) fit templates."
        ),
    )
    parser.add_argument(
        "--vbf-eta-regions",
        action="store_true",
        help=(
            "Split the VBF category into nested incl/CC/CF/FF directories "
            "using |eta(VBF jet)| = 2.5. This is independent of DY "
            "Hard/PU component splitting."
        ),
    )
    parser.add_argument("--force-multiprocessing-with-dnn", action="store_true")
    parser.add_argument(
        "--dnn-model-set",
        choices=["updated", "legacy"],
        default="updated",
        help=(
            "DNN payload generation. 'legacy' uses the 2022-2023 model for "
            "2022/2022EE/2023/2023BPix and the 2024-2025 model for 2024/2025."
        ),
    )
    parser.add_argument(
        "--multiprocessing-method", choices=["spawn", "fork"], default="spawn"
    )
    parser.add_argument(
        "--dy-ptll-reweight-json",
        "--dy-ptll-njets-reweight-json",
        "--dy-ptll-njets-reweight",
        "--dy-ptll-reweight",
        "--dy-reweight-json",
        dest="dy_ptll_njets_reweight_json",
        default=None,
        help="Optional DY pT(ll) reweight JSON.",
    )
    parser.add_argument(
        "--dy-njets-reweight-json",
        "--dy-njets-reweight",
        dest="dy_njets_reweight_json",
        default=None,
        help="Optional DY N(jets) reweight JSON.",
    )
    parser.add_argument(
        "--shift-z-sideband-dnn-mass", action="store_true", help=argparse.SUPPRESS
    )
    args = parser.parse_args()

    workflow_manifest = None
    if args.input_manifest:
        if not os.path.isfile(args.input_manifest):
            raise FileNotFoundError(
                f"Input manifest does not exist: {args.input_manifest}"
            )

        workflow_manifest = read_manifest(args.input_manifest)
        if (
            workflow_manifest.get("era") != args.era
            or workflow_manifest.get("dataset") != args.dataset_name
        ):
            raise ValueError(
                "Input manifest era/dataset does not match histogram job: "
                f"manifest=({workflow_manifest.get('era')}, "
                f"{workflow_manifest.get('dataset')}), "
                f"requested=({args.era}, {args.dataset_name})"
            )

        manifest_stage = workflow_manifest.get("stage")
        if manifest_stage == "validation":
            if "valid_root_files" not in workflow_manifest:
                raise ValueError(
                    "Validation manifest is missing 'valid_root_files'"
                )
            if "valid_json_files" not in workflow_manifest:
                raise ValueError(
                    "Validation manifest is missing 'valid_json_files'"
                )
            if workflow_manifest.get("status", "passed") != "passed":
                invalid_roots = len(workflow_manifest.get("invalid_root_files", []))
                valid_roots = len(workflow_manifest.get("valid_root_files", []))
                print(
                    "[WARNING] Using partially failed validation manifest "
                    f"{args.input_manifest}: {valid_roots} valid ROOT file(s), "
                    f"{invalid_roots} invalid ROOT file(s)."
                )

            # The manifest is the source of truth. Folder arguments, when also
            # supplied, are intentionally ignored for the validated file lists.
            args.root_input = workflow_manifest.get("root_input")
            args.json_input = workflow_manifest.get("json_input")
            args.metadata_inputs = unique_metadata_inputs(
                [
                    *workflow_manifest["valid_json_files"],
                    *args.additional_metadata_inputs,
                ]
            )

        else:
            raise ValueError(
                f"Unsupported histogram input manifest stage: {manifest_stage}"
            )

    else:
        if not args.root_input:
            parser.error(
                "--root-input is required when --input-manifest is not provided"
            )
        if not args.json_input:
            parser.error(
                "--json-input is required when --input-manifest is not provided"
            )

        # Standalone mode: consume exactly the ROOT and JSON inputs supplied by
        # the caller. Validation is a separate workflow stage.
        args.metadata_inputs = unique_metadata_inputs(
            [args.json_input, *args.additional_metadata_inputs]
        )

    start_time = time.time()
    if args.chunk_size < 1:
        raise ValueError("--chunk-size must be >= 1")
    if args.max_files is not None and args.max_files < 1:
        raise ValueError("--max-files must be >= 1")
    if args.n_cores < 1:
        raise ValueError("--n-cores must be >= 1")
    if args.rdf_threads < 1:
        raise ValueError("--rdf-threads must be >= 1")
    if args.file_open_retries < 1:
        raise ValueError("--file-open-retries must be >= 1")
    if args.file_open_retry_delay < 0:
        raise ValueError("--file-open-retry-delay must be >= 0")
    if (
        args.n_cores > 1
        and args.rdf_threads > 1
        and args.multiprocessing_method == "fork"
    ):
        raise ValueError(
            "--rdf-threads > 1 cannot be combined with "
            "--multiprocessing-method fork; use spawn"
        )
    if args.rdf_threads > 1 and args.n_cores == 1:
        ROOT.EnableImplicitMT(args.rdf_threads)
        print(
            "[INFO] Enabled ROOT implicit multithreading with "
            f"{args.rdf_threads} threads"
        )
    analysis_path = os.environ["ANALYSIS_PATH"]
    cfg_dir = os.path.join(analysis_path, "config", args.era)
    main_cfg = utilities.get_config(os.path.join(cfg_dir, "maincfg.yaml"))
    samples_cfg = utilities.get_config(os.path.join(cfg_dir, "samples.yaml"))
    dataset_cfg = samples_cfg.get(args.dataset_name, {})
    is_data = (
        dataset_cfg.get("is_data", False)
        or "data" in args.dataset_name.lower()
    )
    skip_policy_was_explicit = args.skip_failed_chunks is not None
    args.skip_failed_chunks = resolve_skip_failed_chunks(
        args.skip_failed_chunks,
        is_data,
        args.n_cores,
    )
    if not skip_policy_was_explicit:
        policy_reason = (
            "serial MC default"
            if args.skip_failed_chunks
            else "data/parallel fail-fast default"
        )
        print(
            f"[INFO] Failed-chunk policy: "
            f"{'skip and renormalize' if args.skip_failed_chunks else 'fail fast'} "
            f"({policy_reason})."
        )
    elif not args.skip_failed_chunks:
        print("[INFO] Failed-chunk policy: fail fast (explicit override).")
    validate_skip_failed_chunks(
        args.skip_failed_chunks,
        is_data,
        args.n_cores,
        args.resume,
    )
    requested_systematics = parse_requested_systematics(args.systematics)
    request_all = any(name.lower() == "all" for name in requested_systematics)
    request_central_only = {
        name.lower() for name in requested_systematics
    } <= {"central", "nominal"}
    systematics_mode = "central" if request_central_only else "all"
    empty_validated_input = bool(
        args.input_manifest
        and not workflow_manifest.get("valid_root_files", [])
    )
    if empty_validated_input:
        # A failed/empty validation manifest has no events or variation
        # metadata from which systematic templates can be built.  Still emit
        # one nominal empty histogram so downstream campaign bookkeeping has a
        # valid ROOT output instead of failing while resolving (for example)
        # the QCDScale alias.
        print(
            "[WARNING] Validation manifest contains no valid ROOT files: "
            "producing Central empty histograms only."
        )
        requested_systematics = ["Central"]
        request_all = False
        request_central_only = True
        systematics_mode = "central"
    if args.list_systematics:
        request_all = True
        systematics_mode = "all"
    print(systematics_mode)
    if is_data and systematics_mode != "central":
        print(
            f"[INFO] Dataset {args.dataset_name} is data: ignoring non-central "
            "systematics and producing Central histograms only."
        )
        requested_systematics = ["Central"]
        systematics_mode = "central"
    args.systematics_mode = systematics_mode
    process_cfg = utilities.get_config(os.path.join(cfg_dir, "process_names.yaml"))
    args.process_name = (
        utilities.process_from_dataset(process_cfg, args.dataset_name)
        or args.dataset_name
    )
    sel_cfg = utilities.get_config(os.path.join(cfg_dir, "selections.yaml"))
    syst_cfg = utilities.get_config(os.path.join(cfg_dir, "systematics.yaml"))
    hist_cfg = utilities.get_config(
        os.path.join(analysis_path, "config", "plot", "histograms.yaml")
    )
    if args.dy_jet_components and args.vbf_eta_regions:
        raise ValueError(
            "--dy-jet-components already includes VBF eta regions; do not "
            "combine it with --vbf-eta-regions"
        )
    if args.vbf_eta_regions:
        sel_cfg = add_vbf_eta_region_categories(sel_cfg)
        args.categories = [f"VBF_eta_{region}" for region in VBF_ETA_REGIONS]
    if args.dy_jet_components:
        if is_data:
            raise ValueError("--dy-jet-components cannot be used on data")
        if not args.dataset_name.startswith("DY"):
            raise ValueError(
                "--dy-jet-components is restricted to DY datasets; the "
                "underlying matching helpers are reusable for other MC."
            )
        sel_cfg = add_jet_component_categories(sel_cfg)
        args.categories = list(expanded_jet_component_categories())
        args.vbf_component_variables = list(args.variables or ["m_mumu"])
        vars_to_add = [
            "m_mumu",
            "eta_vs_pt_leadingjet",
            "eta_vs_pt_subleadingjet",
        ]
        args.variables = list(dict.fromkeys([*(args.variables or []), *vars_to_add]))
    else:
        args.vbf_component_variables = []
    masses_regions = sel_cfg["masses_regions"]
    categories = sel_cfg["categories"]
    masses_regions_list = args.mass_regions
    categories_list = args.categories
    vars_to_make_hist = list(dict.fromkeys(args.variables or main_cfg["variables"]))

    dnn_payloads = sorted(
        {
            variable.rsplit("_NNOutput", 1)[0]
            for variable in vars_to_make_hist
            if variable.endswith("_NNOutput")
        }
    )
    btag_algo = main_cfg.get("bTagAlgo", "PNet")
    syst_cfg = configure_available_qcd_scale(
        syst_cfg,
        args.metadata_inputs,
        is_data,
        systematics_mode,
    )
    systs_to_run = get_systs_to_run(syst_cfg, systematics_mode)
    if not request_all:
        requested_systematics = [
            "Central" if name.lower() == "nominal" else name
            for name in requested_systematics
        ]
        systs_to_run = filter_systs_to_run(systs_to_run, requested_systematics)
    if args.list_systematics:
        for syst_name in systs_to_run:
            print(syst_name)
        sys.exit(0)

    if is_data:
        dataset_seg_dict = {}
        print(
            f"[INFO] Dataset {args.dataset_name} is data: skipping "
            "segmentation metadata loading."
        )
    else:
        metadata_started = time.perf_counter()
        print(
            f"[INFO] Loading dataset normalization metadata once from "
            f"{len(args.metadata_inputs)} JSON input(s)..."
        )
        dataset_seg_dict = get_combined_segmentation_dict(args.metadata_inputs)
        profile_log(None, "central dataset metadata loading", metadata_started)

    dataset_qcd_scale_seg_dicts = {}
    if (
        not is_data
        and systematics_mode != "central"
        and syst_cfg.get("qcd_scale", {}).get("enabled", False)
    ):
        qcd_metadata_started = time.perf_counter()
        for point in get_qcd_scale_points(syst_cfg["qcd_scale"]):
            point_name = point["name"]
            dataset_qcd_scale_seg_dicts[point_name] = (
                get_qcd_scale_segmentation_dict(
                    args.metadata_inputs,
                    point_name,
                    fallback_to_initial=False,
                )
            )
        profile_log(
            None,
            "QCD-scale dataset metadata loading",
            qcd_metadata_started,
        )

    print(
        f"[INFO] Dataset metadata ready: {len(dataset_seg_dict)} central "
        f"entries and {len(dataset_qcd_scale_seg_dicts)} QCD-scale dictionaries"
    )

    if args.input_manifest:
        all_root_files = workflow_manifest["valid_root_files"]
    elif args.input_files_file:
        with open(args.input_files_file) as input_files_handle:
            all_root_files = [
                line.strip()
                for line in input_files_handle
                if line.strip() and not line.lstrip().startswith("#")
            ]
    else:
        all_root_files = get_root_files(args.root_input)
    # Validation is external. Files from a manifest are already known-good;
    # standalone inputs are consumed exactly as supplied/discovered.
    normalization_root_files = [os.path.abspath(f) for f in all_root_files]
    valid_root_files = list(normalization_root_files)
    if args.max_files is not None:
        original_file_count = len(valid_root_files)
        valid_root_files = valid_root_files[: args.max_files]
        print(
            f"[TEST MODE] Processing {len(valid_root_files)} / "
            f"{original_file_count} validated ROOT file(s) because "
            f"--max-files {args.max_files} was used."
        )
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
    if args.dryrun:
        print("[DRYRUN] Chunks:")
        print(f"[DRYRUN] Segmentation entries: {len(dataset_seg_dict)}")
        print(
            f"[DRYRUN] QCD-scale dictionaries: "
            f"{len(dataset_qcd_scale_seg_dicts)}"
        )
        for idx, chunk_files in enumerate(chunks):
            print(f"\n[DRYRUN] Chunk {idx}: {len(chunk_files)} file(s)")
            for f in chunk_files:
                print(f"  {f}")
        print("\n[DRYRUN] Exiting.")
        sys.exit(0)
    output_dir = os.path.dirname(args.output_file)
    safe_mkdir(output_dir)
    output_path = Path(args.output_file)
    args.tmp_output_dir = str(
        output_path.parent / f"{output_path.stem}_tmp"
    )
    safe_mkdir(args.tmp_output_dir)
    if os.path.exists(args.output_file):
        print(f"[INFO] Removing existing output file: {args.output_file}")
        os.remove(args.output_file)
    if not args.resume:
        for stale_tmp in Path(args.tmp_output_dir).glob("chunk_*.root"):
            remove_file_if_exists(str(stale_tmp))
    pool_inputs = []
    n_chunks = len(chunks)
    for idx, chunk_files in enumerate(chunks):
        pool_inputs.append(
            (
                idx,
                n_chunks,
                chunk_files,
                args,
                is_data,
                sel_cfg,
                syst_cfg,
                vars_to_make_hist,
                masses_regions,
                masses_regions_list,
                categories,
                categories_list,
                hist_cfg,
                systs_to_run,
                dnn_payloads,
                btag_algo,
            )
        )
    tmp_files = []
    failed_chunks = []
    print("\n[INFO] Starting chunk processing...\n")

    def handle_success(tmp):
        tmp_files.append(tmp)
        print(f"[INFO] Finished chunk -> {tmp}")

    if args.n_cores == 1:
        active_items = list(pool_inputs)
        normalization_pass = 0
        excluded_root_files = set()
        while active_items:
            tmp_files = []
            pass_failures = []
            initialize_worker_metadata(
                dataset_seg_dict,
                dataset_qcd_scale_seg_dicts,
            )
            for item in active_items:
                chunk_index = item[0]
                chunk_files = item[2]
                tmp_output = chunk_output_path(args, chunk_index)
                if args.resume and is_valid_tmp_root(tmp_output):
                    print(
                        f"[RESUME] Chunk {chunk_index} already processed: "
                        f"{tmp_output}"
                    )
                    tmp_files.append(tmp_output)
                    continue
                try:
                    tmp = process_single_chunk(item)
                    handle_success(tmp)
                except Exception as error:
                    failure = (chunk_index, chunk_files, repr(error))
                    failed_chunks.append(failure)
                    pass_failures.append(failure)
                    remove_file_if_exists(tmp_output)

            if not pass_failures:
                break
            if not args.skip_failed_chunks:
                print("[ERROR] Stopping because --skip-failed-chunks was not used.")
                write_failed_chunks_report(args.output_file, failed_chunks)
                sys.exit(1)

            failed_indices = {failure[0] for failure in pass_failures}
            for chunk_index, chunk_files, _ in pass_failures:
                excluded_root_files.update(chunk_files)
                print(
                    f"[WARNING] Excluding failed chunk {chunk_index} and all "
                    f"of its {len(chunk_files)} file(s)."
                )
            active_items = [
                item for item in active_items if item[0] not in failed_indices
            ]
            for tmp_file in tmp_files:
                remove_file_if_exists(tmp_file)
            tmp_files = []
            if not active_items:
                break

            surviving_normalization_files = [
                root_file
                for root_file in normalization_root_files
                if root_file not in excluded_root_files
            ]
            dataset_seg_dict, dataset_qcd_scale_seg_dicts = (
                normalization_for_root_files(
                    args.metadata_inputs,
                    surviving_normalization_files,
                    syst_cfg,
                    systematics_mode,
                )
            )
            normalization_pass += 1
            print(
                f"[RENORMALIZE] Pass {normalization_pass}: recalculated "
                f"denominators from {len(surviving_normalization_files)} "
                "dataset file(s), excluding "
                f"{len(excluded_root_files)} file(s) from failed chunks. "
                "Reprocessing every surviving chunk."
            )
    else:
        items_to_run = []
        for item in pool_inputs:
            chunk_index = item[0]
            tmp_output = chunk_output_path(args, chunk_index)
            if args.resume and is_valid_tmp_root(tmp_output):
                print(f"[RESUME] Chunk {chunk_index} already processed: {tmp_output}")
                tmp_files.append(tmp_output)
            else:
                items_to_run.append(item)
        ctx = get_context(args.multiprocessing_method)
        try:
            with ctx.Pool(
                processes=args.n_cores,
                initializer=initialize_worker_metadata,
                initargs=(
                    dataset_seg_dict,
                    dataset_qcd_scale_seg_dicts,
                ),
            ) as pool:
                for tmp in pool.imap_unordered(
                    process_single_chunk, items_to_run, chunksize=1
                ):
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
    hadd_started = time.perf_counter()
    result = subprocess.run(hadd_cmd)
    print(f"[PROFILE] hadd: {time.perf_counter() - hadd_started:.3f} s")
    if result.returncode != 0:
        print("[ERROR] hadd failed.")
        sys.exit(result.returncode)
    print("[INFO] hadd completed successfully.")
    merged_output = ROOT.TFile.Open(args.output_file, "UPDATE")
    if not merged_output or merged_output.IsZombie():
        raise RuntimeError(
            f"Could not reopen merged output file: {args.output_file}"
        )
    if systematics_mode != "central":
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
    if args.dy_jet_components:
        split_dy_jet_component_outputs(
            args.output_file,
            masses_regions_list,
        )
    if args.keep_tmp:
        print("[INFO] Keeping temporary files because --keep-tmp was used.")
    else:
        print("[INFO] Cleaning temporary files...")
        for tmp_f in tmp_files:
            remove_file_if_exists(tmp_f)
        try:
            Path(args.tmp_output_dir).rmdir()
        except OSError:
            pass
    execution_time = time.time() - start_time
    print("\n" + "=" * 80)
    print("[INFO] Histogram production completed successfully.")
    print(f"[INFO] Output file: {args.output_file}")
    print(f"[INFO] Successful chunks: {len(tmp_files)} / {len(chunks)}")
    print(f"[INFO] Failed chunks:     {len(failed_chunks)}")
    print(f"[INFO] Execution time:    {execution_time:.2f} s")
    print("=" * 80 + "\n")
