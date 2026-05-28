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

era = "Run3_2022"
max_files = 2

config = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "maincfg.yaml"))
processes_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "process_names.yaml"))
datasets_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "samples.yaml"))

nano_dir_path = os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "NanoAOD_paths")


input_processes = config.get('process_to_select',[])
print(input_processes)

for process in input_processes:
    print(f"considering process: {process}")
    sub_datasets = processes_cfg[process].get("datasets",[])
    sub_datasets.extend(processes_cfg[process].get("sub_processes",[]))
    for sub_dataset in sub_datasets:
        input_file = os.path.join(nano_dir_path, f"{sub_dataset}.txt")
        with open(input_file, "r") as f:
            files = f.read().splitlines()
        print(f"considering sub_dataset: {sub_dataset} with {len(files)} files")
        k = 0
        for file in files:
            if k >= max_files:
                break
            command = f"""python3 analysis/skim.py --era {era} --input-file "root://cms-xrd-global.cern.ch/{file}" --dataset-name "{sub_dataset}" --output-file "root://cmseos.fnal.gov//store/user/vdamante/H_mumu/prova_skim/outFile_{k}.root" """
            print(command)
            run_cmd(command)
            k+=1
