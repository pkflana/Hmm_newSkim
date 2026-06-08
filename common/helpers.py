
import math
import ROOT, re, array, math, numpy as np, bisect
import os
import sys
import json

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])
import common.utilities as utilities


# ****** root / json files manipulation
def is_valid_root_file(filename, tree_name="Events"):
    try:
        f = ROOT.TFile.Open(filename)
        if not f or f.IsZombie():
            return False
        tree = f.Get(tree_name)
        if tree is None:
            f.Close()
            return False
        if tree.GetEntries() == 0:
            f.Close()
            return False
        f.Close()
        return True
    except Exception:
        return False

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
            files.append(
                os.path.join(root, f)
            )
    return sorted(files)


# ****** dictionary for denum definition
def get_segmentation_dict(input_dir, node="gen"):
    global_segmentation = {}

    for root, _, files in os.walk(input_dir):
        for f in files:
            if not f.endswith(".json"):
                continue
            with open(os.path.join(root, f)) as jf:
                try:
                    info = json.load(jf)
                except Exception as e:
                    print(f"[WARNING] Errore nel parsing del file JSON {f}: {e}")
                    continue

            # Controlliamo se esiste il blocco centrale 'pu'
            if node in info and isinstance(info[node], dict):
                node_dict = info[node]

                # Se ci sono più chiavi di 'total', o se 'total' non c'è, è un file DY segmentato
                has_fine_segmentation = len(node_dict) > 1 #or "total" not in node_dict
                if has_fine_segmentation:
                    # File DY: cicliamo sulle sotto-selezioni ignorando il total cumulativo interno
                    for sub_key, sub_info in node_dict.items():
                        if sub_key == "total":
                            continue
                        selection = sub_info.get("selection")
                        val = float(sub_info.get("value", 0.0))
                        if selection:
                            global_segmentation[selection] = global_segmentation.get(selection, 0.0) + val
                else:
                    # File non-DY: prendiamo direttamente la chiave 'total' dentro 'pu'
                    total_node = node_dict["total"]
                    selection = total_node.get("selection", "return true;")
                    val = float(total_node.get("value", 0.0))
                    global_segmentation[selection] = global_segmentation.get(selection, 0.0) + val

            # Fallback su 'Initial' se manca completamente il blocco 'pu'
            elif "Initial" in info:
                init_val = info["Initial"]
                val = float(init_val) if not isinstance(init_val, dict) else sum(float(v) for v in init_val.values())
                global_segmentation["return true;"] = global_segmentation.get("return true;", 0.0) + val

    return global_segmentation


# ****** RDF manipulation

from histograms.defineTriggerWeights import AddTriggerWeightsAndErrors
from .add_vars_to_skim_tuples import SelectedJetObservablesDef,VBFJetObservablesDef,GetAllMuonsObservablesNew,SoftJetCollectionCleaningInVBF,VBFJetMuonsObservablesDef

def build_rdf(rdf, is_data, seg_dict,weight_dict, store_shifted_weights, dnn_payloads=None, btag_algo="PNet"):
    if not is_data:
        rdf = AddTriggerWeightsAndErrors(
            rdf,
            WantErrors=False
        )
        if seg_dict:
            if len(seg_dict) == 1 and "return true;" in seg_dict:
                total_val = seg_dict["return true;"]
                # print(total_val)
                ternary_expr = f"{1.0 / total_val}f" if total_val > 0.0 else "0.f"
            else:
                # Se ci sono selezioni cinematiche (file DY segmentati presenti nel mix)
                ternary_expr = "0.f"
                for selection, total_val in seg_dict.items():
                    if total_val <= 0.0:
                        continue
                    if selection.strip().lower() == "return true;":
                        # Il return true fa da blocco di fallback finale al posto di 0.f
                        ternary_expr = f"{1.0 / total_val}f"
                    else:
                        ternary_expr = f"({selection}) ? ({1.0 / total_val}f) : ({ternary_expr})"
            rdf = rdf.Define("inv_N_orig", ternary_expr)


    for weight_name, weight_info in weight_dict.items():
        scales = ['central','up','down'] if store_shifted_weights else ['central']
        for scale in scales:
            if weight_name == 'Central' and scale != 'central': continue
            if weight_name != 'Central' and scale == 'central': continue
            if weight_name != 'Central': weight_name = weight_name.format(scale=scale)
            # print(weight_info['expression'])
            expr = "1.f" if is_data else f"({weight_info['expression']}) * inv_N_orig"
            rdf = rdf.Define(f"weight__{weight_name}", expr)
            # rdf.Display({f"weight__{weight_name}","inv_N_orig"}).Print()
    rdf = SelectedJetObservablesDef(rdf)
    rdf = VBFJetObservablesDef(rdf)
    rdf = GetAllMuonsObservablesNew(rdf)
    rdf = VBFJetMuonsObservablesDef(rdf)
    rdf = SoftJetCollectionCleaningInVBF(rdf)
    if dnn_payloads:
        from common.dnn_application import ApplyDNN
        rdf = ApplyDNN(rdf, dnn_payloads, btag_algo=btag_algo)
    return rdf


def GetRdfForDataset(input_dir, is_data, weight_dict, store_shifted_weights, treeName="Events", explicit_files=None, seg_dict=None, skip_validation=False, dnn_payloads=None, btag_algo="PNet"):
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

    # 4. Applica le definizioni e i pesi (usando il denominatore globale seg_dict)
    rdf_base = build_rdf(rdf, is_data, seg_dict, weight_dict, store_shifted_weights, dnn_payloads=dnn_payloads, btag_algo=btag_algo)
    return rdf_base

# def GetRdfForDataset(input_dir, is_data, weight_dict, store_shifted_weights, treeName="Events"):
#     input_files = get_valid_root_files(get_root_files(input_dir), treeName)
#     if len(input_files)==0 :
#         print("[WARNING] No valid ROOT files with non-empty Events tree found.")
#         return None
#     rdf = ROOT.RDataFrame("Events", utilities.ListToVector(input_files))
#     seg_dict = get_segmentation_dict(input_dir)
#     # print(seg_dict)
#     rdf_base = build_rdf(rdf, is_data, seg_dict,weight_dict,store_shifted_weights)
#     return rdf_base

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
    unit_bin_Inputs = []
    var_entry = findBinEntry(hist_cfg, var)
    if dims == 1:
        x_bins_vec = GetBinVec(hist_cfg[var_entry]["x_bins"])
        THModel_Inputs.append(x_bins_vec.size() - 1)
        THModel_Inputs.append(x_bins_vec.data())
        model = ROOT.RDF.TH1DModel("", "", *THModel_Inputs)
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
            return model
        if dims == 3:
            model = ROOT.RDF.TH3DModel("", "", *THModel_Inputs)
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
