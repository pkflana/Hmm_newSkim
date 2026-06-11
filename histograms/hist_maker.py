#!/usr/bin/env python3

import ROOT
import sys
import os
import argparse
import time
import traceback
import subprocess
from multiprocessing import get_context

ROOT.gROOT.SetBatch(True)
ROOT.EnableThreadSafety()

sys.path.append(os.environ["ANALYSIS_PATH"])

import common.utilities as utilities
from common.helpers import GetModel,GetRdfForDataset,get_root_files,get_valid_root_files,get_segmentation_dict,is_valid_tmp_root
HEADERS = ["analysis/AnalysisTools.h"]
for header in HEADERS:
    utilities.DeclareHeader(f"{os.environ['ANALYSIS_PATH']}/{header}")

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

def process_single_chunk(args_tuple):
    (chunk_index,n_chunks,chunk_files,args,is_data,syst_cfg,vars_to_make_hist,masses_regions,masses_regions_list,categories,categories_list,hist_cfg,systs_to_run,dnn_payloads,btag_algo) = args_tuple
    tmp_output = f"{args.output_file}.tmp_{chunk_index}.root"
    try:
        print(f"[CHUNK {chunk_index} / {n_chunks}] Starting with {len(chunk_files)} file(s)")
        # for f in chunk_files:
        #     print(f"[CHUNK {chunk_index}]   {f}")
        chunk_seg_dict = get_segmentation_dict(args.input)# ,root_files=chunk_files)
        print(f"[CHUNK {chunk_index} / {n_chunks}] Using {len(chunk_seg_dict)} segmentation entries for {len(chunk_files)} ROOT file(s)")

        rdf_base = GetRdfForDataset(input_dir=args.input,is_data=is_data,weight_dict=syst_cfg["weights"],store_shifted_weights=False,treeName="Events",explicit_files=chunk_files,seg_dict=chunk_seg_dict,skip_validation=True,dnn_payloads=dnn_payloads,btag_algo=btag_algo,additional_cuts = args.additional_cuts)

        if rdf_base is None:
            print(f"[CHUNK {chunk_index} / {n_chunks}] WARNING: rdf_base is None. Writing empty histograms.")

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
                            rdf_for_category = rdf_for_category.Define(category,cat_info["expression"].format(tot_suff=""))
                        rdf_filtered = rdf_for_category.Filter(f"{mass_region} && {category}",f"{mass_region}_{category}")
                    else:
                        rdf_filtered = None
                    dir_ptr = utilities.mkdir_recursive(outFile,f"{mass_region}_{category}")
                    for var in vars_to_make_hist:
                        model = GetModel(hist_cfg, var, dims=1)
                        hist_name = var if syst_name == "Central" else f"{var}_{syst_name}"
                        if rdf_filtered is not None:
                            available_columns = set(str(c) for c in rdf_filtered.GetColumnNames())
                            if var not in available_columns:
                                print(f"[CHUNK {chunk_index}] WARNING: variable '{var}' not found. Booking empty histogram.")
                                hist = ROOT.TH1D(hist_name,hist_name,model.fNbinsX,model.fXLow,model.fXUp)
                                hist.SetDirectory(0)
                                booked_hists.append((dir_ptr, hist_name, hist, False))
                                continue
                            if weight_name not in available_columns:
                                raise RuntimeError(f"Weight column '{weight_name}' not found for systematic '{syst_name}'")
                            hist_ptr = rdf_filtered.Histo1D(model, var, weight_name)
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
    parser.add_argument("--dataset-name", "--dataset", dest="dataset_name", required=True, type=str)
    parser.add_argument("--output-file", required=True, type=str)
    parser.add_argument("--systematics", choices=["central", "all"], default="central")
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
    args = parser.parse_args()
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
    if len(dnn_payloads) > 0 and args.n_cores > 1 and not args.force_multiprocessing_with_dnn:
        print("[WARNING] DNN payloads requested: forcing n_cores = 1.")
        args.n_cores = 1
    systs_to_run = {
        "Central": syst_cfg["systematics"]["Central"]
    }
    if args.systematics != "central":
        systs_to_run.update(syst_cfg["systematics"])
        systs_to_run.update(syst_cfg["weights"])
    all_root_files = get_root_files(args.input)
    if args.skip_file_validation:
        valid_root_files = all_root_files
    else:
        valid_root_files = get_valid_root_files(all_root_files, tree_name="Events")
    valid_root_files = [os.path.abspath(f) for f in valid_root_files]
    if len(valid_root_files) == 0:
        print("[ERROR] No valid ROOT files found. Exiting.")
        sys.exit(1)
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
            chunk_seg_dict = get_segmentation_dict(args.input, root_files=chunk_files)
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
        pool_inputs.append((idx,n_chunks,chunk_files,args,is_data,syst_cfg,vars_to_make_hist,masses_regions,masses_regions_list,categories,categories_list,hist_cfg,systs_to_run,dnn_payloads,btag_algo))
    tmp_files = []
    failed_chunks = []
    print("\n[INFO] Starting chunk processing...\n")

    def handle_success(tmp):
        tmp_files.append(tmp)
        print(f"[INFO] Finished chunk -> {tmp}")

    if args.n_cores == 1:
        for item in pool_inputs:
            chunk_index = item[0]
            chunk_files = item[1]
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
