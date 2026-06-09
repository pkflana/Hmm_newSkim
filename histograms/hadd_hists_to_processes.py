import os
import shutil
import yaml
import argparse



def load_yaml_config(yaml_path):
    with open(yaml_path, "r") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(f"Errore nel parsing del file YAML: {exc}")
            return None


def hadd_datasets_to_processes(era,input_dir, output_dir,dryRun=False):
    if not dryRun:
        import uproot
    yaml_file = f"config/{era}/process_names.yaml"  # Il tuo file YAML
    config = load_yaml_config(yaml_file)
    config_processnames = load_yaml_config(os.path.join("config", era, "skim_cfg.yaml"))["process_to_select"]
    if not config:
        return

    if not dryRun and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 1. Costruiamo la mappatura Processo -> Lista di Dataset associati
    process_mapping = {}

    for yaml_key, info in config.items():
        if yaml_key not in config_processnames: continue
        if info is None:
            continue

        # Estrai i dataset e sub_processes
        datasets = info.get("datasets", []) + info.get("sub_processes", [])
        if not datasets or not isinstance(datasets, list):
            continue

        process_name = yaml_key

        if process_name not in process_mapping:
            process_mapping[process_name] = []

        process_mapping[process_name].extend(datasets)
    # print(process_mapping)
    # 2. Controllo file ed Esecuzione/Stampa
    if dryRun:
        print("\n=== [DRY-RUN] PIANO DI ACCOPPIAMENTO (Solo file esistenti) ===")

    for process, datasets in process_mapping.items():
        datasets = list(dict.fromkeys(datasets))  # Rimuove duplicati

        # Filtra i dataset tenendo solo quelli CHE ESISTONO SUL DISCO
        valid_dataset_files = []
        for dataset in datasets:
            dataset_file_path = os.path.join(input_dir, f"{dataset}.root")
            if os.path.exists(dataset_file_path):
                valid_dataset_files.append(dataset_file_path)

        # SE NON CE NE SONO, PASSA (Salta completamente il processo)
        if not valid_dataset_files:
            continue

        output_file_path = os.path.join(output_dir, f"{process}.root")

        # --- SE DRY-RUN: Stampa solo quello che farebbe ---
        if dryRun:
            print(f"\n📦 File di output previsto: {process}.root")
            print(
                f"   ↳ Unione (hadd) di {len(valid_dataset_files)}/{len(datasets)} file trovati:"
            )
            for f in valid_dataset_files:
                print(f"     - {f}")
            continue

        # --- SE ESECUZIONE REALE ---
        print(
            f"📦 Creazione di {process}.root da {len(valid_dataset_files)} file..."
        )

        if len(valid_dataset_files) == 1:
            shutil.copyfile(valid_dataset_files[0], output_file_path)
            print(f"   -> Copiato direttamente (singolo file esistente).")
            continue

        try:
            with uproot.open(valid_dataset_files[0]) as first_file:
                histo_keys = [k.split(";")[0] for k in first_file.keys()]

            summed_histograms = {}

            for file_path in valid_dataset_files:
                with uproot.open(file_path) as current_file:
                    for key in histo_keys:
                        if key in current_file:
                            histo = current_file[key]
                            if (
                                hasattr(histo, "to_numpy")
                                or "TH" in str(type(histo))
                            ):
                                if key not in summed_histograms:
                                    summed_histograms[key] = histo.to_hist()
                                else:
                                    summed_histograms[key] += histo.to_hist()

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
        print("\n--- HADDing Completato! ---")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument( "--era", required=True, type=str)
    parser.add_argument( "--input-dir", required=True, type=str, help="ROOT file or dataset directory")
    parser.add_argument( "--output-dir", required=True, type=str, help="ROOT file or dataset directory")
    parser.add_argument( "--dryRun", action="store_true", help="dryRun only")
    args = parser.parse_args()

    hadd_datasets_to_processes(args.era,args.input_dir, args.output_dir,args.dryRun)