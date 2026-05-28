import ROOT
import os
import sys
import subprocess
import argparse
if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])

import analysis.utilities as utilities

def run_cmd(cmd):
    return subprocess.check_output(cmd, shell=True).decode().splitlines()

def make_das_filelist(dataset, out_txt, max_files=None):
    files = run_cmd(f'dasgoclient --query="file dataset={dataset}"')
    if max_files:
        files = files[:max_files]
    with open(out_txt, "a") as f:
        for x in files:
            f.write(x + "\n")

era = "Run3_2022"
config = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "maincfg.yaml"))
processes_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "process_names.yaml"))
datasets_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "samples.yaml"))

input_processes = config.get('process_to_select',[])
print(input_processes)
for process in input_processes:
    print(f"considering process: {process}")
    sub_datasets = processes_cfg[process].get("datasets",[])
    sub_datasets.extend(processes_cfg[process].get("sub_processes",[]))
    for sub_dataset in sub_datasets:
        out_txt = f"{sub_dataset}.txt"
        os.makedirs(os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "NanoAOD_paths"),exist_ok=True)
        out_file = os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "NanoAOD_paths", out_txt)
        nano_path = datasets_cfg[sub_dataset]["nanoAOD"]
        make_das_filelist(nano_path, out_file, max_files=100)
