#!/usr/bin/env python3

import ROOT
import sys
import os
import argparse
import time
import traceback
import subprocess
from multiprocessing import get_context

# =========================================================
# ROOT setup
# =========================================================

ROOT.gROOT.SetBatch(True)
ROOT.EnableThreadSafety()

sys.path.append(os.environ["ANALYSIS_PATH"])

import common.utilities as utilities
from common.helpers import (
    GetModel,
    GetRdfForDataset,
    get_root_files,
    get_valid_root_files,
    get_segmentation_dict,
)

# =========================================================
# C++ headers
# =========================================================

HEADERS = ["analysis/AnalysisTools.h"]

for header in HEADERS:
    utilities.DeclareHeader(f"{os.environ['ANALYSIS_PATH']}/{header}")


# =========================================================
# Utilities
# =========================================================

def chunk_list(items, chunk_size):
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def safe_mkdir(path):
    if path:
        os.makedirs(path, exist_ok=True)


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


def remove_file_if_exists(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"[WARNING] Could not remove temporary file {path}: {e}")


# =========================================================
# Worker
# =========================================================

def process_single_chunk(args_tuple):
    """
    Process one chunk of ROOT files and save a temporary histogram file.

    Important:
    - This function runs inside a separate process.
    - Avoid global mutable ROOT objects here.
    - Any exception is re-raised after printing the failing files.
    """

    (
        chunk_index,
        chunk_files,
        args,
        is_data,
        syst_cfg,
        vars_to_make_hist,
        masses_regions,
        masses_regions_list,
        categories,
        categories_list,
        hist_cfg,
        systs_to_run,
        seg_dict,
        dnn_payloads,
        btag_algo,
    ) = args_tuple

    tmp_output = f"{args.output_file}.tmp_{chunk_index}.root"

    try:
        print(f"[CHUNK {chunk_index}] Starting with {len(chunk_files)} file(s)")
        for f in chunk_files:
            print(f"[CHUNK {chunk_index}]   {f}")

        rdf_base = GetRdfForDataset(
            input_dir=args.input,
            is_data=is_data,
            weight_dict=syst_cfg["weights"],
            store_shifted_weights=False,
            treeName="Events",
            explicit_files=chunk_files,
            seg_dict=seg_dict,
            skip_validation=True,
            dnn_payloads=dnn_payloads,
            btag_algo=btag_algo,
        )

        if rdf_base is None:
            print(f"[CHUNK {chunk_index}] WARNING: rdf_base is None, writing empty histograms")

        outFile = ROOT.TFile(tmp_output, "RECREATE")
        if not outFile or outFile.IsZombie():
            raise RuntimeError(f"Could not create output file: {tmp_output}")

        booked_hists = []

        for syst_name, syst_info in systs_to_run.items():
            weight_name = syst_info["weight"]

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
                        available_columns = set(str(c) for c in rdf_for_category.GetColumnNames())

                        if category not in available_columns:
                            rdf_for_category = rdf_for_category.Define(
                                category,
                                cat_info["expression"],
                            )

                        rdf_filtered = rdf_for_category.Filter(
                            f"{mass_region} && {category}",
                            f"{mass_region}_{category}",
                        )
                    else:
                        rdf_filtered = None

                    dir_ptr = utilities.mkdir_recursive(
                        outFile,
                        f"{mass_region}_{category}",
                    )

                    for var in vars_to_make_hist:
                        model = GetModel(hist_cfg, var, dims=1)
                        hist_name = var if syst_name == "Central" else f"{var}_{syst_name}"

                        if rdf_filtered is not None:
                            available_columns = set(str(c) for c in rdf_filtered.GetColumnNames())

                            if var not in available_columns:
                                print(
                                    f"[CHUNK {chunk_index}] WARNING: variable '{var}' "
                                    f"not found. Booking empty histogram."
                                )

                                hist = ROOT.TH1D(
                                    hist_name,
                                    hist_name,
                                    model.fNbinsX,
                                    model.fXLow,
                                    model.fXUp,
                                )
                                hist.SetDirectory(0)
                                booked_hists.append((dir_ptr, hist_name, hist, False))
                                continue

                            if weight_name not in available_columns:
                                raise RuntimeError(
                                    f"Weight column '{weight_name}' not found for systematic '{syst_name}'"
                                )

                            hist_ptr = rdf_filtered.Histo1D(model, var, weight_name)
                            booked_hists.append((dir_ptr, hist_name, hist_ptr, True))

                        else:
                            hist = ROOT.TH1D(
                                hist_name,
                                hist_name,
                                model.fNbinsX,
                                model.fXLow,
                                model.fXUp,
                            )
                            hist.SetDirectory(0)
                            booked_hists.append((dir_ptr, hist_name, hist, False))

        print(f"[CHUNK {chunk_index}] Booked {len(booked_hists)} histograms. Running event loop...")

        for dir_ptr, hist_name, hist_obj, needs_getvalue in booked_hists:
            if needs_getvalue:
                hist = hist_obj.GetValue()
            else:
                hist = hist_obj

            hist.SetName(hist_name)
            hist.SetTitle(hist_name)
            hist.SetDirectory(0)

            dir_ptr.cd()
            dir_ptr.WriteTObject(hist, hist_name, "Overwrite")

        outFile.Close()

        print(f"[CHUNK {chunk_index}] Done -> {tmp_output}")
        return tmp_output

    except Exception as e:
        print_chunk_error(chunk_index, chunk_files, e)
        remove_file_if_exists(tmp_output)
        raise


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("--era", required=True, type=str)
    parser.add_argument("--input", required=True, type=str, help="ROOT file or dataset directory")
    parser.add_argument("--dataset-name", "--dataset", dest="dataset_name", required=True, type=str)
    parser.add_argument("--output-file", required=True, type=str)
    parser.add_argument("--systematics", choices=["central", "all"], default="central")

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=4,
        help="Number of ROOT files per chunk",
    )

    parser.add_argument(
        "--n-cores",
        type=int,
        default=4,
        help="Number of independent processes",
    )

    parser.add_argument(
        "--skip-file-validation",
        action="store_true",
        help="Do not open all ROOT files before histogramming",
    )

    parser.add_argument(
        "--variables",
        nargs="+",
        help="Variables to histogram instead of those in maincfg.yaml",
    )

    parser.add_argument(
        "--mass-regions",
        nargs="+",
        default=["mass_inclusive", "Z_sideband", "Signal_Fit"],
        help="Mass regions to histogram",
    )

    parser.add_argument(
        "--categories",
        nargs="+",
        default=["baseline", "ggF", "VBF"],
        help="Categories to histogram",
    )

    parser.add_argument(
        "--dryrun",
        action="store_true",
        help="Only print files/chunks and exit",
    )

    parser.add_argument(
        "--keep-tmp",
        action="store_true",
        help="Keep temporary ROOT files after hadd",
    )

    parser.add_argument(
        "--force-multiprocessing-with-dnn",
        action="store_true",
        help="Allow n_cores > 1 even when DNN payloads are requested",
    )

    parser.add_argument(
        "--multiprocessing-method",
        choices=["spawn", "fork"],
        default="spawn",
        help="Multiprocessing start method. spawn is safer, fork is lighter.",
    )

    args = parser.parse_args()

    startTime = time.time()

    if args.chunk_size < 1:
        raise ValueError("--chunk-size must be >= 1")

    if args.n_cores < 1:
        raise ValueError("--n-cores must be >= 1")

    # =====================================================
    # Load configuration
    # =====================================================

    analysis_path = os.environ["ANALYSIS_PATH"]
    cfg_dir = os.path.join(analysis_path, "config", args.era)

    main_cfg = utilities.get_config(os.path.join(cfg_dir, "maincfg.yaml"))

    samples_cfg = utilities.get_config(os.path.join(cfg_dir, "samples.yaml"))
    dataset_cfg = samples_cfg.get(args.dataset_name, {})

    is_data = (
        dataset_cfg.get("is_data", False)
        or "data" in args.dataset_name.lower()
    )

    sel_cfg = utilities.get_config(os.path.join(cfg_dir, "selections.yaml"))
    syst_cfg = utilities.get_config(os.path.join(cfg_dir, "systematics.yaml"))

    hist_cfg = utilities.get_config(
        os.path.join(analysis_path, "config", "plot", "histograms.yaml")
    )

    masses_regions = sel_cfg["masses_regions"]
    categories = sel_cfg["categories"]

    masses_regions_list = args.mass_regions
    categories_list = args.categories

    vars_to_make_hist = list(dict.fromkeys(args.variables or main_cfg["variables"]))

    dnn_payloads = sorted({
        var.rsplit("_NNOutput", 1)[0]
        for var in vars_to_make_hist
        if var.endswith("_NNOutput")
    })

    btag_algo = main_cfg.get("bTagAlgo", "PNet")

    print("\n" + "=" * 80)
    print("[INFO] Histogram maker configuration")
    print(f"[INFO] Era:              {args.era}")
    print(f"[INFO] Dataset:          {args.dataset_name}")
    print(f"[INFO] Is data:          {is_data}")
    print(f"[INFO] Input:            {args.input}")
    print(f"[INFO] Output:           {args.output_file}")
    print(f"[INFO] Systematics:      {args.systematics}")
    print(f"[INFO] Chunk size:       {args.chunk_size}")
    print(f"[INFO] Requested cores:  {args.n_cores}")
    print(f"[INFO] Variables:        {vars_to_make_hist}")
    print(f"[INFO] Mass regions:     {masses_regions_list}")
    print(f"[INFO] Categories:       {categories_list}")
    print(f"[INFO] DNN payloads:     {dnn_payloads}")
    print(f"[INFO] bTag algo:        {btag_algo}")
    print("=" * 80 + "\n")

    # =====================================================
    # Protect against DNN + multiprocessing memory explosion
    # =====================================================

    if len(dnn_payloads) > 0 and args.n_cores > 1 and not args.force_multiprocessing_with_dnn:
        print(
            "[WARNING] DNN payloads requested. "
            "Forcing n_cores = 1 to avoid AsNumpy / CLING memory problems."
        )
        print(
            "[WARNING] To override this, use --force-multiprocessing-with-dnn, "
            "but this may crash for large files."
        )
        args.n_cores = 1

    # =====================================================
    # Systematics
    # =====================================================

    systs_to_run = {
        "Central": syst_cfg["systematics"]["Central"]
    }

    if args.systematics != "central":
        systs_to_run.update(syst_cfg["systematics"])
        systs_to_run.update(syst_cfg["weights"])

    print(f"[INFO] Systematics to run: {list(systs_to_run.keys())}")

    # =====================================================
    # Input files
    # =====================================================

    all_root_files = get_root_files(args.input)

    if args.skip_file_validation:
        valid_root_files = all_root_files
    else:
        valid_root_files = get_valid_root_files(
            all_root_files,
            tree_name="Events",
        )

    seg_dict = get_segmentation_dict(args.input)

    print(
        f"\n[INFO] Dataset {args.dataset_name}: "
        f"{len(valid_root_files)} valid ROOT files out of {len(all_root_files)} total."
    )

    if len(valid_root_files) == 0:
        print("[ERROR] No valid ROOT files found. Exiting.")
        sys.exit(1)

    chunks = chunk_list(valid_root_files, args.chunk_size)

    print(
        f"[INFO] Splitting into {len(chunks)} chunks "
        f"with chunk-size = {args.chunk_size}"
    )
    print(f"[INFO] Running with n_cores = {args.n_cores}")

    if args.dryrun:
        print("\n[DRYRUN] Chunks:")
        for idx, chunk_files in enumerate(chunks):
            print(f"\n[DRYRUN] Chunk {idx}: {len(chunk_files)} file(s)")
            for f in chunk_files:
                print(f"  {f}")
        print("\n[DRYRUN] Exiting without processing.")
        sys.exit(0)

    # =====================================================
    # Prepare output directory
    # =====================================================

    output_dir = os.path.dirname(args.output_file)
    safe_mkdir(output_dir)

    # Remove final output if existing, to avoid confusion
    if os.path.exists(args.output_file):
        print(f"[INFO] Removing existing output file: {args.output_file}")
        os.remove(args.output_file)

    # Remove stale tmp files
    for idx in range(len(chunks)):
        stale_tmp = f"{args.output_file}.tmp_{idx}.root"
        remove_file_if_exists(stale_tmp)

    # =====================================================
    # Prepare worker inputs
    # =====================================================

    pool_inputs = []

    for idx, chunk_files in enumerate(chunks):
        pool_inputs.append((
            idx,
            chunk_files,
            args,
            is_data,
            syst_cfg,
            vars_to_make_hist,
            masses_regions,
            masses_regions_list,
            categories,
            categories_list,
            hist_cfg,
            systs_to_run,
            seg_dict,
            dnn_payloads,
            btag_algo,
        ))

    # =====================================================
    # Run chunks
    # =====================================================

    tmp_files = []

    print("\n[INFO] Starting chunk processing...\n")

    try:
        if args.n_cores == 1:
            for item in pool_inputs:
                tmp = process_single_chunk(item)
                tmp_files.append(tmp)
                print(f"[INFO] Finished chunk -> {tmp}")

        else:
            ctx = get_context(args.multiprocessing_method)

            with ctx.Pool(processes=args.n_cores) as pool:
                for tmp in pool.imap_unordered(
                    process_single_chunk,
                    pool_inputs,
                    chunksize=1,
                ):
                    tmp_files.append(tmp)
                    print(f"[INFO] Finished chunk -> {tmp}")

    except Exception:
        print("\n[ERROR] At least one chunk failed. Not running hadd.")
        print("[ERROR] Temporary files already produced will be kept for inspection:")
        for tmp in tmp_files:
            print(f"  {tmp}")
        sys.exit(1)

    if len(tmp_files) == 0:
        print("[ERROR] No temporary files were produced. Exiting.")
        sys.exit(1)

    print("\n[INFO] All chunks finished successfully.")
    print(f"[INFO] Produced {len(tmp_files)} temporary files.")

    # =====================================================
    # Merge with hadd
    # =====================================================

    print(f"\n[INFO] Merging temporary files into: {args.output_file}")

    hadd_cmd = ["hadd", "-f", args.output_file] + tmp_files

    print("[INFO] Running:")
    print(" ".join(hadd_cmd))

    result = subprocess.run(hadd_cmd)

    if result.returncode != 0:
        print("[ERROR] hadd failed.")
        print("[ERROR] Temporary files are kept for inspection:")
        for tmp in tmp_files:
            print(f"  {tmp}")
        sys.exit(result.returncode)

    print("[INFO] hadd completed successfully.")

    # =====================================================
    # Cleanup
    # =====================================================

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
    print(f"[INFO] Execution time: {executionTime:.2f} s")
    print("=" * 80 + "\n")
    
# #!/usr/bin/env python3

# import ROOT
# import sys
# import os
# import argparse
# import time
# from multiprocessing import get_context
# sys.path.append(os.environ["ANALYSIS_PATH"])
# # ROOT.EnableImplicitMT(8)
# ROOT.EnableThreadSafety()

# import common.utilities as utilities
# from common.helpers import GetModel, GetRdfForDataset, get_root_files, get_valid_root_files, get_segmentation_dict

# # Declarazione degli header C++
# HEADERS = ["analysis/AnalysisTools.h"]
# for header in HEADERS:
#     utilities.DeclareHeader(f"{os.environ['ANALYSIS_PATH']}/{header}")


# def process_single_chunk(args_tuple):
#     """
#     Funzione eseguita in parallelo dai vari core della CPU.
#     Processa un singolo chunk di file e salva un file ROOT temporaneo.
#     """
#     chunk_index, chunk_files, args, is_data, syst_cfg, vars_to_make_hist, masses_regions, masses_regions_list, categories, categories_list, hist_cfg, systs_to_run, seg_dict, dnn_payloads, btag_algo = args_tuple

#     rdf_base = GetRdfForDataset(
#         input_dir=args.input,
#         is_data=is_data,
#         weight_dict=syst_cfg['weights'],
#         store_shifted_weights=False,
#         treeName="Events",
#         explicit_files=chunk_files,
#         seg_dict=seg_dict,
#         skip_validation=True,
#         dnn_payloads=dnn_payloads,
#         btag_algo=btag_algo
#     )

#     tmp_output = f"{args.output_file}.tmp_{chunk_index}"
#     outFile = ROOT.TFile(tmp_output, "RECREATE")
#     booked_hists = []

#     for syst_name, syst_info in systs_to_run.items():
#         weight_name = syst_info["weight"]

#         for mass_region, mass_info in masses_regions.items():
#             if mass_region not in masses_regions_list: continue
#             if not mass_info["store"]: continue
#             for category, cat_info in categories.items():
#                 if category not in categories_list: continue
#                 if category not in rdf_base.GetColumnNames():
#                     rdf_base=rdf_base.Define(category, cat_info['expression'])
#                 if not cat_info["store"]: continue

#                 dir_ptr = utilities.mkdir_recursive(outFile, f"{mass_region}_{category}")
#                 rdf_filtered = rdf_base.Filter(f"{mass_region} && {category}") if rdf_base is not None else None
#                 for var in vars_to_make_hist:
#                     model = GetModel(hist_cfg, var, dims=1)
#                     hist_name = var if syst_name == "Central" else f"{var}_{syst_name}"
#                     if rdf_base is not None:
#                         hist = rdf_filtered.Histo1D(model, var, weight_name)
#                     else:
#                         hist = ROOT.TH1D(hist_name, hist_name, model.fNbinsX, model.fXLow, model.fXUp)
#                     booked_hists.append((dir_ptr, hist_name, hist))

#     for dir_ptr, hist_name, hist_ptr in booked_hists:
#         if rdf_base is not None:
#             hist = hist_ptr.GetValue()
#         else:
#             hist = hist_ptr
#         hist.SetName(hist_name)
#         hist.SetTitle(hist_name)
#         hist.SetDirectory(0)
#         dir_ptr.WriteTObject(hist, hist_name, "Overwrite")

#     outFile.Close()
#     return tmp_output


# if __name__ == "__main__":
#     parser = argparse.ArgumentParser()
#     parser.add_argument( "--era", required=True, type=str)
#     parser.add_argument( "--input", required=True, type=str, help="ROOT file or dataset directory")
#     parser.add_argument( "--dataset-name", "--dataset", dest="dataset_name", required=True, type=str)
#     parser.add_argument( "--output-file", required=True, type=str)
#     parser.add_argument( "--systematics", choices=["central", "all"], default="central")

#     # Nuovi parametri per il controllo locale
#     parser.add_argument( "--chunk-size", type=int, default=4, help="Quanti file ROOT per ogni chunk")
#     parser.add_argument( "--n-cores", type=int, default=4, help="Quanti processi separati usare in parallelo")
#     parser.add_argument( "--skip-file-validation", action="store_true", help="Non aprire tutti i file prima di costruire gli istogrammi")
#     parser.add_argument( "--variables", nargs="+", help="Variabili da istogrammare al posto di quelle in maincfg.yaml")
#     parser.add_argument( "--mass-regions", nargs="+", default=["mass_inclusive", "Z_sideband", "Signal_Fit"], help="Regioni di massa da istogrammare")
#     parser.add_argument( "--categories", nargs="+", default=["baseline", "ggF", "VBF"], help="Categorie da istogrammare")
#     args = parser.parse_args()

#     startTime = time.time()

#     cfg_dir = os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era)
#     main_cfg = utilities.get_config(os.path.join(cfg_dir, "maincfg.yaml"))
#     dataset_cfg = utilities.get_config(os.path.join(cfg_dir, "samples.yaml")).get(args.dataset_name, {})
#     is_data = dataset_cfg.get("is_data", False) or "data" in args.dataset_name or "Data" in args.dataset_name
#     sel_cfg = utilities.get_config(os.path.join(cfg_dir, "selections.yaml"))
#     syst_cfg = utilities.get_config(os.path.join(cfg_dir, "systematics.yaml"))
#     hist_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", "plot", "histograms.yaml"))

#     masses_regions = sel_cfg["masses_regions"]
#     categories = sel_cfg["categories"]
#     masses_regions_list = args.mass_regions
#     categories_list = args.categories
#     vars_to_make_hist = list(dict.fromkeys(args.variables or main_cfg["variables"]))
#     dnn_payloads = sorted({
#         var.rsplit("_NNOutput", 1)[0]
#         for var in vars_to_make_hist
#         if var.endswith("_NNOutput")
#     })

#     systs_to_run = {"Central": syst_cfg["systematics"]["Central"]}
#     if args.systematics != 'central':
#         systs_to_run.update(syst_cfg['systematics'])
#         systs_to_run.update(syst_cfg['weights'])

#     # -----------------------------------------------------------------
#     # Logica di Chunking Locale con multiprocessing spawn
#     # -----------------------------------------------------------------
#     all_root_files = get_root_files(args.input)
#     valid_root_files = all_root_files if args.skip_file_validation else get_valid_root_files(all_root_files, tree_name="Events")
#     seg_dict = get_segmentation_dict(args.input)

#     print(f"\n[INFO] Dataset {args.dataset_name} contiene {len(valid_root_files)} file ROOT validi su {len(all_root_files)} file totali.")
#     print(f"[INFO] Divido in chunk di dimensione {args.chunk_size} usando {args.n_cores} processi separati in parallelo...")

#     if len(valid_root_files) == 0:
#         print("[ERROR] Nessun file ROOT valido trovato. Esco.")
#         sys.exit(1)

#     chunks = [valid_root_files[i:i + args.chunk_size] for i in range(0, len(valid_root_files), args.chunk_size)]
#     pool_inputs = []
#     for idx, chunk_files in enumerate(chunks):
#         pool_inputs.append((
#             idx, chunk_files, args, is_data, syst_cfg, vars_to_make_hist,
#             masses_regions, masses_regions_list, categories, categories_list, hist_cfg, systs_to_run, seg_dict, dnn_payloads, main_cfg.get("bTagAlgo", "PNet")
#         ))

#     ctx = get_context('spawn')
#     tmp_files = []
#     with ctx.Pool(processes=args.n_cores) as pool:
#         tmp_files = pool.map(process_single_chunk, pool_inputs)

#     print("\n[INFO] Tutti i chunk sono stati elaborati con successo.")
#     print(f"[INFO] Unisco i {len(tmp_files)} file temporanei in {args.output_file}...")

#     output_dir = os.path.dirname(args.output_file)
#     if output_dir:
#         os.makedirs(output_dir, exist_ok=True)
#     hadd_cmd = f"hadd -f {args.output_file} " + " ".join(tmp_files)
#     exit_code = os.system(hadd_cmd)

#     if exit_code == 0:
#         print("[INFO] Unione completata. Pulisco i file temporanei...")
#         for tmp_f in tmp_files:
#             if os.path.exists(tmp_f):
#                 os.remove(tmp_f)
#     else:
#         print("[ERROR] Errore durante l'esecuzione di hadd!")

#     executionTime = time.time() - startTime
#     print(f"\nExecution time: {executionTime:.2f} s")
