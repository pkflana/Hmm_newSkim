import os
import yaml
import argparse
import subprocess
# voms-proxy-init --voms cms --valid 192:00

# =========================================================
# Base paths
# =========================================================

ANALYSIS_PATH = os.environ.get("ANALYSIS_PATH")

if ANALYSIS_PATH is None:
    raise RuntimeError("Environment variable ANALYSIS_PATH is not set")

parser = argparse.ArgumentParser(
    description="Submit skim jobs to HTCondor with one Condor cluster per dataset."
)
parser.add_argument(
    "-e",
    "--era",
    required=True,
    help="Era to process, e.g. Run3_2022EE",
)
parser.add_argument(
    "--use-ext",
    action=argparse.BooleanOptionalAction,
    default=None,
    help=(
        "Use all nanoAOD paths listed for each sample, including ext samples. "
        "Default comes from skim_cfg.yaml use_ext, or false if unset."
    ),
)

args = parser.parse_args()

eras = args.era.split(",")

CONFIG_PATH = os.path.join(ANALYSIS_PATH, "config")


def as_list(value):
    if isinstance(value, list):
        return value
    return [value]


def select_nanoaod_paths(nanoaod_paths, use_ext=False):
    paths = as_list(nanoaod_paths)
    if use_ext:
        return paths
    return paths[:1]


def resolve_nanoaod_files(nanoaod_paths, instance=None):
    resolved_files = []
    seen_files = set()

    for dataset in as_list(nanoaod_paths):
        query = f"file dataset={dataset}"
        if instance:
            query += f" instance={instance}"

        command = ["dasgoclient", f"--query={query}"]
        print(" ".join(command))

        filelist = subprocess.check_output(
            command,
            text=True,
        ).splitlines()

        for filepath in filelist:
            eos_path = f"/eos/cms/{filepath}"

            if os.path.exists(eos_path):
                resolved_path = eos_path
            else:
                resolved_path = f"root://cms-xrd-global.cern.ch/{filepath}"

            if resolved_path in seen_files:
                continue

            resolved_files.append(resolved_path)
            seen_files.add(resolved_path)

    return resolved_files


for era in eras: # "Run3_2022","Run3_2022EE","Run3_2023","Run3_2023BPix", "Run3_2024"
    print(f"Processing era: {era}")
    skim_cfg_path = os.path.join(
        CONFIG_PATH,
        era,
        "skim_cfg.yaml"
    )

    with open(skim_cfg_path, "r") as skimconfig:
        skim_config = yaml.safe_load(skimconfig)

    use_ext = args.use_ext
    if use_ext is None:
        use_ext = skim_config.get("use_ext", False)

    print(f"[INFO] use_ext={use_ext}")

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

        selected_nanoaod_paths = select_nanoaod_paths(
            data[key][nanoaod],
            use_ext=use_ext,
        )
        if len(as_list(data[key][nanoaod])) > len(selected_nanoaod_paths):
            print(
                f"[INFO] {key}: use_ext=False, using only first nanoAOD path "
                f"out of {len(as_list(data[key][nanoaod]))}."
            )

        data[key]["filelist"] = resolve_nanoaod_files(
            selected_nanoaod_paths,
            instance=data[key].get("instance", None),
        )

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
