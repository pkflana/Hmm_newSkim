#!/usr/bin/env python3

import ROOT
import os
import sys
import subprocess
import argparse

if __name__ == "__main__":
    sys.path.append(os.environ["ANALYSIS_PATH"])

import analysis.utilities as utilities

# ---------------------------------------------------------
# Utils
# ---------------------------------------------------------

def run_cmd(cmd, dryrun=False):

    print("\n" + "=" * 100)
    print(cmd)

    if dryrun:
        return

    subprocess.run(cmd, shell=True, check=True)

# ---------------------------------------------------------
# Arguments
# ---------------------------------------------------------

parser = argparse.ArgumentParser()

parser.add_argument(
    "--era",
    default="Run3_2022"
)

parser.add_argument(
    "--processes",
    nargs="+",
    default=["Data_Muon"]
)

parser.add_argument(
    "--max-files",
    type=int,
    default=-1,
    help="Maximum number of files per dataset"
)

parser.add_argument(
    "--chunk-size",
    type=int,
    default=1,
    help="Number of NanoAOD files per skim job"
)

parser.add_argument(
    "--output-dir",
    default="root://cmseos.fnal.gov//store/user/vdamante/H_mumu/prova_skim"
)

parser.add_argument(
    "--dryrun",
    action="store_true"
)

args = parser.parse_args()

# ---------------------------------------------------------
# Configs
# ---------------------------------------------------------

config = utilities.get_config(
    os.path.join(
        os.environ["ANALYSIS_PATH"],
        "config",
        args.era,
        "maincfg.yaml"
    )
)

processes_cfg = utilities.get_config(
    os.path.join(
        os.environ["ANALYSIS_PATH"],
        "config",
        args.era,
        "process_names.yaml"
    )
)

datasets_cfg = utilities.get_config(
    os.path.join(
        os.environ["ANALYSIS_PATH"],
        "config",
        args.era,
        "samples.yaml"
    )
)

nano_dir_path = os.path.join(
    os.environ["ANALYSIS_PATH"],
    "config",
    args.era,
    "NanoAOD_paths"
)

# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

for process in args.processes:

    print(f"\nConsidering process: {process}")

    sub_datasets = processes_cfg[process].get("datasets", [])

    sub_datasets.extend(
        processes_cfg[process].get("sub_processes", [])
    )

    for sub_dataset in sub_datasets:

        input_txt = os.path.join(
            nano_dir_path,
            f"{sub_dataset}.txt"
        )

        with open(input_txt, "r") as f:
            files = f.read().splitlines()

        if args.max_files > 0:
            files = files[:args.max_files]

        print(
            f"\nDataset: {sub_dataset}"
        )

        print(
            f"Number of input files: {len(files)}"
        )

        # -------------------------------------------------
        # Split in chunks
        # -------------------------------------------------

        chunks = []

        for i in range(0, len(files), args.chunk_size):

            chunk = files[i:i + args.chunk_size]

            chunks.append(chunk)

        print(
            f"Number of jobs/chunks: {len(chunks)}"
        )

        # -------------------------------------------------
        # Run chunks
        # -------------------------------------------------

        for job_id, chunk in enumerate(chunks):

            input_files = [
                f"root://cms-xrd-global.cern.ch/{f}"
                for f in chunk
            ]

            input_string = " ".join([
                f'"{f}"'
                for f in input_files
            ])

            output_file = (
                f"{args.output_dir.rstrip('/')}/"
                f"{sub_dataset}/"
                f"outFile_{job_id}.root"
            )

            command = f"""
python3 analysis/skim.py \
    --era {args.era} \
    --dataset-name "{sub_dataset}" \
    --input-files {input_string} \
    --output-file "{output_file}"
"""

            run_cmd(
                command,
                dryrun=args.dryrun
            )

print("\nDone.")


# import ROOT
# import os
# import sys
# import subprocess
# import argparse
# if __name__ == "__main__":
#     sys.path.append(os.environ["ANALYSIS_PATH"])

# import analysis.utilities as utilities

# def run_cmd(cmd):
#     return subprocess.check_output(cmd, shell=True).decode().splitlines()

# era = "Run3_2022"
# max_files = 2

# config = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "maincfg.yaml"))
# processes_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "process_names.yaml"))
# datasets_cfg = utilities.get_config(os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "samples.yaml"))

# nano_dir_path = os.path.join(os.environ["ANALYSIS_PATH"], "config", era, "NanoAOD_paths")


# input_processes = config.get('process_to_select',[])
# input_processes = ['Data_Muon']

# for process in input_processes:
#     print(f"considering process: {process}")
#     sub_datasets = processes_cfg[process].get("datasets",[])
#     sub_datasets.extend(processes_cfg[process].get("sub_processes",[]))
#     for sub_dataset in sub_datasets:
#         input_file = os.path.join(nano_dir_path, f"{sub_dataset}.txt")
#         with open(input_file, "r") as f:
#             files = f.read().splitlines()
#         print(f"considering sub_dataset: {sub_dataset} with {len(files)} files")
#         k = 0
#         for file in files:
#             if k >= max_files:
#                 break
#             command = f"""python3 analysis/skim.py --era {era} --input-file "root://cms-xrd-global.cern.ch/{file}" --dataset-name "{sub_dataset}" --output-file "root://cmseos.fnal.gov//store/user/vdamante/H_mumu/prova_skim/{sub_dataset}_outFile_{k}.root" """
#             print(command)
#             run_cmd(command)
#             k+=1
