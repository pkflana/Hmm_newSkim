#!/usr/bin/env python3

import argparse
import getpass
import os
import time
import yaml
import htcondor
from collections import defaultdict


# =========================================================
# CLI
# =========================================================

parser = argparse.ArgumentParser(
    description="Submit skim jobs to HTCondor with continuous queue refill."
)
parser.add_argument(
    "-e",
    "--era",
    required=True,
    help="Era to process, e.g. Run3_2022EE",
)
parser.add_argument(
    "--max-parallel-jobs",
    type=int,
    default=None,
    help="Override MAX_PARALLEL_JOBS from the script/default configuration.",
)
parser.add_argument(
    "--poll-interval",
    type=int,
    default=None,
    help="Override polling interval in seconds.",
)
args = parser.parse_args()

era = args.era


# =========================================================
# Environment & Paths
# =========================================================

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_PATH = os.environ.get(
    "ANALYSIS_PATH",
    os.path.abspath(os.path.join(BASE_PATH, "..")),
)

if "ANALYSIS_PATH" not in os.environ:
    print(
        f"Environment variable ANALYSIS_PATH is not set, "
        f"using {ANALYSIS_PATH} as default"
    )
else:
    print(f"Using ANALYSIS_PATH={ANALYSIS_PATH}")

HTCONDOR_PATH = os.path.join(ANALYSIS_PATH, "htcondor")
CONFIG_PATH = os.path.join(ANALYSIS_PATH, "config")

skim_cfg_path = os.path.join(CONFIG_PATH, era, "skim_cfg.yaml")
processes_yaml = os.path.join(CONFIG_PATH, era, "process_names.yaml")
samples_yaml = os.path.join(CONFIG_PATH, era, "samples_withfiles.yaml")

with open(skim_cfg_path, "r") as skimconfig:
    skim_config = yaml.safe_load(skimconfig)

with open(processes_yaml, "r") as processes_config:
    processes_cfg = yaml.safe_load(processes_config)

with open(samples_yaml, "r") as samples_config:
    data = yaml.safe_load(samples_config)


# =========================================================
# HTCondor setup
# =========================================================

schedd = htcondor.Schedd()
credd = htcondor.Credd()
credd.add_user_cred(htcondor.CredTypes.Kerberos, None)


# =========================================================
# Configuration
# =========================================================

flavour = skim_config["job_flavour"]
cpus = skim_config["request_cpus"]
memory = skim_config["request_memory"]
disk = skim_config["request_disk"]

max_files = skim_config["max_files"]
chunk_size = skim_config["chunk_size"]

datasets_whitelist = skim_config.get("datasets_whitelist", [])
process_to_select = skim_config.get("process_to_select", [])

output_directory = os.path.abspath(skim_config["output_dir"])
proxy_location = skim_config["proxy_location"]

submit_jobs = skim_config.get("submit", True)

MAX_PARALLEL_JOBS = args.max_parallel_jobs or skim_config.get("max_parallel_jobs", 6000)
POLL_INTERVAL = args.poll_interval or skim_config.get("poll_interval", 120)

WRITE_MISSING_FILES_DRYRUN = skim_config.get("write_missing_files_dryrun", True)


# =========================================================
# Helpers
# =========================================================

def valid_file(path):
    return os.path.exists(path) and os.path.getsize(path) > 0


def get_output_paths(infile, dataset):
    basename = os.path.basename(infile)

    output_file_root = basename.replace(".root", "_skim.root")
    output_file_json = basename.replace(".root", "_skim_report.json")

    outfile_root = os.path.join(output_directory, era, dataset, output_file_root)
    outfile_json = os.path.join(output_directory, era, dataset, output_file_json)

    return outfile_root, outfile_json


def is_completed(infile, dataset, completed_files_set):
    outfile_root, outfile_json = get_output_paths(infile, dataset)

    in_completed_list = (
        outfile_root in completed_files_set
        and outfile_json in completed_files_set
    )

    exists_on_disk = valid_file(outfile_root) and valid_file(outfile_json)

    return in_completed_list or exists_on_disk


def make_filename_key(infile):
    return os.path.basename(infile).replace(".root", "")


def make_job_key(dataset, filename_key):
    return f"{dataset}::{filename_key}"


def ensure_dataset_dirs(dataset):
    for folder in ["log", "error", "output"]:
        os.makedirs(os.path.join(HTCONDOR_PATH, folder, era, dataset), exist_ok=True)

    os.makedirs(os.path.join(output_directory, era, dataset), exist_ok=True)


def get_condor_status_counts(cluster_id):
    ads = schedd.query(
        constraint=f"ClusterId == {cluster_id}",
        projection=["JobStatus"],
    )

    counts = {
        "idle": 0,
        "running": 0,
        "removed": 0,
        "completed": 0,
        "held": 0,
        "transferring": 0,
        "suspended": 0,
        "unknown": 0,
    }

    for ad in ads:
        status = int(ad.get("JobStatus", -1))

        if status == 1:
            counts["idle"] += 1
        elif status == 2:
            counts["running"] += 1
        elif status == 3:
            counts["removed"] += 1
        elif status == 4:
            counts["completed"] += 1
        elif status == 5:
            counts["held"] += 1
        elif status == 6:
            counts["transferring"] += 1
        elif status == 7:
            counts["suspended"] += 1
        else:
            counts["unknown"] += 1

    counts["in_queue"] = len(ads)

    return counts


def get_active_jobs_count():
    """
    Count jobs that occupy active queue capacity for the current user.

    Here we count idle, running and transferring jobs. Held jobs are reported
    separately by the cluster monitor and do not consume the refill threshold.
    """
    owner = getpass.getuser()

    ads = schedd.query(
        constraint=(
            f'Owner == "{owner}" '
            "&& (JobStatus == 1 || JobStatus == 2 || JobStatus == 6)"
        ),
        projection=["ClusterId"],
    )

    return len(ads)


def write_missing_files_report(dataset, missing_files):
    log_dir = os.path.join(HTCONDOR_PATH, "log", era, dataset)
    os.makedirs(log_dir, exist_ok=True)

    missing_path = os.path.join(log_dir, "missing_files_dryrun.txt")

    with open(missing_path, "w") as mf:
        for infile in missing_files:
            mf.write(f"{infile}\n")

    return missing_path


def print_dryrun_summary(dataset_stats):
    print("\n========== DRY RUN SUMMARY ==========")

    total_files = 0
    total_completed = 0
    total_missing = 0
    total_jobs = 0

    for dataset, stats in dataset_stats.items():
        n_total = stats["total_files"]
        n_completed = stats["completed_files"]
        n_missing = stats["missing_files"]
        n_jobs = stats["jobs_to_run"]

        total_files += n_total
        total_completed += n_completed
        total_missing += n_missing
        total_jobs += n_jobs

        percent = 100.0 * n_completed / n_total if n_total > 0 else 0.0

        print(f"\n{dataset}")
        print(f"  files total      : {n_total}")
        print(f"  files completed  : {n_completed}")
        print(f"  files missing    : {n_missing}")
        print(f"  completion       : {percent:.1f}%")
        print(f"  jobs to submit   : {n_jobs}")

        if stats.get("missing_report"):
            print(f"  missing report   : {stats['missing_report']}")

    global_percent = 100.0 * total_completed / total_files if total_files > 0 else 0.0

    print("\n========== GLOBAL SUMMARY ==========")
    print(f"files total      : {total_files}")
    print(f"files completed  : {total_completed}")
    print(f"files missing    : {total_missing}")
    print(f"completion       : {global_percent:.1f}%")
    print(f"jobs to submit   : {total_jobs}")
    print("====================================\n")


def verify_job_outputs(job_key, global_job_output_map):
    expected = global_job_output_map[job_key]

    missing_or_corrupt = []

    for fpath in expected["root_files"] + expected["json_files"]:
        if not valid_file(fpath):
            missing_or_corrupt.append(fpath)

    return len(missing_or_corrupt) == 0, missing_or_corrupt


def mark_job_completed(job_key, global_job_output_map):
    expected = global_job_output_map[job_key]
    dataset = expected["dataset"]

    completed_files_path = os.path.join(
        HTCONDOR_PATH,
        "log",
        era,
        dataset,
        "completed_files.txt",
    )

    os.makedirs(os.path.dirname(completed_files_path), exist_ok=True)

    with open(completed_files_path, "a") as cf:
        for rf in expected["root_files"]:
            cf.write(f"{rf}\n")
        for jf in expected["json_files"]:
            cf.write(f"{jf}\n")


def write_failed_job_report(
    cluster_id,
    proc_id,
    job_key,
    missing_or_corrupt,
    global_job_output_map,
):
    expected = global_job_output_map[job_key]
    dataset = expected["dataset"]
    filename = expected["filename"]

    log_dir = os.path.join(HTCONDOR_PATH, "log", era, dataset)
    os.makedirs(log_dir, exist_ok=True)

    failed_report = os.path.join(log_dir, "failed_jobs_report.txt")

    with open(failed_report, "a") as f:
        f.write(
            f"Cluster: {cluster_id}.{proc_id} | "
            f"Dataset: {dataset} | "
            f"Filename: {filename} | "
            f"Missing: {missing_or_corrupt}\n"
        )


def print_cluster_status(active_clusters):
    if not active_clusters:
        return

    print("\n[CLUSTERS] Currently tracked clusters:")

    for cluster_id, info in active_clusters.items():
        counts = get_condor_status_counts(cluster_id)
        finished = info["num_proc"] - counts["in_queue"]
        percent = 100.0 * finished / info["num_proc"] if info["num_proc"] > 0 else 0.0

        print(
            f"  Cluster {cluster_id}: "
            f"finished={finished}/{info['num_proc']} ({percent:.1f}%) | "
            f"idle={counts['idle']} running={counts['running']} "
            f"held={counts['held']} transferring={counts['transferring']} "
            f"in_queue={counts['in_queue']}"
        )


def verify_finished_cluster(cluster_id, cluster_info, global_job_output_map):
    num_proc = cluster_info["num_proc"]
    proc_to_job_key = cluster_info["proc_to_job_key"]

    print(f"\n[VERIFY] Cluster {cluster_id} left the queue. Verifying outputs...")

    cluster_success = 0
    cluster_failed = 0

    for proc_id in range(num_proc):
        job_key = proc_to_job_key[proc_id]

        ok, missing_or_corrupt = verify_job_outputs(
            job_key,
            global_job_output_map,
        )

        if ok:
            mark_job_completed(job_key, global_job_output_map)
            cluster_success += 1
        else:
            write_failed_job_report(
                cluster_id,
                proc_id,
                job_key,
                missing_or_corrupt,
                global_job_output_map,
            )
            cluster_failed += 1

    print(f"[CLUSTER SUMMARY] Cluster {cluster_id}")
    print(f"  successful jobs : {cluster_success}")
    print(f"  failed jobs     : {cluster_failed}")

    return cluster_success, cluster_failed


def check_and_verify_finished_clusters(active_clusters, global_job_output_map):
    finished_cluster_ids = []
    success = 0
    failed = 0
    finished = 0

    for cluster_id, cluster_info in list(active_clusters.items()):
        counts = get_condor_status_counts(cluster_id)

        if counts["in_queue"] != 0:
            if counts["held"] > 0:
                print(
                    f"[WARNING] Cluster {cluster_id} has {counts['held']} held jobs. "
                    "Check condor_q -hold for details."
                )
            continue

        cluster_success, cluster_failed = verify_finished_cluster(
            cluster_id,
            cluster_info,
            global_job_output_map,
        )

        success += cluster_success
        failed += cluster_failed
        finished += cluster_info["num_proc"]
        finished_cluster_ids.append(cluster_id)

    for cluster_id in finished_cluster_ids:
        del active_clusters[cluster_id]

    return finished, success, failed


# =========================================================
# Dataset selection
# =========================================================

all_datasets = []

all_datasets.extend(datasets_whitelist)

for process in process_to_select:
    datasets = processes_cfg[process].get("datasets", [])
    subprocesses = processes_cfg[process].get("sub_processes", [])
    all_datasets.extend(datasets + subprocesses)

all_datasets = list(dict.fromkeys(all_datasets))

print(f"Datasets to process: {all_datasets}")


# =========================================================
# FASE 1: scan files + dry run information
# =========================================================

global_condorinputs = []
global_job_output_map = {}

dataset_stats = {}
missing_files_by_dataset = defaultdict(list)

print("\n[INFO] Scanning datasets and checking existing outputs...")

for dataset in all_datasets:
    if dataset not in data or "filelist" not in data[dataset]:
        print(f"[WARNING] You don't have the filelist for: {dataset}")
        continue

    ensure_dataset_dirs(dataset)

    completed_files_path = os.path.join(
        HTCONDOR_PATH,
        "log",
        era,
        dataset,
        "completed_files.txt",
    )

    completed_files_set = set()

    if os.path.exists(completed_files_path):
        with open(completed_files_path, "r") as cf:
            completed_files_set = {line.strip() for line in cf if line.strip()}

    filelist = data[dataset]["filelist"]

    if max_files > 0:
        filelist = filelist[:max_files]

    total_files = len(filelist)
    completed_files_count = 0
    missing_files_count = 0
    jobs_to_run = 0

    for i in range(0, len(filelist), chunk_size):
        chunk = filelist[i:i + chunk_size]

        input_files = []
        output_files_root = []
        output_files_json = []

        for infile in chunk:
            outfile_root, outfile_json = get_output_paths(infile, dataset)

            if is_completed(infile, dataset, completed_files_set):
                completed_files_count += 1
                continue

            missing_files_count += 1
            missing_files_by_dataset[dataset].append(infile)

            input_files.append(infile)
            output_files_root.append(outfile_root)
            output_files_json.append(outfile_json)

        if len(input_files) == 0:
            continue

        input_list = ",".join(input_files)
        output_list = ",".join(output_files_root)

        filename_key = make_filename_key(input_files[0])
        job_key = make_job_key(dataset, filename_key)

        arguments = (
            f"{proxy_location} "
            f"{ANALYSIS_PATH} "
            f"{era} "
            f"{input_list} "
            f"{dataset} "
            f"{output_list}"
        )

        global_condorinputs.append({
            "arguments": arguments,
            "filename": filename_key,
            "dataset": dataset,
            "job_key": job_key,
        })

        global_job_output_map[job_key] = {
            "dataset": dataset,
            "filename": filename_key,
            "input_files": input_files,
            "root_files": output_files_root,
            "json_files": output_files_json,
        }

        jobs_to_run += 1

    missing_report = None

    if WRITE_MISSING_FILES_DRYRUN:
        missing_report = write_missing_files_report(
            dataset,
            missing_files_by_dataset[dataset],
        )

    dataset_stats[dataset] = {
        "total_files": total_files,
        "completed_files": completed_files_count,
        "missing_files": missing_files_count,
        "jobs_to_run": jobs_to_run,
        "missing_report": missing_report,
    }

total_jobs_to_run = len(global_condorinputs)

print_dryrun_summary(dataset_stats)


# =========================================================
# FASE 2: dry run exit
# =========================================================

if not submit_jobs:
    print("[DRY RUN] submit: False")
    print("[DRY RUN] No jobs submitted.")
    raise SystemExit(0)

if total_jobs_to_run == 0:
    print("[INFO] All files are already completed. No jobs to submit.")
    raise SystemExit(0)


# =========================================================
# FASE 3: submit description
# =========================================================

job = htcondor.Submit({
    "executable": os.path.join(HTCONDOR_PATH, "run_skim.sh"),
    "arguments": "$(arguments)",

    "output": os.path.join(
        HTCONDOR_PATH,
        "output",
        era,
        "$(dataset)",
        "$(filename).$(ClusterId).$(ProcId).out",
    ),

    "error": os.path.join(
        HTCONDOR_PATH,
        "error",
        era,
        "$(dataset)",
        "$(filename).$(ClusterId).$(ProcId).err",
    ),

    "log": os.path.join(
        HTCONDOR_PATH,
        "log",
        era,
        "$(dataset)",
        "$(filename).$(ClusterId).$(ProcId).log",
    ),

    "universe": "vanilla",
    "Requirements": '(OpSysAndVer =?= "AlmaLinux9")',
    "+JobFlavour": flavour,
    "+JobKey": '"$(job_key)"',
    "RequestCpus": str(cpus),
    "request_memory": str(memory),
    "request_disk": str(disk),
    "max_retries": "1",
    "batch_name": f"Skim_{era}_Global",
})

job["MY.SendCredential"] = "true"


# =========================================================
# FASE 4: continuous submit + monitoring
# =========================================================

print("\n[INFO] Starting continuous submission...")
print(f"[INFO] MAX_PARALLEL_JOBS = {MAX_PARALLEL_JOBS}")
print(f"[INFO] POLL_INTERVAL     = {POLL_INTERVAL}s")

chunk_idx = 0
active_clusters = {}

global_submitted_jobs = 0
global_finished_jobs = 0
global_success_jobs = 0
global_failed_jobs = 0

while chunk_idx < len(global_condorinputs) or active_clusters:

    finished, success, failed = check_and_verify_finished_clusters(
        active_clusters,
        global_job_output_map,
    )

    if finished > 0:
        global_finished_jobs += finished
        global_success_jobs += success
        global_failed_jobs += failed

        print(
            f"[GLOBAL STATUS] "
            f"submitted={global_submitted_jobs}/{total_jobs_to_run}, "
            f"finished={global_finished_jobs}/{total_jobs_to_run}, "
            f"success={global_success_jobs}, "
            f"failed={global_failed_jobs}"
        )

    if chunk_idx < len(global_condorinputs):
        current_active = get_active_jobs_count()
        available_slots = MAX_PARALLEL_JOBS - current_active
        remaining_jobs = len(global_condorinputs) - chunk_idx

        if available_slots > 0:
            n_to_submit = min(available_slots, remaining_jobs)
            sub_chunk = global_condorinputs[chunk_idx:chunk_idx + n_to_submit]
            chunk_idx += len(sub_chunk)

            print(
                f"\n[SUBMIT] active={current_active}, "
                f"available_slots={available_slots}, "
                f"submitting={len(sub_chunk)}, "
                f"remaining_after_submit={len(global_condorinputs) - chunk_idx}"
            )

            submit_result = schedd.submit(job, itemdata=iter(sub_chunk))

            cluster_id = submit_result.cluster()
            num_proc = submit_result.num_procs()

            proc_to_job_key = {
                proc_id: sub_chunk[proc_id]["job_key"]
                for proc_id in range(num_proc)
            }

            active_clusters[cluster_id] = {
                "num_proc": num_proc,
                "proc_to_job_key": proc_to_job_key,
            }

            global_submitted_jobs += num_proc

            print(f"[SUBMIT] Cluster ID: {cluster_id}")
            print(f"[SUBMIT] Jobs in cluster: {num_proc}")
            print(
                f"[GLOBAL STATUS] "
                f"submitted={global_submitted_jobs}/{total_jobs_to_run}, "
                f"finished={global_finished_jobs}/{total_jobs_to_run}, "
                f"success={global_success_jobs}, "
                f"failed={global_failed_jobs}"
            )
        else:
            print(
                f"\n[QUEUE] Queue full: {current_active} active jobs. "
                f"Waiting {POLL_INTERVAL}s..."
            )
            print_cluster_status(active_clusters)
    else:
        print(
            f"\n[MONITOR] All jobs submitted. "
            f"Waiting for {len(active_clusters)} active clusters to finish..."
        )
        print_cluster_status(active_clusters)

    if chunk_idx < len(global_condorinputs) or active_clusters:
        time.sleep(POLL_INTERVAL)


# =========================================================
# Final summary
# =========================================================

print("\n========== FINAL SUMMARY ==========")
print(f"submitted jobs : {global_submitted_jobs}")
print(f"finished jobs  : {global_finished_jobs}")
print(f"successful     : {global_success_jobs}")
print(f"failed         : {global_failed_jobs}")
print("===================================\n")

# import os
# import time
# import yaml
# import htcondor
# from collections import defaultdict

# # =========================================================
# # Environment & Paths
# # =========================================================

# BASE_PATH = os.path.dirname(os.path.abspath(__file__))
# ANALYSIS_PATH = os.path.abspath(os.path.join(BASE_PATH, ".."))

# print(f"Environment variable ANALYSIS_PATH is not set, using {ANALYSIS_PATH} as default")

# HTCONDOR_PATH = os.path.join(ANALYSIS_PATH, "htcondor")
# CONFIG_PATH = os.path.join(ANALYSIS_PATH, "config")

# era = "Run3_2022EE"

# skim_cfg_path = os.path.join(CONFIG_PATH, era, "skim_cfg.yaml")
# processes_yaml = os.path.join(CONFIG_PATH, era, "process_names.yaml")
# samples_yaml = os.path.join(CONFIG_PATH, era, "samples_withfiles.yaml")

# with open(skim_cfg_path, "r") as skimconfig:
#     skim_config = yaml.safe_load(skimconfig)

# with open(processes_yaml, "r") as processes_config:
#     processes_cfg = yaml.safe_load(processes_config)

# with open(samples_yaml, "r") as samples_config:
#     data = yaml.safe_load(samples_config)

# # =========================================================
# # HTCondor setup
# # =========================================================

# schedd = htcondor.Schedd()
# credd = htcondor.Credd()
# credd.add_user_cred(htcondor.CredTypes.Kerberos, None)

# # =========================================================
# # Configuration
# # =========================================================

# flavour = skim_config["job_flavour"]
# cpus = skim_config["request_cpus"]
# memory = skim_config["request_memory"]
# disk = skim_config["request_disk"]

# max_files = skim_config["max_files"]
# chunk_size = skim_config["chunk_size"]

# datasets_whitelist = skim_config.get("datasets_whitelist", [])
# process_to_select = skim_config.get("process_to_select", [])

# output_directory = os.path.abspath(skim_config["output_dir"])
# proxy_location = skim_config["proxy_location"]

# submit_jobs = skim_config.get("submit", True)

# MAX_PARALLEL_JOBS = 6000
# POLL_INTERVAL = 120

# WRITE_MISSING_FILES_DRYRUN = True

# # =========================================================
# # Helpers
# # =========================================================

# def valid_file(path):
#     return os.path.exists(path) and os.path.getsize(path) > 0


# def get_output_paths(infile, dataset):
#     basename = os.path.basename(infile)

#     output_file_root = basename.replace(".root", "_skim.root")
#     output_file_json = basename.replace(".root", "_skim_report.json")

#     outfile_root = os.path.join(output_directory, era, dataset, output_file_root)
#     outfile_json = os.path.join(output_directory, era, dataset, output_file_json)

#     return outfile_root, outfile_json


# def is_completed(infile, dataset, completed_files_set):
#     outfile_root, outfile_json = get_output_paths(infile, dataset)

#     in_completed_list = (
#         outfile_root in completed_files_set
#         and outfile_json in completed_files_set
#     )

#     exists_on_disk = valid_file(outfile_root) and valid_file(outfile_json)

#     return in_completed_list or exists_on_disk


# def make_filename_key(infile):
#     return os.path.basename(infile).replace(".root", "")


# def make_job_key(dataset, filename_key):
#     return f"{dataset}::{filename_key}"


# def ensure_dataset_dirs(dataset):
#     for folder in ["log", "error", "output"]:
#         os.makedirs(os.path.join(HTCONDOR_PATH, folder, era, dataset), exist_ok=True)

#     os.makedirs(os.path.join(output_directory, era, dataset), exist_ok=True)


# def get_condor_status_counts(cluster_id):
#     ads = schedd.query(
#         constraint=f"ClusterId == {cluster_id}",
#         projection=["JobStatus"],
#     )

#     counts = {
#         "idle": 0,
#         "running": 0,
#         "removed": 0,
#         "completed": 0,
#         "held": 0,
#         "transferring": 0,
#         "suspended": 0,
#         "unknown": 0,
#     }

#     for ad in ads:
#         status = int(ad.get("JobStatus", -1))

#         if status == 1:
#             counts["idle"] += 1
#         elif status == 2:
#             counts["running"] += 1
#         elif status == 3:
#             counts["removed"] += 1
#         elif status == 4:
#             counts["completed"] += 1
#         elif status == 5:
#             counts["held"] += 1
#         elif status == 6:
#             counts["transferring"] += 1
#         elif status == 7:
#             counts["suspended"] += 1
#         else:
#             counts["unknown"] += 1

#     counts["in_queue"] = len(ads)

#     return counts


# def get_active_jobs_count():
#     ads = schedd.query(
#         constraint=(
#             f'Owner == "{os.getlogin()}" '
#             "&& (JobStatus == 1 || JobStatus == 2)"
#         ),
#         projection=["ClusterId"],
#     )

#     return len(ads)


# def write_missing_files_report(dataset, missing_files):
#     log_dir = os.path.join(HTCONDOR_PATH, "log", era, dataset)
#     os.makedirs(log_dir, exist_ok=True)

#     missing_path = os.path.join(log_dir, "missing_files_dryrun.txt")

#     with open(missing_path, "w") as mf:
#         for infile in missing_files:
#             mf.write(f"{infile}\n")

#     return missing_path


# def print_dryrun_summary(dataset_stats):
#     print("\n========== DRY RUN SUMMARY ==========")

#     total_files = 0
#     total_completed = 0
#     total_missing = 0
#     total_jobs = 0

#     for dataset, stats in dataset_stats.items():
#         n_total = stats["total_files"]
#         n_completed = stats["completed_files"]
#         n_missing = stats["missing_files"]
#         n_jobs = stats["jobs_to_run"]

#         total_files += n_total
#         total_completed += n_completed
#         total_missing += n_missing
#         total_jobs += n_jobs

#         percent = 100.0 * n_completed / n_total if n_total > 0 else 0.0

#         print(f"\n{dataset}")
#         print(f"  files total      : {n_total}")
#         print(f"  files completed  : {n_completed}")
#         print(f"  files missing    : {n_missing}")
#         print(f"  completion       : {percent:.1f}%")
#         print(f"  jobs to submit   : {n_jobs}")

#         if stats.get("missing_report"):
#             print(f"  missing report   : {stats['missing_report']}")

#     global_percent = 100.0 * total_completed / total_files if total_files > 0 else 0.0

#     print("\n========== GLOBAL SUMMARY ==========")
#     print(f"files total      : {total_files}")
#     print(f"files completed  : {total_completed}")
#     print(f"files missing    : {total_missing}")
#     print(f"completion       : {global_percent:.1f}%")
#     print(f"jobs to submit   : {total_jobs}")
#     print("====================================\n")


# def verify_job_outputs(job_key, global_job_output_map):
#     expected = global_job_output_map[job_key]

#     missing_or_corrupt = []

#     for fpath in expected["root_files"] + expected["json_files"]:
#         if not valid_file(fpath):
#             missing_or_corrupt.append(fpath)

#     return len(missing_or_corrupt) == 0, missing_or_corrupt


# def mark_job_completed(job_key, global_job_output_map):
#     expected = global_job_output_map[job_key]
#     dataset = expected["dataset"]

#     completed_files_path = os.path.join(
#         HTCONDOR_PATH,
#         "log",
#         era,
#         dataset,
#         "completed_files.txt",
#     )

#     os.makedirs(os.path.dirname(completed_files_path), exist_ok=True)

#     with open(completed_files_path, "a") as cf:
#         for rf in expected["root_files"]:
#             cf.write(f"{rf}\n")
#         for jf in expected["json_files"]:
#             cf.write(f"{jf}\n")


# def write_failed_job_report(cluster_id, proc_id, job_key, missing_or_corrupt, global_job_output_map):
#     expected = global_job_output_map[job_key]
#     dataset = expected["dataset"]
#     filename = expected["filename"]

#     log_dir = os.path.join(HTCONDOR_PATH, "log", era, dataset)
#     os.makedirs(log_dir, exist_ok=True)

#     failed_report = os.path.join(log_dir, "failed_jobs_report.txt")

#     with open(failed_report, "a") as f:
#         f.write(
#             f"Cluster: {cluster_id}.{proc_id} | "
#             f"Dataset: {dataset} | "
#             f"Filename: {filename} | "
#             f"Missing: {missing_or_corrupt}\n"
#         )


# # =========================================================
# # Dataset selection
# # =========================================================

# all_datasets = []

# all_datasets.extend(datasets_whitelist)

# for process in process_to_select:
#     datasets = processes_cfg[process].get("datasets", [])
#     subprocesses = processes_cfg[process].get("sub_processes", [])
#     all_datasets.extend(datasets + subprocesses)

# all_datasets = list(dict.fromkeys(all_datasets))

# print(f"Datasets to process: {all_datasets}")

# # =========================================================
# # FASE 1: scan files + dry run information
# # =========================================================

# global_condorinputs = []
# global_job_output_map = {}

# dataset_stats = {}
# missing_files_by_dataset = defaultdict(list)

# print("\n[INFO] Scanning datasets and checking existing outputs...")

# for dataset in all_datasets:
#     if dataset not in data or "filelist" not in data[dataset]:
#         print(f"[WARNING] You don't have the filelist for: {dataset}")
#         continue

#     ensure_dataset_dirs(dataset)

#     completed_files_path = os.path.join(
#         HTCONDOR_PATH,
#         "log",
#         era,
#         dataset,
#         "completed_files.txt",
#     )

#     completed_files_set = set()

#     if os.path.exists(completed_files_path):
#         with open(completed_files_path, "r") as cf:
#             completed_files_set = {line.strip() for line in cf if line.strip()}

#     filelist = data[dataset]["filelist"]

#     if max_files > 0:
#         filelist = filelist[:max_files]

#     total_files = len(filelist)
#     completed_files_count = 0
#     missing_files_count = 0
#     jobs_to_run = 0

#     for i in range(0, len(filelist), chunk_size):
#         chunk = filelist[i:i + chunk_size]

#         input_files = []
#         output_files_root = []
#         output_files_json = []

#         for infile in chunk:
#             outfile_root, outfile_json = get_output_paths(infile, dataset)

#             if is_completed(infile, dataset, completed_files_set):
#                 completed_files_count += 1
#                 continue

#             missing_files_count += 1
#             missing_files_by_dataset[dataset].append(infile)

#             input_files.append(infile)
#             output_files_root.append(outfile_root)
#             output_files_json.append(outfile_json)

#         if len(input_files) == 0:
#             continue

#         input_list = ",".join(input_files)
#         output_list = ",".join(output_files_root)

#         filename_key = make_filename_key(input_files[0])
#         job_key = make_job_key(dataset, filename_key)

#         arguments = (
#             f"{proxy_location} "
#             f"{ANALYSIS_PATH} "
#             f"{era} "
#             f"{input_list} "
#             f"{dataset} "
#             f"{output_list}"
#         )

#         global_condorinputs.append({
#             "arguments": arguments,
#             "filename": filename_key,
#             "dataset": dataset,
#             "job_key": job_key,
#         })

#         global_job_output_map[job_key] = {
#             "dataset": dataset,
#             "filename": filename_key,
#             "input_files": input_files,
#             "root_files": output_files_root,
#             "json_files": output_files_json,
#         }

#         jobs_to_run += 1

#     missing_report = None

#     if WRITE_MISSING_FILES_DRYRUN:
#         missing_report = write_missing_files_report(
#             dataset,
#             missing_files_by_dataset[dataset],
#         )

#     dataset_stats[dataset] = {
#         "total_files": total_files,
#         "completed_files": completed_files_count,
#         "missing_files": missing_files_count,
#         "jobs_to_run": jobs_to_run,
#         "missing_report": missing_report,
#     }

# total_jobs_to_run = len(global_condorinputs)

# print_dryrun_summary(dataset_stats)

# # =========================================================
# # FASE 2: dry run exit
# # =========================================================

# if not submit_jobs:
#     print("[DRY RUN] submit: False")
#     print("[DRY RUN] No jobs submitted.")
#     raise SystemExit(0)

# if total_jobs_to_run == 0:
#     print("[INFO] All files are already completed. No jobs to submit.")
#     raise SystemExit(0)

# # =========================================================
# # FASE 3: submit description
# # =========================================================

# job = htcondor.Submit({
#     "executable": os.path.join(HTCONDOR_PATH, "run_skim.sh"),
#     "arguments": "$(arguments)",

#     "output": os.path.join(
#         HTCONDOR_PATH,
#         "output",
#         era,
#         "$(dataset)",
#         "$(filename).$(ClusterId).$(ProcId).out",
#     ),

#     "error": os.path.join(
#         HTCONDOR_PATH,
#         "error",
#         era,
#         "$(dataset)",
#         "$(filename).$(ClusterId).$(ProcId).err",
#     ),

#     # Condor event log separato job-per-job
#     "log": os.path.join(
#         HTCONDOR_PATH,
#         "log",
#         era,
#         "$(dataset)",
#         "$(filename).$(ClusterId).$(ProcId).log",
#     ),

#     "universe": "vanilla",
#     "Requirements": '(OpSysAndVer =?= "AlmaLinux9")',
#     "+JobFlavour": flavour,
#     "+JobKey": '"$(job_key)"',
#     "RequestCpus": cpus,
#     "request_memory": memory,
#     "request_disk": disk,
#     "max_retries": "1",
#     "batch_name": f"Skim_{era}_Global",
# })

# job["MY.SendCredential"] = "true"

# # =========================================================
# # FASE 4: submit + monitoring via schedd.query
# # =========================================================

# print("\n[INFO] Starting submission...")

# chunk_idx = 0

# global_submitted_jobs = 0
# global_finished_jobs = 0
# global_success_jobs = 0
# global_failed_jobs = 0

# while chunk_idx < len(global_condorinputs):

#     while True:
#         current_active = get_active_jobs_count()

#         if current_active < MAX_PARALLEL_JOBS:
#             available_slots = MAX_PARALLEL_JOBS - current_active
#             break

#         print(
#             f"[QUEUE] Queue full: {current_active} active jobs. "
#             f"Waiting {POLL_INTERVAL}s..."
#         )
#         time.sleep(POLL_INTERVAL)

#     sub_chunk = global_condorinputs[chunk_idx:chunk_idx + available_slots]
#     chunk_idx += len(sub_chunk)

#     print(f"\n[SUBMIT] Submitting block of {len(sub_chunk)} jobs...")

#     submit_result = schedd.submit(job, itemdata=iter(sub_chunk))

#     cluster_id = submit_result.cluster()
#     num_proc = submit_result.num_procs()

#     global_submitted_jobs += num_proc

#     print(f"[SUBMIT] Cluster ID: {cluster_id}")
#     print(f"[SUBMIT] Jobs in cluster: {num_proc}")

#     proc_to_job_key = {
#         proc_id: sub_chunk[proc_id]["job_key"]
#         for proc_id in range(num_proc)
#     }

#     last_printed_finished = -1
#     while True:
#         counts = get_condor_status_counts(cluster_id)

#         in_queue = counts["in_queue"]
#         finished_for_cluster = num_proc - in_queue

#         cluster_percent = 100.0 * finished_for_cluster / num_proc
#         global_projected_finished = global_finished_jobs + finished_for_cluster
#         global_percent = 100.0 * global_projected_finished / total_jobs_to_run

#         print(
#             f"[MONITOR] Cluster {cluster_id}: "
#             f"finished {finished_for_cluster}/{num_proc} "
#             f"({cluster_percent:.1f}%) | "
#             f"idle={counts['idle']} "
#             f"running={counts['running']} "
#             f"held={counts['held']} "
#             f"transferring={counts['transferring']} | "
#             f"global projected {global_projected_finished}/{total_jobs_to_run} "
#             f"({global_percent:.1f}%)",
#             flush=True,
#         )

#         if in_queue == 0:
#             break

#         time.sleep(POLL_INTERVAL)

#     # while True:
#     #     counts = get_condor_status_counts(cluster_id)

#     #     in_queue = counts["in_queue"]
#     #     finished_for_cluster = num_proc - in_queue

#     #     if finished_for_cluster != last_printed_finished:
#     #         cluster_percent = 100.0 * finished_for_cluster / num_proc
#     #         global_projected_finished = global_finished_jobs + finished_for_cluster
#     #         global_percent = 100.0 * global_projected_finished / total_jobs_to_run

#     #         print(
#     #             f"[MONITOR] Cluster {cluster_id}: "
#     #             f"finished {finished_for_cluster}/{num_proc} "
#     #             f"({cluster_percent:.1f}%) | "
#     #             f"idle={counts['idle']} "
#     #             f"running={counts['running']} "
#     #             f"held={counts['held']} "
#     #             f"transferring={counts['transferring']} | "
#     #             f"global projected {global_projected_finished}/{total_jobs_to_run} "
#     #             f"({global_percent:.1f}%)"
#     #         )

#     #         last_printed_finished = finished_for_cluster

#     #     if in_queue == 0:
#     #         break

#     #     if counts["held"] > 0:
#     #         print(
#     #             f"[WARNING] Cluster {cluster_id} has {counts['held']} held jobs. "
#     #             "Check condor_q -hold for details."
#     #         )

#     #     time.sleep(POLL_INTERVAL)

#     print(f"[VERIFY] Cluster {cluster_id} left the queue. Verifying outputs...")

#     cluster_success = 0
#     cluster_failed = 0

#     for proc_id, job_key in proc_to_job_key.items():
#         ok, missing_or_corrupt = verify_job_outputs(
#             job_key,
#             global_job_output_map,
#         )

#         if ok:
#             mark_job_completed(job_key, global_job_output_map)
#             cluster_success += 1
#             global_success_jobs += 1
#         else:
#             write_failed_job_report(
#                 cluster_id,
#                 proc_id,
#                 job_key,
#                 missing_or_corrupt,
#                 global_job_output_map,
#             )
#             cluster_failed += 1
#             global_failed_jobs += 1

#     global_finished_jobs += num_proc

#     print(f"[CLUSTER SUMMARY] Cluster {cluster_id}")
#     print(f"  successful jobs : {cluster_success}")
#     print(f"  failed jobs     : {cluster_failed}")

#     print(
#         f"[GLOBAL STATUS] "
#         f"finished={global_finished_jobs}/{total_jobs_to_run}, "
#         f"success={global_success_jobs}, "
#         f"failed={global_failed_jobs}"
#     )

# # =========================================================
# # Final summary
# # =========================================================

# print("\n========== FINAL SUMMARY ==========")
# print(f"submitted jobs : {global_submitted_jobs}")
# print(f"finished jobs  : {global_finished_jobs}")
# print(f"successful     : {global_success_jobs}")
# print(f"failed         : {global_failed_jobs}")
# print("===================================\n")