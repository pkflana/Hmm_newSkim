import argparse
import copy
import os
import re
import shutil
import sys

import yaml

ANALYSIS_PATH = os.environ.get(
    "ANALYSIS_PATH",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
)
sys.path.append(ANALYSIS_PATH)

from common.dataset_utilities import resolve_dataset_selection
from common.jet_component_splitting import DY_COMPONENT_FILE_LABELS


def load_yaml_config(yaml_path):
    with open(yaml_path, "r") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(f"Errore nel parsing del file YAML: {exc}")
            return None


def hist_sum_value(histogram):
    total = histogram.sum(flow=True)
    return float(getattr(total, "value", total))


def dataset_file_candidates(input_dir, process, dataset, component_label=None):
    suffix_by_process = {
        "DYto2Mu_MLL105To160": ["_stitched", ""],
        "DYto2Mu_MLL105To160_nonStitched": ["_nonStitched", ""],
        "DYto2Mu_MLL105To160_VBFFiltered": ["_stitched", ""],
        "DYto2Mu_MLL105To160_VBFFiltered_nonStitched": ["_nonStitched", ""],
        "DYto2Mu_MLL105To160_FlashSim": ["_nonStitched", ""],
    }
    source_process = process
    if process == "DYto2Mu_MLL105To160_combined" and component_label:
        # The combined process is assembled component by component from the
        # complementary inclusive and generator-VBF-filtered productions.
        source_process = (
            "DYto2Mu_MLL105To160_VBFFiltered"
            if "Fil_VBF" in dataset or "VBFFiltered" in dataset
            else "DYto2Mu_MLL105To160"
        )
    suffixes = suffix_by_process.get(source_process, [""])
    # hist_maker prefixes split files with the concrete process name, except
    # for the canonical DY process where the historical DY_* labels are kept.
    # Examples:
    #   DY                         -> <dataset>_DY_VBF_Hard.root
    #   DYto2Mu_MLL105To160        -> <dataset>_DYto2Mu_MLL105To160_VBF_Hard.root
    candidates = []
    component_name = component_label.removeprefix("DY_") if component_label else None
    for suffix in suffixes:
        if component_name and source_process != "DY":
            # Current split files encode the concrete process variant inside
            # the component suffix, e.g.
            #   <dataset>_DYto2Mu_MLL105To160_nonStitched_0J.root
            candidates.append(
                os.path.join(
                    input_dir,
                    f"{dataset}_{source_process}{suffix}_{component_name}.root",
                )
            )
            # Retain compatibility with the older dataset-suffix layout.
            candidates.append(
                os.path.join(
                    input_dir,
                    f"{dataset}{suffix}_{source_process}_{component_name}.root",
                )
            )
        elif component_name:
            candidates.append(
                os.path.join(input_dir, f"{dataset}{suffix}_{component_label}.root")
            )
        else:
            candidates.append(os.path.join(input_dir, f"{dataset}{suffix}.root"))
    return list(dict.fromkeys(candidates))


def add_derived_systematics(era, output_dir):
    import numpy as np
    import uproot

    systematics_cfg = load_yaml_config(
        os.path.join("config", era, "systematics.yaml")
    )
    derived_cfg = (systematics_cfg or {}).get("derived_systematics", {})

    for _, config in derived_cfg.items():
        nominal_process = config["nominal_process"]
        alternative_process = config["alternative_process"]
        nuisance_name = config["name"]
        coefficient = float(config.get("coefficient", 0.5))
        floor = float(config.get("floor", 0.0))
        nominal_path = os.path.join(output_dir, f"{nominal_process}.root")
        alternative_path = os.path.join(
            output_dir, f"{alternative_process}.root"
        )

        if not os.path.exists(nominal_path) or not os.path.exists(alternative_path):
            print(
                f"[WARNING] Cannot build {nuisance_name}: missing "
                f"{nominal_path} or {alternative_path}"
            )
            continue

        variations = {}
        with (
            uproot.open(nominal_path) as nominal_file,
            uproot.open(alternative_path) as alternative_file,
        ):
            for key in nominal_file.keys(recursive=True):
                clean_key = key.split(";")[0]
                histogram_name = clean_key.rsplit("/", 1)[-1]
                if re.search(r"(Up|Down)$", histogram_name):
                    continue
                if clean_key not in alternative_file:
                    continue

                nominal_object = nominal_file[clean_key]
                alternative_object = alternative_file[clean_key]
                if not (
                    hasattr(nominal_object, "to_hist")
                    and hasattr(alternative_object, "to_hist")
                ):
                    continue

                nominal_hist = nominal_object.to_hist()
                alternative_hist = alternative_object.to_hist()
                nominal_values = nominal_hist.values(flow=True)
                alternative_values = alternative_hist.values(flow=True)
                if nominal_values.shape != alternative_values.shape:
                    raise RuntimeError(
                        f"Histogram shape mismatch for '{clean_key}' between "
                        f"{nominal_process} and {alternative_process}"
                    )

                half_difference = coefficient * np.abs(
                    alternative_values - nominal_values
                )
                up_hist = copy.deepcopy(nominal_hist)
                down_hist = copy.deepcopy(nominal_hist)
                up_hist.view(flow=True).value[...] = (
                    nominal_values + half_difference
                )
                down_hist.view(flow=True).value[...] = np.maximum(
                    floor, nominal_values - half_difference
                )

                directory = clean_key.rsplit("/", 1)[0] if "/" in clean_key else ""
                prefix = f"{directory}/" if directory else ""
                variations[
                    f"{prefix}{histogram_name}_{nuisance_name}Up"
                ] = up_hist
                variations[
                    f"{prefix}{histogram_name}_{nuisance_name}Down"
                ] = down_hist

        with uproot.update(nominal_path) as nominal_output:
            for key, histogram in variations.items():
                nominal_output[key] = histogram
        print(
            f"   -> Added {len(variations)} {nuisance_name} templates "
            f"to {nominal_path}"
        )


def hadd_datasets_to_processes(era,input_dir, output_dir,add_derived_systs=True,dryRun=False):
    if not dryRun:
        import uproot
    selection = resolve_dataset_selection(ANALYSIS_PATH, era)

    if not dryRun and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 1. Costruiamo la mappatura Processo -> Lista di Dataset associati
    process_mapping = selection["process_datasets"]
    # print(process_mapping)
    # 2. Controllo file ed Esecuzione/Stampa
    if dryRun:
        print("\n=== [DRY-RUN] PIANO DI ACCOPPIAMENTO (Solo file esistenti) ===")

    output_variants = (None, *dict.fromkeys(DY_COMPONENT_FILE_LABELS.values()))
    for process, datasets in process_mapping.items():
      for component_label in output_variants:
        datasets = list(dict.fromkeys(datasets))  # Rimuove duplicati

        # Filtra i dataset tenendo solo quelli CHE ESISTONO SUL DISCO
        valid_dataset_files = []
        for dataset in datasets:
            for dataset_file_path in dataset_file_candidates(
                input_dir, process, dataset, component_label
            ):
                if os.path.exists(dataset_file_path):
                    valid_dataset_files.append(dataset_file_path)
                    break

        # SE NON CE NE SONO, PASSA (Salta completamente il processo)
        if not valid_dataset_files:
            continue

        # Do not duplicate the historical DY prefix in process-level files:
        # DY_DY_0J.root becomes DY_0J.root, while process-specific outputs use
        # e.g. DYto2Mu_MLL105To160_0J.root.
        output_component = (
            component_label.removeprefix("DY_") if component_label else None
        )
        output_suffix = f"_{output_component}" if output_component else ""
        output_name = f"{process}{output_suffix}.root"
        output_file_path = os.path.join(output_dir, output_name)

        # --- SE DRY-RUN: Stampa solo quello che farebbe ---
        if dryRun:
            print(f"\n📦 File di output previsto: {output_name}")
            print(
                f"   ↳ Unione (hadd) di {len(valid_dataset_files)}/{len(datasets)} file trovati:"
            )
            for f in valid_dataset_files:
                print(f"     - {f}")
            continue

        # --- SE ESECUZIONE REALE ---
        print(
            f"📦 Creazione di {output_name} da {len(valid_dataset_files)} file..."
        )

        if len(valid_dataset_files) == 1:
            shutil.copyfile(valid_dataset_files[0], output_file_path)
            print(f"   -> Copiato direttamente (singolo file esistente).")
            continue

        try:
            histo_keys = []
            seen_keys = set()
            for file_path in valid_dataset_files:
                with uproot.open(file_path) as current_file:
                    for key in current_file.keys(recursive=True):
                        clean_key = key.split(";")[0]
                        if clean_key in seen_keys:
                            continue
                        try:
                            histo = current_file[clean_key]
                        except Exception:
                            continue
                        if hasattr(histo, "to_numpy") or "TH" in str(type(histo)):
                            histo_keys.append(clean_key)
                            seen_keys.add(clean_key)

            summed_histograms = {}

            for file_path in valid_dataset_files:
                with uproot.open(file_path) as current_file:
                    for key in histo_keys:
                        try:
                            histo = current_file[key]
                        except Exception:
                            continue
                        if hasattr(histo, "to_numpy") or "TH" in str(type(histo)):
                            current_hist = histo.to_hist()
                            if key not in summed_histograms:
                                summed_histograms[key] = current_hist
                            elif hist_sum_value(summed_histograms[key]) == 0.0 and hist_sum_value(current_hist) != 0.0:
                                summed_histograms[key] = current_hist
                            else:
                                summed_histograms[key] = summed_histograms[key] + current_hist

            with uproot.recreate(output_file_path) as output_root:
                for key, merged_hist in summed_histograms.items():
                    output_root[key] = merged_hist

            print(
                f"   ✅ Successo! Salvato in: {output_file_path}"
            )

        except Exception as e:
            print(
                f"   ❌ Errore durante l'elaborazione del processo {process}: {e}"
            )

    if dryRun:
        print("\n===============================================================\n")
    else:
        if add_derived_systs:
            add_derived_systematics(era, output_dir)
        print("\n--- HADDing Completato! ---")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument( "--era", required=True, type=str)
    parser.add_argument( "--input-dir", required=True, type=str, help="ROOT file or dataset directory")
    parser.add_argument( "--output-dir", required=True, type=str, help="ROOT file or dataset directory")
    parser.add_argument( "--dryRun", action="store_true", help="dryRun only")
    parser.add_argument( "--add-derived-systs", action="store_true", help="add EWKZ unc")
    args = parser.parse_args()

    hadd_datasets_to_processes(args.era,args.input_dir, args.output_dir,args.add_derived_systs,args.dryRun)
