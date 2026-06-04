import os
import time
import yaml
import htcondor
from collections import defaultdict

# =========================================================
# Environment & Paths
# =========================================================

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_PATH = os.path.abspath(os.path.join(BASE_PATH, ".."))

print(f"Environment variable ANALYSIS_PATH is not set, using {ANALYSIS_PATH} as default")

HTCONDOR_PATH = os.path.join(ANALYSIS_PATH, "htcondor")
CONFIG_PATH = os.path.join(ANALYSIS_PATH, "config")

era = "Run3_2024"

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

MAX_PARALLEL_JOBS = 2000
POLL_INTERVAL = 30

WRITE_MISSING_FILES_DRYRUN = True

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
    ads = schedd.query(
        constraint=(
            f'Owner == "{os.getlogin()}" '
            "&& (JobStatus == 1 || JobStatus == 2)"
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


def write_failed_job_report(cluster_id, proc_id, job_key, missing_or_corrupt, global_job_output_map):
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

    # Condor event log separato job-per-job
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
    "RequestCpus": cpus,
    "request_memory": memory,
    "request_disk": disk,
    "max_retries": "1",
    "batch_name": f"Skim_{era}_Global",
})

job["MY.SendCredential"] = "true"

# =========================================================
# FASE 4: submit + monitoring via schedd.query
# =========================================================

print("\n[INFO] Starting submission...")

chunk_idx = 0

global_submitted_jobs = 0
global_finished_jobs = 0
global_success_jobs = 0
global_failed_jobs = 0

while chunk_idx < len(global_condorinputs):

    while True:
        current_active = get_active_jobs_count()

        if current_active < MAX_PARALLEL_JOBS:
            available_slots = MAX_PARALLEL_JOBS - current_active
            break

        print(
            f"[QUEUE] Queue full: {current_active} active jobs. "
            f"Waiting {POLL_INTERVAL}s..."
        )
        time.sleep(POLL_INTERVAL)

    sub_chunk = global_condorinputs[chunk_idx:chunk_idx + available_slots]
    chunk_idx += len(sub_chunk)

    print(f"\n[SUBMIT] Submitting block of {len(sub_chunk)} jobs...")

    submit_result = schedd.submit(job, itemdata=iter(sub_chunk))

    cluster_id = submit_result.cluster()
    num_proc = submit_result.num_procs()

    global_submitted_jobs += num_proc

    print(f"[SUBMIT] Cluster ID: {cluster_id}")
    print(f"[SUBMIT] Jobs in cluster: {num_proc}")

    proc_to_job_key = {
        proc_id: sub_chunk[proc_id]["job_key"]
        for proc_id in range(num_proc)
    }

    last_printed_finished = -1

    while True:
        counts = get_condor_status_counts(cluster_id)

        in_queue = counts["in_queue"]
        finished_for_cluster = num_proc - in_queue

        if finished_for_cluster != last_printed_finished:
            cluster_percent = 100.0 * finished_for_cluster / num_proc
            global_projected_finished = global_finished_jobs + finished_for_cluster
            global_percent = 100.0 * global_projected_finished / total_jobs_to_run

            print(
                f"[MONITOR] Cluster {cluster_id}: "
                f"finished {finished_for_cluster}/{num_proc} "
                f"({cluster_percent:.1f}%) | "
                f"idle={counts['idle']} "
                f"running={counts['running']} "
                f"held={counts['held']} "
                f"transferring={counts['transferring']} | "
                f"global projected {global_projected_finished}/{total_jobs_to_run} "
                f"({global_percent:.1f}%)"
            )

            last_printed_finished = finished_for_cluster

        if in_queue == 0:
            break

        if counts["held"] > 0:
            print(
                f"[WARNING] Cluster {cluster_id} has {counts['held']} held jobs. "
                "Check condor_q -hold for details."
            )

        time.sleep(POLL_INTERVAL)

    print(f"[VERIFY] Cluster {cluster_id} left the queue. Verifying outputs...")

    cluster_success = 0
    cluster_failed = 0

    for proc_id, job_key in proc_to_job_key.items():
        ok, missing_or_corrupt = verify_job_outputs(
            job_key,
            global_job_output_map,
        )

        if ok:
            mark_job_completed(job_key, global_job_output_map)
            cluster_success += 1
            global_success_jobs += 1
        else:
            write_failed_job_report(
                cluster_id,
                proc_id,
                job_key,
                missing_or_corrupt,
                global_job_output_map,
            )
            cluster_failed += 1
            global_failed_jobs += 1

    global_finished_jobs += num_proc

    print(f"[CLUSTER SUMMARY] Cluster {cluster_id}")
    print(f"  successful jobs : {cluster_success}")
    print(f"  failed jobs     : {cluster_failed}")

    print(
        f"[GLOBAL STATUS] "
        f"finished={global_finished_jobs}/{total_jobs_to_run}, "
        f"success={global_success_jobs}, "
        f"failed={global_failed_jobs}"
    )

# =========================================================
# Final summary
# =========================================================

print("\n========== FINAL SUMMARY ==========")
print(f"submitted jobs : {global_submitted_jobs}")
print(f"finished jobs  : {global_finished_jobs}")
print(f"successful     : {global_success_jobs}")
print(f"failed         : {global_failed_jobs}")
print("===================================\n")