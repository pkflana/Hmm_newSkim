#!/usr/bin/env python3

import os
import sys
import yaml
import argparse
import subprocess

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])

import analysis.utilities as utilities

# ---------------------------------------------------------
# Utils
# ---------------------------------------------------------

def run_cmd(cmd):
    print(cmd)
    subprocess.run(cmd, shell=True, check=True)

def eos_mkdir(path):
    # path MUST be /store/... not root://...
    if path.startswith("root://"):
        path = path.split("root://cmseos.fnal.gov/")[-1]

    if not path.startswith("/"):
        path = "/" + path

    os.system(f"xrdfs root://cmseos.fnal.gov mkdir -p {path}")

# ---------------------------------------------------------
# Arguments
# ---------------------------------------------------------

parser = argparse.ArgumentParser()

parser.add_argument("--cfg", required=True)
parser.add_argument("--dryrun", action="store_true")

args = parser.parse_args()

# ---------------------------------------------------------
# Load config
# ---------------------------------------------------------

with open(args.cfg) as f:
    cfg = yaml.safe_load(f)

era = cfg["era"]
processes = cfg["processes"]
chunk_size = cfg.get("chunk_size", 1)
max_files = cfg.get("max_files", -1)

output_dir = cfg["output_dir"]
submit = cfg.get("submit", True)

# ---------------------------------------------------------
# Load CMSSW config
# ---------------------------------------------------------

processes_cfg = utilities.get_config(
    os.path.join(
        os.environ["ANALYSIS_PATH"],
        "config",
        era,
        "process_names.yaml"
    )
)

nano_dir_path = os.path.join(
    os.environ["ANALYSIS_PATH"],
    "config",
    era,
    "NanoAOD_paths"
)

# ---------------------------------------------------------
# Condor setup
# ---------------------------------------------------------

job_dir = os.path.join(os.environ["ANALYSIS_PATH"], "skimProduction","condor")
os.makedirs(job_dir, exist_ok=True)
os.makedirs(f"{job_dir}/logs", exist_ok=True)

arguments_file = f"{job_dir}/arguments.txt"
open(arguments_file, "w").close()

job_counter = 0

# ---------------------------------------------------------
# Loop over processes
# ---------------------------------------------------------

for process in processes:

    print(f"\n>>> Process: {process}")

    sub_datasets = processes_cfg[process].get("datasets", [])
    sub_datasets.extend(processes_cfg[process].get("sub_processes", []))

    for sub_dataset in sub_datasets:

        input_txt = os.path.join(
            nano_dir_path,
            f"{sub_dataset}.txt"
        )

        with open(input_txt) as f:
            files = f.read().splitlines()

        if max_files > 0:
            files = files[:max_files]

        print(f"  Dataset: {sub_dataset} ({len(files)} files)")

        # create dataset output dir on EOS
        dataset_dir = f"{output_dir.rstrip('/')}/{sub_dataset}"
        eos_mkdir(dataset_dir)

        # chunking
        chunks = [
            files[i:i+chunk_size]
            for i in range(0, len(files), chunk_size)
        ]

        print(f"  -> {len(chunks)} jobs")

        # write arguments
        with open(arguments_file, "a") as f:

            for job_id, chunk in enumerate(chunks):

                input_files = [
                    f"root://cms-xrd-global.cern.ch/{x}"
                    for x in chunk
                ]

                output_file = (
                    f"{dataset_dir}/outFile_{job_id}.root"
                )

                f.write(
                    f"{era}@@@"
                    f"{sub_dataset}@@@"
                    f"{','.join(input_files)}@@@"
                    f"{output_file}\n"
                )

                job_counter += 1

print(f"\nTotal jobs: {job_counter}")

# ---------------------------------------------------------
# Condor submit file
# ---------------------------------------------------------

submit_file = f"{job_dir}/condor.sub"


with open(submit_file, "w") as subf:

    subf.write(f"""
executable = {job_dir}/job.sh
arguments  = $(ARGS)

output = {job_dir}/logs/job_$(ClusterId)_$(ProcId).out
error  = {job_dir}/logs/job_$(ClusterId)_$(ProcId).err
log    = {job_dir}/logs/job_$(ClusterId)_$(ProcId).log

request_cpus   = 1
request_memory = 4 GB

+JobFlavour = "{cfg.get('job_flavour','espresso')}"

getenv = True
environment = "ANALYSIS_PATH=$(ENV.ANALYSIS_PATH)"

should_transfer_files   = YES
when_to_transfer_output = ON_EXIT
transfer_input_files    = skimProduction/, analysis/, corrections/, config/, env.sh

queue ARGS from (
""")

    with open(arguments_file) as argf:

        for line in argf:
            era_, ds_, inputs_, out_ = line.strip().split("@@@")

            subf.write(f"{era_} {ds_} {inputs_} {out_}\n")

    subf.write(")\n")

# ---------------------------------------------------------
# Submit
# ---------------------------------------------------------

print(f"\nCreated:")
print(f"  - {submit_file}")
print(f"  - {arguments_file}")

if submit:

    if args.dryrun:
        print("\n[DRYRUN] condor_submit", submit_file)
    else:
        run_cmd(f"condor_submit {submit_file}")
