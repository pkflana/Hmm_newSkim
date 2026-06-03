import os
import yaml
import htcondor

# =========================================================
# Environment
# =========================================================

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_PATH = os.path.abspath(os.path.join(BASE_PATH, ".."))

print(f"Environment variable ANALYSIS_PATH is not set, using {ANALYSIS_PATH} as default")

HTCONDOR_PATH = os.path.join(ANALYSIS_PATH, "htcondor")
CONFIG_PATH = os.path.join(ANALYSIS_PATH, "config")

era = "Run3_2022"
skim_cfg_path = os.path.join(CONFIG_PATH, era, "skim_cfg.yaml")

with open(skim_cfg_path, "r") as skimconfig:
    skim_config = yaml.safe_load(skimconfig)

schedd = htcondor.Schedd()
col = htcondor.Collector()
credd = htcondor.Credd()

credd.add_user_cred(htcondor.CredTypes.Kerberos, None)

processes_yaml = os.path.join(CONFIG_PATH, era, "process_names.yaml")
with open(processes_yaml, "r") as processes_config:
    processes_cfg = yaml.safe_load(processes_config)

samples_yaml = os.path.join(CONFIG_PATH, era, "samples_withfiles.yaml")
with open(samples_yaml, "r") as samples_config:
    data = yaml.safe_load(samples_config)

# =========================================================
# Configuration
# =========================================================

flavour = skim_config["job_flavour"]
cpus = skim_config["request_cpus"]
memory = skim_config["request_memory"]
disk = skim_config["request_disk"]

max_files = skim_config["max_files"]
datasets_whitelist = skim_config.get("datasets_whitelist", [])
chunk_size = skim_config["chunk_size"]

output_directory = os.path.abspath(skim_config["output_dir"])
proxy_location = skim_config["proxy_location"]

all_datasets = []
all_datasets.extend(datasets_whitelist)
if skim_config.get("process_to_select", []):
    for process in skim_config.get("process_to_select", []):
        for dataset in processes_cfg[process].get("datasets", []) + processes_cfg[process].get("sub_processes", []):
            all_datasets.append(dataset)

print(f"Datasets to process: {all_datasets}")

for dataset in all_datasets:
    if dataset not in data or "filelist" not in data[dataset]:
        print(f"You don't have the filelist for: {dataset}")
        continue

    completed_files_path = os.path.join(HTCONDOR_PATH, "log", era, dataset, "completed_files.txt")
    completed_files = []
    if os.path.exists(completed_files_path):
        with open(completed_files_path, "r") as cf:
            completed_files = [line.rstrip() for line in cf]
        print(f"Loaded {len(completed_files)} completed entries from recovery list.")


    condorinputs = []
    filecounter = 0
    filelist = data[dataset]["filelist"]

    # Ciclo sui file a blocchi (chunk_size)
    for i in range(0, len(filelist), chunk_size):
        input_files = []
        output_files = []
        chunk = filelist[i:i + chunk_size]

        for infile in chunk:
            # Sostituzione per il file ROOT finale
            output_file_root = os.path.basename(infile).replace(".root", "_skim.root")
            outfile_root = os.path.join(output_directory, era, dataset, output_file_root)

            # Generazione del corrispettivo nome per il file JSON report
            output_file_json = os.path.basename(infile).replace(".root", "_skim_report.json")
            outfile_json = os.path.join(output_directory, era, dataset, output_file_json)

            # --- Controllo Risottomissione Doppio (ROOT + JSON) ---
            # Il job viene saltato SOLO se entrambi i file sono marcati come completati
            if outfile_root in completed_files and outfile_json in completed_files:
                filecounter += 1
                continue

            input_files.append(infile)
            output_files.append(outfile_root)
            filecounter += 1

        # Se tutti i file di questo chunk erano già completati, passiamo oltre
        if len(input_files) == 0:
            continue

        input_list = ",".join(input_files)
        output_list = ",".join(output_files)

        arguments = (
            f"{proxy_location} "
            f"{ANALYSIS_PATH} "
            f"{era} "
            f"{input_list} "
            f"{dataset} "
            f"{output_list}"
        )

        condorinputs.append({
            "arguments": arguments,
            "filename": os.path.basename(input_files[0]).replace(".root", ""),
            "logpath": f"{dataset}/"
        })

    # =====================================================
    # Create log directories
    # =====================================================
    if len(condorinputs) > 0:
        log_base = os.path.join(HTCONDOR_PATH, "log", era, dataset)
        err_base = os.path.join(HTCONDOR_PATH, "error", era, dataset)
        out_base = os.path.join(HTCONDOR_PATH, "output", era, dataset)

        for p in [log_base, err_base, out_base]:
            os.makedirs(p, exist_ok=True)

        output_dataset_dir = os.path.join(output_directory, era, dataset)
        os.makedirs(output_dataset_dir, exist_ok=True)

        # =====================================================
        # Submit description
        # =====================================================
        executable_path = os.path.join(HTCONDOR_PATH, "run_skim.sh")

        job = htcondor.Submit({
            "executable": executable_path,
            "arguments": "$(arguments)",
            "output": os.path.join(out_base, "$(filename).$(ClusterId).$(ProcId).out"),
            "error": os.path.join(err_base, "$(filename).$(ClusterId).$(ProcId).err"),
            "log": os.path.join(log_base, "$(filename).$(ClusterId).$(ProcId).log"),
            "universe": "vanilla",
            "Requirements": '(OpSysAndVer =?= "AlmaLinux9")',
            "+JobFlavour": flavour,
            "RequestCpus": cpus,
            "request_memory": memory,
            "request_disk": disk,
            "max_retries": "1",
            "batch_name": dataset
        })

        job["MY.SendCredential"] = "true"

        # =====================================================
        # Submit
        # =====================================================
        print(f"Submitting {len(condorinputs)} jobs for dataset {dataset}")

        if skim_config.get("submit", False):
            submit_result = schedd.submit(
                job,
                itemdata=iter(condorinputs)
            )
    else:
        print(f"All files (ROOT + JSON reports) for dataset {dataset} are already completed. Skipping submission.")