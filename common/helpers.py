
import array
import bisect
import json
import math
import os
import re
import sys

import numpy as np
import ROOT

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])
import common.utilities as utilities


# ****** root / json files manipulation
def is_valid_root_file(filename, tree_name="Events"):
    root_file = None
    try:
        root_file = ROOT.TFile.Open(filename)
        if not root_file or root_file.IsZombie():
            return False
        tree = root_file.Get(tree_name)
        if not tree:
            return False
        return tree.GetEntries() > 0
    except Exception:
        return False
    finally:
        if root_file:
            root_file.Close()


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
            files.append(os.path.join(root, f))
    return sorted(files)


# ****** dictionary for denum definition
def normalize_stem(path):
    base = os.path.basename(str(path))
    for ext in (".root", ".json"):
        if base.endswith(ext):
            base = base[: -len(ext)]
    return base


def filter_seg_dict_for_files(seg_dict, root_files):
    valid_stems = {normalize_stem(f) for f in root_files}

    out = {}
    for k, v in seg_dict.items():
        if normalize_stem(k) in valid_stems:
            out[k] = v

    return out


def is_valid_tmp_root(path):
    if not os.path.exists(path):
        return False

    root_file = None
    try:
        root_file = ROOT.TFile.Open(path, "READ")
        if not root_file or root_file.IsZombie():
            return False
        return root_file.GetNkeys() > 0
    except Exception:
        return False
    finally:
        if root_file:
            root_file.Close()

def get_segmentation_dict(
    input_dir,
    node="gen",
    fallback_to_initial=True,
    warn_if_missing=True,
):
    global_segmentation = {}

    input_path = os.path.abspath(input_dir)

    if input_path.endswith(".root"):
        search_dir = os.path.dirname(input_path)
        stem = os.path.splitext(os.path.basename(input_path))[0]
        report_path = os.path.join(search_dir, f"{stem}_report.json")
        json_paths = [report_path] if os.path.isfile(report_path) else []

    elif input_path.endswith(".json"):
        search_dir = os.path.dirname(input_path)
        json_paths = [input_path] if os.path.isfile(input_path) else []

    else:
        search_dir = input_path
        json_paths = [
            os.path.join(root, filename)
            for root, _, files in os.walk(search_dir)
            for filename in files
            if filename.endswith(".json")
        ]

    for json_path in json_paths:
        try:
            with open(json_path) as json_file:
                info = json.load(json_file)
        except (OSError, json.JSONDecodeError) as error:
            print(
                f"[WARNING] Could not parse JSON file {json_path}: {error}"
            )
            continue

        node_dict = info.get(node)

        if isinstance(node_dict, dict):
            segmented_keys = [
                key
                for key, value in node_dict.items()
                if key != "total" and isinstance(value, dict)
            ]

            if segmented_keys:
                # Dataset con denominatori distinti per segmentazione.
                # Il total viene ignorato perché è cumulativo.
                for sub_key in segmented_keys:
                    sub_info = node_dict[sub_key]

                    selection = sub_info.get("selection")
                    value = sub_info.get("value", 0.0)

                    if not selection:
                        continue

                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        print(
                            f"[WARNING] Invalid value for node '{node}', "
                            f"segment '{sub_key}', file {json_path}: {value!r}"
                        )
                        continue

                    global_segmentation[selection] = (
                        global_segmentation.get(selection, 0.0) + value
                    )

            elif isinstance(node_dict.get("total"), dict):
                # Dataset non segmentato.
                total_info = node_dict["total"]

                selection = total_info.get("selection", "return true;")
                value = total_info.get("value", 0.0)

                try:
                    value = float(value)
                except (TypeError, ValueError):
                    print(
                        f"[WARNING] Invalid total value for node '{node}', "
                        f"file {json_path}: {value!r}"
                    )
                    continue

                global_segmentation[selection] = (
                    global_segmentation.get(selection, 0.0) + value
                )

            else:
                print(
                    f"[WARNING] Node '{node}' has no usable segmentation "
                    f"entries in {json_path}"
                )

        elif fallback_to_initial and "Initial" in info:
            initial = info["Initial"]

            try:
                if isinstance(initial, dict):
                    value = sum(float(item) for item in initial.values())
                else:
                    value = float(initial)
            except (TypeError, ValueError):
                print(
                    f"[WARNING] Invalid Initial value in "
                    f"{json_path}: {initial!r}"
                )
                continue

            global_segmentation["return true;"] = (
                global_segmentation.get("return true;", 0.0) + value
            )

    if not global_segmentation and warn_if_missing:
        print(
            f"[WARNING] No segmentation JSON information found under: "
            f"{search_dir}"
        )

    return global_segmentation


# ****** RDF manipulation

from histograms.defineTriggerWeights import AddTriggerWeightsAndErrors

from .add_vars_to_skim_tuples import (
    GetAllMuonsObservablesNew,
    SelectedJetObservablesDef,
    SoftJetCollectionCleaningInVBF,
    VBFJetMuonsObservablesDef,
    VBFJetObservablesDef,
)


def _inverse_sum_expression(seg_dict):
    if len(seg_dict) == 1 and "return true;" in seg_dict:
        total_val = seg_dict["return true;"]
        return f"{1.0 / total_val}f" if total_val != 0.0 else "0.f"

    expression = "0.f"
    for selection, total_val in seg_dict.items():
        if total_val == 0.0:
            continue
        if selection.strip().lower() == "return true;":
            expression = f"{1.0 / total_val}f"
        else:
            expression = (
                f"({selection}) ? ({1.0 / total_val}f) : ({expression})"
            )
    return expression


def build_rdf(
    rdf,
    is_data,
    seg_dict,
    weight_dict,
    store_shifted_weights,
    dnn_payloads=None,
    btag_algo="PNet",
    era=None,
    qcd_scale_config=None,
    qcd_scale_seg_dicts=None,
    pdf_config=None,
):
    if not is_data:
        rdf = AddTriggerWeightsAndErrors(
            rdf,
            WantErrors=store_shifted_weights,
        )
        if seg_dict:
            rdf = rdf.Define("inv_N_orig", _inverse_sum_expression(seg_dict))

        if store_shifted_weights and pdf_config is not None:
            from corrections.pdf import define_pdf_weights

            rdf = define_pdf_weights(rdf, pdf_config)

    for weight_name_template, weight_info in weight_dict.items():
        if weight_info.get("derived_envelope", False):
            continue
        if weight_name_template == "Central":
            variations = [("Central", weight_info["expression"])]
        elif store_shifted_weights:
            weight_expression = weight_info.get("expression")
            if weight_expression is None:
                if "relative_expression" not in weight_info:
                    raise RuntimeError(
                        f"Weight '{weight_name_template}' has neither an "
                        "'expression' nor a 'relative_expression'"
                    )
                weight_expression = "1.f"
            if "{scale}" in weight_name_template:
                variations = [
                    (
                        weight_name_template.replace("{scale}", scale),
                        weight_expression.replace("{scale}", scale),
                    )
                    for scale in ("up", "down")
                ]
            else:
                variations = [(weight_name_template, weight_expression)]
        else:
            variations = []

        for weight_name, weight_expression in variations:
            relative_expression = weight_info.get("relative_expression")
            if relative_expression:
                scale = next(
                    (
                        candidate
                        for candidate in ("up", "down")
                        if weight_name
                        == weight_name_template.replace("{scale}", candidate)
                    ),
                    None,
                )
                if scale is None and "{scale}" in relative_expression:
                    raise RuntimeError(
                        f"Cannot resolve scale for relative weight '{weight_name}'"
                    )
                if scale is not None:
                    relative_expression = relative_expression.replace(
                        "{scale}", scale
                    )
                central_expression = weight_dict["Central"]["expression"]
                weight_expression = (
                    f"({central_expression}) * ({relative_expression})"
                )
            expr = "1.f" if is_data else f"({weight_expression}) * inv_N_orig"
            rdf = rdf.Define(f"weight__{weight_name}", expr)

    if (
        store_shifted_weights
        and qcd_scale_config is not None
        and qcd_scale_config.get("enabled", True)
    ):
        from corrections.qcd_scale import get_qcd_scale_points

        if is_data:
            for point in get_qcd_scale_points(qcd_scale_config):
                rdf = rdf.Define(
                    f"weight__QCDScale__{point['name']}",
                    "1.f",
                )
            qcd_scale_config = None

    if (
        not is_data
        and store_shifted_weights
        and qcd_scale_config is not None
        and qcd_scale_config.get("enabled", True)
    ):
        from corrections.qcd_scale import get_qcd_scale_points

        branch = qcd_scale_config.get("branch", "LHEScaleWeight")
        available_columns = {str(column) for column in rdf.GetColumnNames()}
        if branch not in available_columns:
            raise RuntimeError(
                f"QCD scale branch '{branch}' is missing from the skim"
            )
        central_expression = weight_dict["Central"]["expression"]
        for point in get_qcd_scale_points(qcd_scale_config):
            name = point["name"]
            index = int(point["index"])
            point_seg_dict = (qcd_scale_seg_dicts or {}).get(name, {})
            if not point_seg_dict:
                raise RuntimeError(
                    f"Missing qcd_scale__{name} sums in skim reports. "
                    "Reproduce the skim with --want-variations."
                )
            inv_column = f"inv_N_qcd_scale__{name}"
            rdf = rdf.Define(
                inv_column,
                _inverse_sum_expression(point_seg_dict),
            )
            rdf = rdf.Define(
                f"weight__QCDScale__{name}",
                f"({central_expression}) * "
                f"qcd_scale::weightAt({branch}, {index}u) * {inv_column}",
            )
    rdf = SelectedJetObservablesDef(rdf)
    rdf = VBFJetObservablesDef(rdf)
    rdf = GetAllMuonsObservablesNew(rdf)
    rdf = VBFJetMuonsObservablesDef(rdf)
    rdf = SoftJetCollectionCleaningInVBF(rdf)
    if dnn_payloads:
        from common.dnn_application import ApplyDNN

        rdf = ApplyDNN(rdf, dnn_payloads, btag_algo=btag_algo, era=era)
    return rdf


def GetRdfForDataset(
    input_dir,
    is_data,
    weight_dict,
    store_shifted_weights,
    treeName="Events",
    explicit_files=None,
    seg_dict=None,
    skip_validation=False,
    dnn_payloads=None,
    btag_algo="PNet",
    additional_cuts=None,
    era=None,
    qcd_scale_config=None,
    qcd_scale_seg_dicts=None,
    pdf_config=None,
):
    """
    Se explicit_files è una lista di file ROOT, RDataFrame caricherà SOLO quei file (chunk).
    Il seg_dict può essere fornito esternamente per evitare di ricalcolarlo in ogni chunk.
    """
    # 1. Calcola il denominatore globale guardando SEMPRE tutti i file JSON della cartella,
    #    a meno che non venga fornito già pre-calcolato.
    if seg_dict is None:
        seg_dict = get_segmentation_dict(input_dir)

    # 2. Seleziona i file ROOT da processare (tutti o solo il chunk richiesto)
    if explicit_files is not None:
        if isinstance(explicit_files, str):
            files_to_process = [explicit_files]
        else:
            files_to_process = explicit_files
    else:
        files_to_process = get_root_files(input_dir)

    if skip_validation:
        valid_files = files_to_process
    else:
        valid_files = get_valid_root_files(files_to_process, treeName)

    if len(valid_files) == 0:
        print("[WARNING] No valid ROOT files found for this chunk.")
        return None

    # 3. Inizializza l'RDataFrame solo sul chunk di file desiderato
    rdf = ROOT.RDataFrame("Events", utilities.ListToVector(valid_files))
    if additional_cuts:
        rdf = rdf.Filter(additional_cuts)
    # 4. Applica le definizioni e i pesi (usando il denominatore globale seg_dict)
    rdf_base = build_rdf(
        rdf,
        is_data,
        seg_dict,
        weight_dict,
        store_shifted_weights,
        dnn_payloads=dnn_payloads,
        btag_algo=btag_algo,
        era=era,
        qcd_scale_config=qcd_scale_config,
        qcd_scale_seg_dicts=qcd_scale_seg_dicts,
        pdf_config=pdf_config,
    )
    return rdf_base

# ****** histogram manipulation - from config

def findBinEntry(hist_cfg_dict, var_name):
    """
    Match variable name against regex-based histogram config entries.
    """

    matches = []

    for pattern in hist_cfg_dict.keys():
        if re.fullmatch(pattern, var_name):
            matches.append(pattern)

    if not matches:
        raise KeyError(f"No histogram config pattern matches variable '{var_name}'")

    if len(matches) > 1:
        raise RuntimeError(f"Ambiguous histogram config for '{var_name}': {matches}")

    return matches[0]

def findNewBins(hist_cfg_dict, var, **keys):
    cfg = hist_cfg_dict.get(var, {})
    if 'x_rebin' not in cfg: return cfg.get('x_bins', [])
    x_rebin = cfg['x_rebin']
    if isinstance(x_rebin, list): return x_rebin
    def recursive_search(d, remaining_keys):
        if isinstance(d, list): return d
        if not remaining_keys and isinstance(d, dict) and 'other' in d: return d['other']
        if not isinstance(d, dict): return None
        for k_name, k_value in remaining_keys.items():
            if k_value in d:
                found = recursive_search(d[k_value], {kk: vv for kk, vv in remaining_keys.items() if kk != k_name})
                if found is not None: return found
        return d.get('other') if isinstance(d, dict) else None
    return recursive_search(x_rebin, {k: v for k, v in keys.items() if v is not None}) or cfg.get('x_bins', [])

def GetModel(hist_cfg, var, dims):
    THModel_Inputs = []
    var_entry = findBinEntry(hist_cfg, var)
    if dims == 1:
        x_bins_vec = GetBinVec(hist_cfg[var_entry]["x_bins"])
        THModel_Inputs.append(x_bins_vec.size() - 1)
        THModel_Inputs.append(x_bins_vec.data())
        model = ROOT.RDF.TH1DModel("", "", *THModel_Inputs)
        # TH1DModel keeps the edge pointer rather than copying its storage.
        # Retain the vector for at least as long as the Python model wrapper.
        model._bin_vectors = [x_bins_vec]
        return model

    elif (dims == 2) or (dims == 3):
        list_var_bins_vec = []
        for var_nD in hist_cfg[var_entry]["var_list"]:
            var_bin_name = f"{var_nD}_bins"
            var_bins = (
                hist_cfg[var_entry][var_bin_name]
                if var_bin_name in hist_cfg[var_entry]
                else hist_cfg[var_nD]["x_bins"]
            )
            var_bins_vec = GetBinVec(var_bins)
            list_var_bins_vec.append(var_bins_vec)
            THModel_Inputs.append(var_bins_vec.size() - 1)
            THModel_Inputs.append(var_bins_vec.data())
        if dims == 2:
            model = ROOT.RDF.TH2DModel("", "", *THModel_Inputs)
            model._bin_vectors = list_var_bins_vec
            return model
        if dims == 3:
            model = ROOT.RDF.TH3DModel("", "", *THModel_Inputs)
            model._bin_vectors = list_var_bins_vec
            return model
            return model
    else:
        raise RuntimeError("nD histogram not implemented yet")
        # model = ROOT.RDF.THnDModel("", "", )

    return model


def getNewBins(bins):
    if isinstance(bins, list): return bins
    n_bins_str, bin_range = bins.split('|')
    start, stop = map(float, bin_range.split(':'))
    n_bins = int(n_bins_str)
    return [start + i * (stop - start) / n_bins for i in range(n_bins + 1)]

# ****** histogram manipulation - bins

def GetBinVec(x_bins):
    if isinstance(x_bins, dict):
        return x_bins

    x_bins_vec = None
    if not isinstance(x_bins, list):
        n_bins, bin_range = x_bins.split("|")
        start, stop = bin_range.split(":")
        x_bins = np.linspace(float(start), float(stop), int(n_bins) + 1).tolist()
    x_bins_vec = utilities.ListToVector(x_bins, "float")
    return x_bins_vec

# ****** histogram manipulation - histograms

def AdaptBinningToHistogram(hist, desired_binning):
    axis = hist.GetXaxis()
    original_edges = [axis.GetBinLowEdge(i) for i in range(1, axis.GetNbins() + 2)]
    adapted = []
    for x in desired_binning:
        idx = bisect.bisect_left(original_edges, x)
        if idx == 0: closest = original_edges[0]
        elif idx == len(original_edges): closest = original_edges[-1]
        else:
            before, after = original_edges[idx - 1], original_edges[idx]
            closest = before if abs(x - before) < abs(x - after) else after
        adapted.append(closest)
    return sorted(set(adapted))

def FixNegativeContributions(histogram):
    orig_integral = histogram.Integral(0, histogram.GetNbinsX() + 1)
    if orig_integral < 0:
        print(f"Integral negative for {histogram.GetName()}")
        return False, "", ""
    for n in range(1, histogram.GetNbinsX() + 1):
        if histogram.GetBinContent(n) < 0:
            error = abs(histogram.GetBinContent(n))
            new_error = math.sqrt(error**2 + histogram.GetBinError(n)**2)
            histogram.SetBinContent(n, 0)
            histogram.SetBinError(n, new_error)
    if orig_integral > 0: histogram.Scale(1.0)
    return True, "", ""

def RebinHisto(hist_initial, new_binning, sample, wantOverflow=True, verbose=False):
    adapted = AdaptBinningToHistogram(hist_initial, new_binning)
    if len(adapted) < 2: raise RuntimeError("Adapted binning < 2 edges!")
    new_hist = hist_initial.Rebin(len(adapted) - 1, sample, array.array('d', adapted))
    if sample == 'data': new_hist.SetBinErrorOption(ROOT.TH1.kPoisson)
    if wantOverflow:
        n_final = new_hist.GetBinContent(new_hist.GetNbinsX())
        n_over = new_hist.GetBinContent(new_hist.GetNbinsX() + 1)
        new_hist.SetBinContent(new_hist.GetNbinsX(), n_final + n_over)
    FixNegativeContributions(new_hist)
    return new_hist


def is_valid_histogram(hist, check_overflow=True):
    """
    Verifica che l'istogramma sia utilizzabile per il plotting.
    """

    if hist is None:
        return False

    if not hist.InheritsFrom("TH1"):
        return False

    n_bins = hist.GetNbinsX()

    total_content = 0.0

    first_bin = 0 if check_overflow else 1
    last_bin  = n_bins + 1 if check_overflow else n_bins

    for ibin in range(first_bin, last_bin + 1):

        content = hist.GetBinContent(ibin)
        error   = hist.GetBinError(ibin)

        if not np.isfinite(content):
            return False

        if not np.isfinite(error):
            return False

        total_content += abs(content)

    return total_content > 0
