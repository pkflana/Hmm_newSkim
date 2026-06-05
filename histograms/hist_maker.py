#!/usr/bin/env python3

import ROOT
import sys
import os
import argparse
import time
from multiprocessing import get_context
sys.path.append(os.environ["ANALYSIS_PATH"])
ROOT.EnableImplicitMT(8)

import common.utilities as utilities
from common.helpers import GetModel, GetRdfForDataset, get_root_files, get_valid_root_files, get_segmentation_dict

# Declarazione degli header C++
HEADERS = ["analysis/AnalysisTools.h"]
for header in HEADERS:
    utilities.DeclareHeader(f"{os.environ['ANALYSIS_PATH']}/{header}")


def process_single_chunk(args_tuple):
    """
    Funzione eseguita in parallelo dai vari core della CPU.
    Processa un singolo chunk di file e salva un file ROOT temporaneo.
    """
    chunk_index, chunk_files, args, is_data, syst_cfg, vars_to_make_hist, masses_regions, masses_regions_list, categories, categories_list, hist_cfg, systs_to_run, seg_dict, dnn_payloads, btag_algo = args_tuple

    rdf_base = GetRdfForDataset(
        input_dir=args.input,
        is_data=is_data,
        weight_dict=syst_cfg['weights'],
        store_shifted_weights=False,
        treeName="Events",
        explicit_files=chunk_files,
        seg_dict=seg_dict,
        skip_validation=True,
        dnn_payloads=dnn_payloads,
        btag_algo=btag_algo
    )

    tmp_output = f"{args.output_file}.tmp_{chunk_index}"
    outFile = ROOT.TFile(tmp_output, "RECREATE")
    booked_hists = []

    for syst_name, syst_info in systs_to_run.items():
        weight_name = syst_info["weight"]

        for mass_region, mass_info in masses_regions.items():
            if mass_region not in masses_regions_list: continue
            if not mass_info["store"]: continue
            for category, cat_info in categories.items():
                if category not in categories_list: continue
                if category not in rdf_base.GetColumnNames():
                    rdf_base=rdf_base.Define(category, cat_info['expression'])
                if not cat_info["store"]: continue

                dir_ptr = utilities.mkdir_recursive(outFile, f"{mass_region}_{category}")
                rdf_filtered = rdf_base.Filter(f"{mass_region} && {category}") if rdf_base is not None else None
                for var in vars_to_make_hist:
                    model = GetModel(hist_cfg, var, dims=1)
                    hist_name = var if syst_name == "Central" else f"{var}_{syst_name}"
                    if rdf_base is not None:
                        hist = rdf_filtered.Histo1D(model, var, weight_name)
                    else:
                        hist = ROOT.TH1D(hist_name, hist_name, model.fNbinsX, model.fXLow, model.fXUp)
                    booked_hists.append((dir_ptr, hist_name, hist))

    for dir_ptr, hist_name, hist_ptr in booked_hists:
        if rdf_base is not None:
            hist = hist_ptr.GetValue()
        else:
            hist = hist_ptr
        hist.SetName(hist_name)
        hist.SetTitle(hist_name)
        hist.SetDirectory(0)
        dir_ptr.WriteTObject(hist, hist_name, "Overwrite")

    outFile.Close()
    return tmp_output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument( "--era", required=True, type=str)
    parser.add_argument( "--input", required=True, type=str, help="ROOT file or dataset directory")
    parser.add_argument( "--dataset-name", "--dataset", dest="dataset_name", required=True, type=str)
    parser.add_argument( "--output-file", required=True, type=str)
    parser.add_argument( "--systematics", choices=["central", "all"], default="central")

    # Nuovi parametri per il controllo locale
    parser.add_argument( "--chunk-size", type=int, default=4, help="Quanti file ROOT per ogni chunk")
    parser.add_argument( "--n-cores", type=int, default=4, help="Quanti processi separati usare in parallelo")
    parser.add_argument( "--skip-file-validation", action="store_true", help="Non aprire tutti i file prima di costruire gli istogrammi")
    parser.add_argument( "--variables", nargs="+", help="Variabili da istogrammare al posto di quelle in maincfg.yaml")
    parser.add_argument( "--mass-regions", nargs="+", default=["mass_inclusive", "Z_sideband", "Signal_Fit"], help="Regioni di massa da istogrammare")
    parser.add_argument( "--categories", nargs="+", default=["baseline", "ggF", "VBF"], help="Categorie da istogrammare")
    args = parser.parse_args()

    startTime = time.time()

    cfg_dir = os.path.join(os.environ["ANALYSIS_PATH"], "config", args.era)
    main_cfg = utilities.get_config(os.path.join(cfg_dir, "maincfg.yaml"))
    dataset_cfg = utilities.get_config(os.path.join(cfg_dir, "samples.yaml")).get(args.dataset_name, {})
    is_data = dataset_cfg.get("is_data", False) or "data" in args.dataset_name or "Data" in args.dataset_name
    sel_cfg = utilities.get_config(os.path.join(cfg_dir, "selections.yaml"))
    syst_cfg = utilities.get_config(os.path.join(cfg_dir, "systematics.yaml"))
    hist_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", "plot", "histograms.yaml"))

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

    systs_to_run = {"Central": syst_cfg["systematics"]["Central"]}
    if args.systematics != 'central':
        systs_to_run.update(syst_cfg['systematics'])
        systs_to_run.update(syst_cfg['weights'])

    # -----------------------------------------------------------------
    # Logica di Chunking Locale con multiprocessing spawn
    # -----------------------------------------------------------------
    all_root_files = get_root_files(args.input)
    valid_root_files = all_root_files if args.skip_file_validation else get_valid_root_files(all_root_files, tree_name="Events")
    seg_dict = get_segmentation_dict(args.input)

    print(f"\n[INFO] Dataset {args.dataset_name} contiene {len(valid_root_files)} file ROOT validi su {len(all_root_files)} file totali.")
    print(f"[INFO] Divido in chunk di dimensione {args.chunk_size} usando {args.n_cores} processi separati in parallelo...")

    if len(valid_root_files) == 0:
        print("[ERROR] Nessun file ROOT valido trovato. Esco.")
        sys.exit(1)

    chunks = [valid_root_files[i:i + args.chunk_size] for i in range(0, len(valid_root_files), args.chunk_size)]
    pool_inputs = []
    for idx, chunk_files in enumerate(chunks):
        pool_inputs.append((
            idx, chunk_files, args, is_data, syst_cfg, vars_to_make_hist,
            masses_regions, masses_regions_list, categories, categories_list, hist_cfg, systs_to_run, seg_dict, dnn_payloads, main_cfg.get("bTagAlgo", "PNet")
        ))

    ctx = get_context('spawn')
    tmp_files = []
    with ctx.Pool(processes=args.n_cores) as pool:
        tmp_files = pool.map(process_single_chunk, pool_inputs)

    print("\n[INFO] Tutti i chunk sono stati elaborati con successo.")
    print(f"[INFO] Unisco i {len(tmp_files)} file temporanei in {args.output_file}...")

    output_dir = os.path.dirname(args.output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    hadd_cmd = f"hadd -f {args.output_file} " + " ".join(tmp_files)
    exit_code = os.system(hadd_cmd)

    if exit_code == 0:
        print("[INFO] Unione completata. Pulisco i file temporanei...")
        for tmp_f in tmp_files:
            if os.path.exists(tmp_f):
                os.remove(tmp_f)
    else:
        print("[ERROR] Errore durante l'esecuzione di hadd!")

    executionTime = time.time() - startTime
    print(f"\nExecution time: {executionTime:.2f} s")

# #!/usr/bin/env python3

# import ROOT
# import sys
# import os
# import argparse
# import time

# if __name__ == "__main__":
#     sys.path.append(os.environ["ANALYSIS_PATH"])

# import common.utilities as utilities

# HEADERS = ["analysis/AnalysisTools.h"]
# for header in HEADERS:
#     utilities.DeclareHeader(f"{os.environ['ANALYSIS_PATH']}/{header}")

# from common.helpers import GetModel,GetRdfForDataset



# parser = argparse.ArgumentParser()
# parser.add_argument( "--era", required=True, type=str)
# parser.add_argument( "--input", required=True, type=str, help="ROOT file or dataset directory")
# parser.add_argument( "--dataset-name", required=True, type=str)
# parser.add_argument( "--output-file", required=True, type=str)
# parser.add_argument( "--systematics", choices=["central", "all"], default="central")
# args = parser.parse_args()

# startTime = time.time()

# cfg_dir = os.path.join( os.environ["ANALYSIS_PATH"],"config",args.era)
# main_cfg = utilities.get_config(os.path.join(cfg_dir, "maincfg.yaml"))
# dataset_cfg = utilities.get_config(os.path.join(cfg_dir, "samples.yaml"))[args.dataset_name]
# is_data = dataset_cfg.get("is_data", False)
# sel_cfg = utilities.get_config(os.path.join(cfg_dir, "selections.yaml"))
# syst_cfg = utilities.get_config(os.path.join(cfg_dir, "systematics.yaml"))
# hist_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"],"config","plot","histograms.yaml"))

# masses_regions = sel_cfg["masses_regions"]
# categories = sel_cfg["categories"]
# masses_regions_list = ["Z_sideband"]#,"Signal_Fit","H_sideband"]
# categories_list = ["baseline","ggF","VBF"]
# vars_to_make_hist = main_cfg["variables"]

# rdf_base =  GetRdfForDataset(args.input, is_data, syst_cfg['weights'], store_shifted_weights=False, treeName="Events")


# systs_to_run = {
#         "Central": syst_cfg["systematics"]["Central"]
#     }
# if args.systematics != 'central':
#     syst_to_run = syst_cfg['systematics']
#     syst_to_run.update(syst_cfg['weights'])

# # up to here it is totally general for every kind of manipulation

# outFile = ROOT.TFile(args.output_file,"RECREATE")

# for syst_name, syst_info in systs_to_run.items():
#     mu_suffix = syst_info["muon_suffix"]
#     jet_suffix = syst_info["jet_suffix"]
#     weight_name = syst_info["weight"]
#     suffix_for_hist = syst_info["name"]

#     rdf = rdf_base
#     for mass_region, mass_info in masses_regions.items():
#         if mass_region not in masses_regions_list: continue
#         if not mass_info["store"]: continue
#         for category, cat_info in categories.items():
#             if category not in categories_list: continue
#             if not cat_info["store"]: continue
#             print(f"Processing: {mass_region} / {category}")
#             dir_ptr = utilities.mkdir_recursive(outFile,f"{mass_region}_{category}")
#             for var in vars_to_make_hist:
#                 model = GetModel(hist_cfg,var,dims=1)
#                 hist_name = var if syst_name == "Central" else f"{var}_{syst_name}"
#                 if rdf is not None:
#                     hist = rdf.Filter(f"{mass_region} && {category}").Histo1D(model,var,weight_name).GetValue()
#                 else:
#                     hist = ROOT.TH1D(hist_name,hist_name,model.fNbinsX,model.fXLow,model.fXUp)
#                 hist.SetName(hist_name)
#                 hist.SetDirectory(0)
#                 dir_ptr.WriteTObject(hist,hist_name,"Overwrite")

# outFile.Close()
# executionTime = time.time() - startTime
# print(f"\nExecution time: {executionTime:.2f} s")
