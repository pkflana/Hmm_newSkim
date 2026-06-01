import os
import shutil
import yaml

# CONFIGURAZIONE
YAML_FILE = "config/Run3_2022/process_names.yaml"  # Il tuo file YAML
INPUT_DIR = "/eos/user/v/vdamante/H_mumu/newHists/"  # Cartella file ROOT dei dataset
OUTPUT_DIR = "/eos/user/v/vdamante/H_mumu/newHists_hadded/"  # Cartella di output

# MODALITÀ DRY-RUN
# True: Stampa solo la mappa dei file che verranno uniti (senza toccare il disco)
# False: Esegue l'hadd reale degli istogrammi
DRY_RUN = False

# Importiamo uproot solo se serve davvero l'elaborazione reale
if not DRY_RUN:
    import uproot

def load_yaml_config(yaml_path):
    with open(yaml_path, "r") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(f"Errore nel parsing del file YAML: {exc}")
            return None


def hadd_datasets_to_processes():
    config = load_yaml_config(YAML_FILE)
    config_processnames = load_yaml_config(os.path.join("config", "Run3_2022", "skim_cfg.yaml"))["process_to_select"]
    if not config:
        return

    if not DRY_RUN and not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

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

        # Determina il nome del processo finale basandoti sul campo 'name' o sulla chiave
        process_name = yaml_key
        # process_name = info.get("name", yaml_key)

        # Pulizia del nome per renderlo un nome di file sicuro
        # process_name = (
        #     process_name.strip()
        #     .replace(" ", "_")
        #     .replace("$", "")
        #     .replace("\\bar{t}", "barT")
        #     .replace("t_\\bar{t}", "ttbar")
        #     .replace("\\rightarrow", "to")
        #     .replace("\\ell", "l")
        #     .replace("\\nu", "nu")
        #     .replace("#", "")
        # )
        # if process_name == "Data_Full" : continue
        # if process_name=="DY": continue

        if process_name not in process_mapping:
            process_mapping[process_name] = []

        process_mapping[process_name].extend(datasets)
    # print(process_mapping)
    # 2. Controllo file ed Esecuzione/Stampa
    if DRY_RUN:
        print("\n=== [DRY-RUN] PIANO DI ACCOPPIAMENTO (Solo file esistenti) ===")

    for process, datasets in process_mapping.items():
        datasets = list(dict.fromkeys(datasets))  # Rimuove duplicati

        # Filtra i dataset tenendo solo quelli CHE ESISTONO SUL DISCO
        valid_dataset_files = []
        for dataset in datasets:
            dataset_file_path = os.path.join(INPUT_DIR, f"{dataset}.root")
            if os.path.exists(dataset_file_path):
                valid_dataset_files.append(dataset_file_path)

        # SE NON CE NE SONO, PASSA (Salta completamente il processo)
        if not valid_dataset_files:
            continue

        output_file_path = os.path.join(OUTPUT_DIR, f"{process}.root")

        # --- SE DRY-RUN: Stampa solo quello che farebbe ---
        if DRY_RUN:
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
                f"   ✅ Successo! Salvato in: {os.path.basename(output_file_path)}"
            )

        except Exception as e:
            print(
                f"   ❌ Errore durante l'elaborazione del processo {process}: {e}"
            )

    if DRY_RUN:
        print("\n===============================================================\n")
    else:
        print("\n--- HADDing Completato! ---")


if __name__ == "__main__":
    hadd_datasets_to_processes()