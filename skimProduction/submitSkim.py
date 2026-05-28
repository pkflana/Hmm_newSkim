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
    os.makedirs(path, exist_ok=True)


# ---------------------------------------------------------
# Arguments
# ---------------------------------------------------------

parser = argparse.ArgumentParser()
parser.add_argument("--era", required=True)
parser.add_argument("--dryrun", action="store_true")
args = parser.parse_args()

# ---------------------------------------------------------
# Load config
# ---------------------------------------------------------

with open(f"config/{args.era}/maincfg.yaml") as f:
    era_cfg = yaml.safe_load(f)

with open(f"config/{args.era}/skim_cfg.yaml") as f:
    skim_cfg = yaml.safe_load(f)

cfg = {**era_cfg, **skim_cfg}

era = cfg["era"]
processes = cfg["process_to_select"]

chunk_size = cfg.get("chunk_size", 1)
max_files = cfg.get("max_files", -1)

output_dir = cfg["final_skim_folder"]
submit = cfg.get("submit", True)

# ---------------------------------------------------------
# CMSSW / analysis config
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
# GLOBAL job counter
# ---------------------------------------------------------

job_counter = 0

# ---------------------------------------------------------
# LOOP OVER PROCESSES + DATASETS
# ---------------------------------------------------------

for process in processes:

    print(f"\n>>> Process: {process}")

    sub_datasets = processes_cfg[process].get("datasets", [])
    sub_datasets.extend(processes_cfg[process].get("sub_processes", []))

    for sub_dataset in sub_datasets:

        print(f"  -> Dataset: {sub_dataset}")

        # -------------------------------------------------
        # JOB DIR (per dataset)
        # -------------------------------------------------

        job_dir = os.path.join(
            os.environ["ANALYSIS_PATH"],
            "skimProduction",
            "condor",
            era,
            sub_dataset
        )

        os.makedirs(job_dir, exist_ok=True)
        os.makedirs(os.path.join(job_dir, "logs"), exist_ok=True)

        arguments_file = os.path.join(job_dir, "arguments.txt")
        submit_file = os.path.join(job_dir, f"condor_{era}.sub")

        open(arguments_file, "w").close()

        # -------------------------------------------------
        # INPUT FILES
        # -------------------------------------------------

        input_txt = os.path.join(
            nano_dir_path,
            f"{sub_dataset}.txt"
        )

        with open(input_txt) as f:
            files = f.read().splitlines()

        if max_files > 0:
            files = files[:max_files]

        print(f"     files: {len(files)}")

        # -------------------------------------------------
        # EOS OUTPUT DIR
        # -------------------------------------------------

        dataset_dir = os.path.join(output_dir, era, sub_dataset)
        eos_mkdir(dataset_dir)

        # -------------------------------------------------
        # CHUNKING
        # -------------------------------------------------

        chunks = [
            files[i:i + chunk_size]
            for i in range(0, len(files), chunk_size)
        ]

        print(f"     jobs: {len(chunks)}")

        # -------------------------------------------------
        # WRITE ARGUMENTS
        # -------------------------------------------------

        with open(arguments_file, "w") as f:

            for job_id, chunk in enumerate(chunks):

                input_files = [
                    f"root://cms-xrd-global.cern.ch/{x}"
                    for x in chunk
                ]

                output_file = f"{dataset_dir}/outFile_{job_id}.root"

                f.write(
                    f"{era}@@@"
                    f"{sub_dataset}@@@"
                    f"{','.join(input_files)}@@@"
                    f"{output_file}\n"
                )

                job_counter += 1

        # -------------------------------------------------
        # WRITE CONDOR SUB
        # -------------------------------------------------

        job_sh = os.path.join(
            os.environ["ANALYSIS_PATH"],
            "skimProduction",
            "condor",
            "job.sh"
        )

        with open(submit_file, "w") as subf:

            subf.write(f"""
executable = {job_sh}
arguments  = $(ARGS)

output = {job_dir}/logs/job_$(ClusterId)_$(ProcId).out
error  = {job_dir}/logs/job_$(ClusterId)_$(ProcId).err
log    = {job_dir}/logs/job_$(ClusterId)_$(ProcId).log

request_cpus   = 1
request_memory = 4 GB

+JobFlavour = "{cfg.get('job_flavour','espresso')}"

should_transfer_files   = YES
when_to_transfer_output = ON_EXIT

transfer_input_files = framework.tar.gz

getenv = True

queue ARGS from (
""")

            with open(arguments_file) as argf:
                for line in argf:
                    era_, ds_, inputs_, out_ = line.strip().split("@@@")
                    subf.write(f"{era_} {ds_} {inputs_} {out_}\n")

            subf.write(")\n")

        print(f"  created:")
        print(f"    {submit_file}")
        print(f"    {arguments_file}")

# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------

print(f"\nTOTAL JOBS: {job_counter}")

# ---------------------------------------------------------
# SUBMIT
# ---------------------------------------------------------

if submit:

    if args.dryrun:
        print("\n[DRYRUN] condor_submit per dataset")
    else:
        condor_base = os.path.join(
            os.environ["ANALYSIS_PATH"],
            "skimProduction",
            "condor",
            era
        )

        for root, _, files in os.walk(condor_base):
            for f in files:
                if f.startswith("condor_") and f.endswith(".sub"):
                    run_cmd(f"condor_submit {os.path.join(root, f)}")