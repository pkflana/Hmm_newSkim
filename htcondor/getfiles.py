import os
import yaml

# voms-proxy-init --voms cms --valid 192:00

# =========================================================
# Base paths
# =========================================================

ANALYSIS_PATH = os.environ.get("ANALYSIS_PATH")

if ANALYSIS_PATH is None:
    raise RuntimeError("Environment variable ANALYSIS_PATH is not set")

CONFIG_PATH = os.path.join(ANALYSIS_PATH, "config")
for era in ["Run3_2022","Run3_2022EE","Run3_2023","Run3_2023BPix", "Run3_2024"]:
    print(f"Processing era: {era}")
    skim_cfg_path = os.path.join(
        CONFIG_PATH,
        era,
        "skim_cfg.yaml"
    )

    with open(skim_cfg_path, "r") as skimconfig:
        skim_config = yaml.safe_load(skimconfig)

    samples_yaml = os.path.join(CONFIG_PATH, era, "samples.yaml")
    process_yaml = os.path.join(CONFIG_PATH, era, "process_names.yaml")

    with open(samples_yaml, "r") as samples_config:
        data = yaml.safe_load(samples_config)

    with open(process_yaml, "r") as process_names:
        processes = yaml.safe_load(process_names)

    datasetlist = []

    for key in processes.keys():

        if "datasets" in processes[key]:
            datasetlist.extend(processes[key]["datasets"])

        else:
            print(f"{key} has no datasets in process_names.yaml")

    nanoaod = "nanoAOD"
    istance = None

    for key in data.keys():

        if key not in datasetlist:
            continue

        if nanoaod not in data[key]:
            print(f"Missing nanoAOD for {key} in samples.yaml")
            continue

        dataset = data[key][nanoaod]


        query = f'dasgoclient --query="file dataset={dataset}'
        if data[key].get("instance", None):
            istance= data[key].get("instance", None)
            query += f' instance={istance}"'
            print(query)
        else: query+='"'
        filelist = os.popen(query).read().splitlines()

        resolved_files = []

        for filepath in filelist:

            eos_path = f"/eos/cms/{filepath}"

            if os.path.exists(eos_path):
                resolved_files.append(eos_path)

            else:
                resolved_files.append(
                    f"root://cms-xrd-global.cern.ch/{filepath}"
                )

        data[key]["filelist"] = resolved_files

    output_yaml = os.path.join(
        CONFIG_PATH,
        era,
        f"samples_withfiles.yaml"
    )

    with open(output_yaml, "w") as outfile:
        yaml.dump(
            data,
            outfile,
            default_flow_style=False,
            sort_keys=False
        )

    print(f"Saved output to {output_yaml}")
