#!/usr/bin/env python3

import argparse
import csv
import getpass
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml


GROUPS_2024_PLUS = [
    "DiTriBoson",
    "data",
    "DY_amcatnlo",
    "DY_amcatnlo_105_160_VBFFil",
    "DY_minnlo",
    "signals",
    "SingleH",
    "SingleTop",
    "TTX",
    "TT",
    "W",
    "DY_amcatnlo_105_160",
    "DY_amcatnlo_105_160_stitched",
    "other_signals",
    "EWK",
]

GROUPS_2022_2023 = [
    "DiTriBoson",
    "data",
    "EWK",
    "DY_amcatnlo",
    "DY_amcatnlo_105_160",
    "signals",
    "SingleH",
    "SingleTop",
    "TTX",
    "TT",
    "W",
    "other_signals",
]

KNOWN_GROUPS = {
    "data": "data",
    "Data": "data",
    "ditriboson": "DiTriBoson",
    "DiTriBoson": "DiTriBoson",
    "dy_amcatnlo": "DY_amcatnlo",
    "DY_amcatnlo": "DY_amcatnlo",
    "dy_amcatnlo_105_160": "DY_amcatnlo_105_160",
    "DY_amcatnlo_105_160": "DY_amcatnlo_105_160",
    "dy_amcatnlo_105_160_stitched": "DY_amcatnlo_105_160_stitched",
    "DY_amcatnlo_105_160_stitched": "DY_amcatnlo_105_160_stitched",
    "dy_amcatnlo_105_160_VBFFil": "DY_amcatnlo_105_160_VBFFil",
    "DY_amcatnlo_105_160_VBFFil": "DY_amcatnlo_105_160_VBFFil",
    "dy_minnlo": "DY_minnlo",
    "DY_minnlo": "DY_minnlo",
    "ewk": "EWK",
    "EWK": "EWK",
    "signals": "signals",
    "Signals": "signals",
    "singleh": "SingleH",
    "SingleH": "SingleH",
    "singletop": "SingleTop",
    "SingleTop": "SingleTop",
    "ttx": "TTX",
    "TTX": "TTX",
    "TT": "TT",
    "w": "W",
    "W": "W",
    "other_signals": "other_signals",
    "all": "all",
    "All": "all",
}

DEFAULT_INPUT_FOLDER = "/eos/user/a/ayeagle/skim_v2_noUnc"
DEFAULT_RELATIVE_INPUT_PREPATH = "/eos/user/a/ayeagle"


def parse_csv(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def dataset_input_path(input_folder, era, dataset):
    input_folder = Path(input_folder)
    if input_folder.is_absolute():
        return input_folder / era / dataset
    return Path(DEFAULT_RELATIVE_INPUT_PREPATH) / input_folder / era / dataset


def groups_for_era(era):
    if era in ("Run3_2024", "Run3_2025", "Run3_2026"):
        return GROUPS_2024_PLUS
    if era in ("Run3_2022", "Run3_2022EE", "Run3_2023", "Run3_2023BPix"):
        return GROUPS_2022_2023
    raise SystemExit(f"[ERROR] Unknown era '{era}'")


def normalize_groups(groups, era):
    if not groups:
        return groups_for_era(era)

    normalized = []
    for group in groups:
        if group not in KNOWN_GROUPS:
            raise SystemExit(f"[ERROR] Unknown histogram group '{group}'")
        group = KNOWN_GROUPS[group]
        if group == "all":
            return groups_for_era(era)
        normalized.append(group)
    return normalized


def job(dataset, chunk_size, file_suffix="", specific_opts=None):
    return {
        "dataset": dataset,
        "chunk_size": chunk_size,
        "file_suffix": file_suffix,
        "specific_opts": specific_opts or [],
    }


def data_jobs(era):
    datasets_by_era = {
        "Run3_2022": ["Muon_Run2022C", "Muon_Run2022D", "SingleMuon_Run2022C"],
        "Run3_2022EE": ["Muon_Run2022E", "Muon_Run2022F", "Muon_Run2022G"],
        "Run3_2023": [
            "Muon0_Run2023C_v1", "Muon0_Run2023C_v2", "Muon0_Run2023C_v3", "Muon0_Run2023C_v4",
            "Muon1_Run2023C_v1", "Muon1_Run2023C_v2", "Muon1_Run2023C_v3", "Muon1_Run2023C_v4",
        ],
        "Run3_2023BPix": ["Muon0_Run2023D_v1", "Muon0_Run2023D_v2", "Muon1_Run2023D_v1", "Muon1_Run2023D_v2"],
        "Run3_2024": [
            "Muon0_Run2024C", "Muon0_Run2024D", "Muon0_Run2024E", "Muon0_Run2024F",
            "Muon0_Run2024G", "Muon0_Run2024H", "Muon0_Run2024I_v1", "Muon0_Run2024I_v2",
            "Muon1_Run2024C", "Muon1_Run2024D", "Muon1_Run2024E", "Muon1_Run2024F",
            "Muon1_Run2024G", "Muon1_Run2024H", "Muon1_Run2024I_v1", "Muon1_Run2024I_v2",
        ],
        "Run3_2025": [
            "Muon0_Run2025C_v1", "Muon0_Run2025C_v2", "Muon0_Run2025D_v1", "Muon0_Run2025E_v1",
            "Muon0_Run2025F_v1", "Muon0_Run2025F_v2", "Muon0_Run2025G_v1",
            "Muon1_Run2025C_v1", "Muon1_Run2025C_v2", "Muon1_Run2025D_v1", "Muon1_Run2025E_v1",
            "Muon1_Run2025F_v1", "Muon1_Run2025F_v2", "Muon1_Run2025G_v1",
        ],
        "Run3_2026": [],
    }
    datasets = datasets_by_era.get(era, [])
    if not datasets:
        raise SystemExit(f"[ERROR] No data datasets configured for era {era}")
    return [job(dataset, 6) for dataset in datasets]


def dy_amcatnlo_jobs(era):
    if era in ("Run3_2024", "Run3_2025", "Run3_2026"):
        datasets = ["DYto2Mu_M_50_amcatnloFXFX", "DYto2Tau_M_50_amcatnloFXFX", "DYto2E_M_50_amcatnloFXFX"]
    else:
        datasets = ["DYto2L_M_50_amcatnloFXFX"]
    return [job(dataset, 20) for dataset in datasets]


def dy_105_160_jobs(era):
    if era in ("Run3_2024", "Run3_2025", "Run3_2026"):
        datasets = [
            "DYto2Mu_MLL_105to160_amcatnloFXFX",
            "DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF",
            "DYto2Mu_MLL_105to160_amcatnloFXFX_Flashsim",
        ]
    else:
        datasets = ["DYto2Mu_MLL_105to160_amcatnloFXFX"]
    return [job(dataset, 20, "_nonStitched") for dataset in datasets]


def dy_105_160_vbf_filtered_jobs(era):
    if era not in ("Run3_2024", "Run3_2025", "Run3_2026"):
        raise SystemExit("[ERROR] DY_amcatnlo_105_160_VBFFil is only configured for Run3_2024/2025/2026")
    return [job("DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF", 20, "_stitched", ["--additional-cuts", "GenVBFFilter==1"])]


def dy_105_160_stitched_jobs(era):
    if era not in ("Run3_2024", "Run3_2025", "Run3_2026"):
        raise SystemExit("[ERROR] DY_amcatnlo_105_160_stitched is only configured for Run3_2024/2025/2026")
    return [job("DYto2Mu_MLL_105to160_amcatnloFXFX", 20, "_stitched", ["--additional-cuts", "GenVBFFilter==0"])]


def w_jobs(era):
    if era in ("Run3_2024", "Run3_2025", "Run3_2026"):
        datasets = ["WtoMuNu_amcatnloFXFX", "WtoTauNu_amcatnloFXFX"]
    else:
        datasets = ["WtoLNu_0J_amcatnloFXFX", "WtoLNu_1J_amcatnloFXFX", "WtoLNu_2J_amcatnloFXFX", "WtoLNu_amcatnloFXFX"]
    return [job(dataset, 15) for dataset in datasets]


STATIC_GROUPS = {
    "DiTriBoson": (30, [
        "WWW_4F", "WWZ_4F", "WWto2L2Nu_powheg", "WWto4Q_powheg", "WWtoLNu2Q_powheg",
        "WZZ", "WZto2L2Q_powheg", "WZto3LNu_powheg", "WZtoLNu2Q_powheg",
        "ZZZ", "ZZto2L2Nu_powheg", "ZZto2L2Q_powheg", "ZZto2Nu2Q_powheg", "ZZto4L_powheg",
    ]),
    "DY_minnlo": (30, [
        "DYto2Mu_MLL_130to200_powheg_minnlo", "DYto2Mu_MLL_1000to1500_powheg_minnlo",
        "DYto2Mu_MLL_1500to2000_powheg_minnlo", "DYto2Mu_MLL_2000to4000_powheg_minnlo",
        "DYto2Mu_MLL_200to400_powheg_minnlo", "DYto2Mu_MLL_4000to6000_powheg_minnlo",
        "DYto2Mu_MLL_400to600_powheg_minnlo", "DYto2Mu_MLL_50to130_powheg_minnlo",
        "DYto2Mu_MLL_6000to13600_powheg_minnlo", "DYto2Mu_MLL_600to800_powheg_minnlo",
    ]),
    "EWK": (15, ["EWK_2L2J_madgraph_herwig", "EWK_2Mu2J_MLL_105to160_herwig", "EWK_2Mu2J_MLL_105to160_pythia", "EWK_2Mu2J_MLL_105to160_pythia_Flashsim"]),
    "signals": (15, [
        "GluGluHto2Mu", "GluGluHto2Mu_M120", "GluGluHto2Mu_M130", "GluGluHto2Mu_MiNNLO",
        "GluGluHto2Mu_amcatnlo", "GluGluHto2Mu_tuneDown", "GluGluHto2Mu_tuneUp",
        "VBFHto2Mu_M120", "VBFHto2Mu_M125_amcatnlo", "VBFHto2Mu_M125_powheg", "VBFHto2Mu_M130",
        "VBFHto2Mu_m125_Flashsim", "VBFHto2Mu_m125_tuneCP5Down_amcatnlo", "VBFHto2Mu_m125_tuneCP5Up_amcatnlo",
    ]),
    "other_signals": (15, ["TTH_Hto2Mu", "ZH_Hto2Mu", "ggZH_Hto2Mu", "ggZH_Hto2Mu_ZtoAll_M125", "WminusH_Hto2Mu", "WplusH_Hto2Mu"]),
    "SingleH": (15, [
        "GluGluHto2B_M125", "GluGluHto2Tau_UncorrelatedDecay_UnFiltered", "GluGluHto2Wto2L2Nu_M125",
        "VBFHto2B_M125", "VBFHto2Tau_UncorrelatedDecay_UnFiltered", "VBFHto2Wto2L2Nu_M125",
        "ggZH_Hto2B_Zto2L", "ggZH_Hto2B_Zto2Q",
        "ZH_Hto2B_Zto2L", "ZH_Hto2B_Zto2Q",
        "WminusH_Hto2B_WtoLNu", "WminusHto2Tau_UncorrelatedDecay_UnFiltered",
        "WplusH_Hto2B_WtoLNu", "WplusHto2Tau_UncorrelatedDecay_UnFiltered",
    ]),
    "SingleTop": (15, [
        "TWminusto2L2Nu", "TWminusto4Q", "TWminustoLNu2Q", "TbarWplusto2L2Nu", "TbarWplusto4Q", "TbarWplustoLNu2Q",
        "TBbarQto2Q_t_channel_4FS", "TBbarQtoLNu_t_channel_4FS", "TBbartoLplusNuBbar_s_channel_4FS",
        "TbarBQto2Q_t_channel_4FS", "TbarBQtoLNu_t_channel_4FS", "TbarBtoLminusNuB_s_channel_4FS",
    ]),
    "TTX": (10, ["TTHto2B_M125", "TTHtoNon2B_M125", "TTWH", "TTWW", "TTZH_ZHto4B", "TTZ_Zto2Q"]),
    "TT": (10, [ "TTto2L2Nu", "TTto4Q", "TTtoLNu2Q"]),
}


def jobs_for_group(era, group, dataset_name=None, chunk_size=20):
    if dataset_name:
        return [job(dataset_name, chunk_size)]
    if group == "data":
        return data_jobs(era)
    if group == "DY_amcatnlo":
        return dy_amcatnlo_jobs(era)
    if group == "DY_amcatnlo_105_160":
        return dy_105_160_jobs(era)
    if group == "DY_amcatnlo_105_160_stitched":
        return dy_105_160_stitched_jobs(era)
    if group == "DY_amcatnlo_105_160_VBFFil":
        return dy_105_160_vbf_filtered_jobs(era)
    if group == "W":
        return w_jobs(era)
    if group in STATIC_GROUPS:
        chunk_size, datasets = STATIC_GROUPS[group]
        return [job(dataset, chunk_size) for dataset in datasets]
    raise SystemExit(f"[ERROR] Unhandled histogram group '{group}'")


def configured_datasets(analysis_path, era):
    samples_file = analysis_path / "config" / era / "samples.yaml"
    if not samples_file.exists():
        return None
    with samples_file.open() as handle:
        samples = yaml.safe_load(handle) or {}
    return set(samples)


def drop_unconfigured_jobs(selected_jobs, analysis_path, era):
    configured = configured_datasets(analysis_path, era)
    if configured is None:
        return selected_jobs

    kept = []
    for item in selected_jobs:
        if item["dataset"] in configured:
            kept.append(item)
        else:
            print(
                f"[INFO] Skipping {item['dataset']}: "
                f"not present in config/{era}/samples.yaml"
            )
    return kept


def get_active_jobs_count():
    owner = getpass.getuser()
    cmd = [
        "condor_q",
        owner,
        "-constraint",
        "(JobStatus == 1 || JobStatus == 2 || JobStatus == 6)",
        "-af",
        "ClusterId",
        "ProcId",
    ]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return 0
    return sum(1 for line in out.splitlines() if line.strip())


def wait_for_slots(max_parallel_jobs, poll_interval):
    if max_parallel_jobs is None:
        return None

    while True:
        active = get_active_jobs_count()
        available = max_parallel_jobs - active
        if available > 0:
            print(
                f"[QUEUE] Active user Condor jobs={active}; "
                f"available slots={available}/{max_parallel_jobs}."
            )
            return available

        print(
            f"[QUEUE] Waiting: active user Condor jobs={active}, "
            f"max_parallel_jobs={max_parallel_jobs}. "
            f"Waiting {poll_interval}s..."
        )
        time.sleep(poll_interval)


def print_summary(summary_file, monitor_mode, submit_missing):
    if not summary_file.exists() or summary_file.stat().st_size == 0:
        print("[INFO] No monitoring summary produced.")
        return

    with summary_file.open() as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    selected = sum(int(row["selected"]) for row in rows)
    done = sum(int(row["completed_existing"]) for row in rows)
    queued = sum(int(row["queued_existing"]) for row in rows)
    missing = sum(int(row["missing_outputs"]) for row in rows)
    erased = sum(int(row["erased_existing"]) for row in rows)
    submit = sum(int(row["jobs_to_submit"]) for row in rows)

    print("\n============================================================")
    print("[INFO] Histogram campaign monitoring summary")
    print(f"[INFO] Selected datasets : {selected}")
    print(f"[INFO] Completed outputs : {done}")
    print(f"[INFO] Already queued    : {queued}")
    print(f"[INFO] Missing outputs   : {missing}")
    print(f"[INFO] Erased outputs    : {erased}")
    print(f"[INFO] Jobs to submit    : {submit}")
    print()
    print(f"{'ERA':<12} {'GROUP':<34} {'TOTAL':>8} {'DONE':>8} {'QUEUE':>8} {'MISS':>8} {'SUBMIT':>8}")
    print(f"{'-' * 12:<12} {'-' * 34:<34} {'-' * 8:>8} {'-' * 8:>8} {'-' * 8:>8} {'-' * 8:>8} {'-' * 8:>8}")

    output_dirs = []
    for row in rows:
        print(
            f"{row['era']:<12} {row['group']:<34} "
            f"{int(row['selected']):>8} "
            f"{int(row['completed_existing']):>8} "
            f"{int(row['queued_existing']):>8} "
            f"{int(row['missing_outputs']):>8} "
            f"{int(row['jobs_to_submit']):>8}"
        )
        if row["output_dir"] not in output_dirs:
            output_dirs.append(row["output_dir"])

    print()
    for output_dir in output_dirs:
        print(f"[INFO] Output dir checked: {output_dir}")
    if monitor_mode:
        if submit_missing:
            print("[INFO] Submit-missing mode active.")
        else:
            print("[INFO] Monitor mode: no jobs submitted.")
    print("============================================================")


def output_exists(path):
    try:
        return Path(path).stat().st_size > 0
    except OSError:
        return False


def chunk_items(items, chunk_size):
    return [
        items[index:index + chunk_size]
        for index in range(0, len(items), chunk_size)
    ]


def resolve_hist_opts(hist_opts, era):
    return [
        option.replace("{era}", era).replace("{ERA}", era)
        for option in hist_opts
    ]


def extract_requested_variables(hist_opts):
    remaining = []
    variables = []
    index = 0
    while index < len(hist_opts):
        option = hist_opts[index]
        if option != "--variables":
            remaining.append(option)
            index += 1
            continue

        index += 1
        while index < len(hist_opts) and not hist_opts[index].startswith("--"):
            variables.append(hist_opts[index])
            index += 1

    return remaining, list(dict.fromkeys(variables))


def variable_group_name(variable):
    lower = variable.lower()

    if variable.endswith("_NNOutput"):
        return "dnn"
    if lower.startswith(("mu1_", "mu2_")):
        return "muons"
    if "mumu" in lower or lower in {"phi_cs", "costheta_cs", "costheta_phi_cs"}:
        return "dimuon"
    if lower.startswith(("vbfjet1_", "vbfjet2_")):
        return "vbf_jets"
    if variable in {"m_jj", "delta_eta_jj"}:
        return "vbf_dijet"
    if variable in {"m_jj_ls", "delta_eta_jj_ls"}:
        return "selected_dijet"
    if lower.startswith("soft") or lower.startswith("nsoft"):
        return "soft_activity"
    if lower.startswith(
        (
            "leadingjet_",
            "subleadingjet_",
            "thirdjet_",
            "fourthjet_",
            "selectedjets_",
        )
    ) or variable == "N_SelectedJets":
        return "jets"
    if variable in {
        "Zeppenfeld_Var",
        "R_pt",
        "pt_centrality",
        "minDeltaPhi",
        "minDeltaEta",
    }:
        return "vbf_muon"
    return "other"


def group_variables(variables):
    groups = {}
    for variable in dict.fromkeys(variables):
        groups.setdefault(variable_group_name(variable), []).append(variable)
    return groups


def dag_quote(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def write_chunk_dag(
    analysis_path,
    era,
    group_label,
    jobs_to_submit,
    args,
    submit_dir,
    output_dir,
    max_parallel_chunks,
):
    manifests_dir = submit_dir / "manifests"
    options_dir = submit_dir / "options"
    chunk_root = output_dir / ".hist_chunks" / submit_dir.name
    dag_file = submit_dir / "histograms.dag"
    chunk_submit_file = submit_dir / "chunk.sub"
    merge_submit_file = submit_dir / "merge.sub"
    extra_opts_file = options_dir / "extra_opts.txt"

    for directory in (manifests_dir, options_dir, chunk_root):
        directory.mkdir(parents=True, exist_ok=True)

    resolved_hist_opts = resolve_hist_opts(args.hist_opts, era)
    common_hist_opts, requested_variables = extract_requested_variables(
        resolved_hist_opts
    )
    extra_opts_file.write_text(shlex.join(common_hist_opts) + "\n")

    if args.split_variable_groups and not requested_variables:
        main_cfg_file = analysis_path / "config" / era / "maincfg.yaml"
        with main_cfg_file.open() as handle:
            requested_variables = list(
                dict.fromkeys((yaml.safe_load(handle) or {}).get("variables", []))
            )
    if args.split_variable_groups and not requested_variables:
        raise SystemExit(
            f"[ERROR] No variables available for grouped submission in {era}"
        )

    chunk_wrapper = analysis_path / "htcondor" / "run_hist_chunk_condor.sh"
    merge_wrapper = analysis_path / "htcondor" / "run_hist_hadd_condor.sh"
    chunk_submit_file.write_text(
        f"""universe = vanilla
executable = {chunk_wrapper}
arguments = {analysis_path} $(era) $(dataset) $(input_path) $(chunk_manifest) $(chunk_output) $(specific_opts_file) $(extra_opts_file) $(metadata_input_path)

output = $(stdout)
error  = $(stderr)
log    = {submit_dir}/log/chunks.log

request_cpus = {args.chunk_request_cpus}
request_memory = {args.request_memory}
request_disk = {args.request_disk}
+JobFlavour = "{args.job_flavour}"
+Era = "$(era)"
+HistGroup = "{group_label}"
+FinalOutput = "$(final_output)"
batch_name = Hists_$(era)_$(dataset)_$(variable_group)_chunks
getenv = True
queue
"""
    )
    merge_submit_file.write_text(
        f"""universe = vanilla
executable = {merge_wrapper}
arguments = {analysis_path} $(final_output) $(chunk_list)

output = $(stdout)
error  = $(stderr)
log    = {submit_dir}/log/merges.log

request_cpus = 1
request_memory = 2GB
request_disk = {args.request_disk}
+JobFlavour = "{args.job_flavour}"
+Era = "$(era)"
+HistGroup = "{group_label}"
+FinalOutput = "$(final_output)"
batch_name = Hists_$(era)_$(dataset)_hadd
getenv = True
queue
"""
    )

    dag_lines = []
    total_chunk_jobs = 0
    for dataset_index, item in enumerate(jobs_to_submit):
        dataset = item["dataset"]
        suffix = item["file_suffix"]
        metadata_input_path = dataset_input_path(args.input_folder, era, dataset)
        root_input_folder = args.root_input_folder or args.input_folder
        root_input_path = dataset_input_path(root_input_folder, era, dataset)
        root_files = sorted(str(path.resolve()) for path in root_input_path.rglob("*.root"))
        if not root_files:
            print(
                f"[WARNING] No ROOT files found under {root_input_path}. "
                "Scheduling one job to create empty histograms."
            )
            dataset_chunks = [[]]
        else:
            dataset_chunks = chunk_items(root_files, item["chunk_size"])
        dataset_tag = f"d{dataset_index:04d}"
        dataset_chunk_dir = chunk_root / f"{dataset}{suffix}"
        dataset_chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_outputs_file = manifests_dir / f"{dataset_tag}_outputs.txt"
        chunk_outputs = []
        parent_nodes = []
        if args.split_variable_groups:
            variable_groups = group_variables(requested_variables)
        else:
            variable_groups = {"all_variables": []}

        group_opts_files = {}
        for variable_group, variables in variable_groups.items():
            group_opts_file = (
                options_dir / f"{dataset_tag}_{variable_group}_specific_opts.txt"
            )
            group_options = list(item["specific_opts"])
            if variables:
                group_options.extend(["--variables", *variables])
            group_opts_file.write_text(shlex.join(group_options) + "\n")
            group_opts_files[variable_group] = group_opts_file

        for chunk_index, files in enumerate(dataset_chunks):
            manifest_tag = f"{dataset_tag}_c{chunk_index:05d}"
            manifest = manifests_dir / f"{manifest_tag}.txt"
            manifest.write_text("\n".join(files) + "\n")
            for variable_group in variable_groups:
                chunk_tag = (
                    f"{dataset_tag}_c{chunk_index:05d}_{variable_group}"
                )
                chunk_output = (
                    dataset_chunk_dir
                    / f"chunk_{chunk_index:05d}_{variable_group}.root"
                )
                chunk_outputs.append(str(chunk_output))
                node = f"C_{chunk_tag}"
                parent_nodes.append(node)
                total_chunk_jobs += 1

                dag_lines.append(f"JOB {node} {chunk_submit_file}")
                dag_lines.append(
                    f'VARS {node} '
                    f'era="{dag_quote(era)}" '
                    f'dataset="{dag_quote(dataset)}" '
                    f'variable_group="{dag_quote(variable_group)}" '
                    f'input_path="{dag_quote(root_input_path)}" '
                    f'metadata_input_path="{dag_quote(metadata_input_path)}" '
                    f'chunk_manifest="{dag_quote(manifest)}" '
                    f'chunk_output="{dag_quote(chunk_output)}" '
                    f'final_output="{dag_quote(output_dir / f"{dataset}{suffix}.root")}" '
                    f'specific_opts_file="{dag_quote(group_opts_files[variable_group])}" '
                    f'extra_opts_file="{dag_quote(extra_opts_file)}" '
                    f'stdout="{dag_quote(submit_dir / "output" / f"{chunk_tag}.out")}" '
                    f'stderr="{dag_quote(submit_dir / "error" / f"{chunk_tag}.err")}"'
                )
                dag_lines.append(f"RETRY {node} {args.chunk_retries}")
                dag_lines.append(f"CATEGORY {node} CHUNKS")

        chunk_outputs_file.write_text("\n".join(chunk_outputs) + "\n")
        merge_node = f"M_{dataset_tag}"
        final_output = output_dir / f"{dataset}{suffix}.root"
        dag_lines.append(f"JOB {merge_node} {merge_submit_file}")
        dag_lines.append(
            f'VARS {merge_node} '
            f'era="{dag_quote(era)}" '
            f'dataset="{dag_quote(dataset)}" '
            f'final_output="{dag_quote(final_output)}" '
            f'chunk_list="{dag_quote(chunk_outputs_file)}" '
            f'stdout="{dag_quote(submit_dir / "output" / f"{dataset_tag}_merge.out")}" '
            f'stderr="{dag_quote(submit_dir / "error" / f"{dataset_tag}_merge.err")}"'
        )
        dag_lines.append(f"RETRY {merge_node} 1")
        dag_lines.append(f"PARENT {' '.join(parent_nodes)} CHILD {merge_node}")

    if max_parallel_chunks is not None:
        dag_lines.append(f"MAXJOBS CHUNKS {max_parallel_chunks}")

    dag_file.write_text("\n".join(dag_lines) + "\n")
    return dag_file, total_chunk_jobs


def queued_outputs_from_condor():
    owner = getpass.getuser()
    cmd = [
        "condor_q",
        owner,
        "-constraint",
        'regexp("^Hists_", JobBatchName) && (JobStatus == 1 || JobStatus == 2 || JobStatus == 6)',
        "-af",
        "ProcId",
        "Arguments",
    ]
    outputs = set()
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        out = ""

    for line in out.splitlines():
        if not line.strip():
            continue
        try:
            proc_id_str, arguments = line.split(maxsplit=1)
            proc_id = int(proc_id_str)
            parts = shlex.split(arguments)
        except Exception:
            continue
        if len(parts) < 7:
            continue
        jobs_file = Path(parts[1])
        output_dir = parts[5]
        if not jobs_file.exists():
            continue
        try:
            job_line = jobs_file.read_text().splitlines()[proc_id]
            dataset, _chunk, suffix, *_rest = job_line.split("\t")
        except Exception:
            continue
        outputs.add(f"{output_dir}/{dataset}{suffix}.root")

    dag_cmd = [
        "condor_q",
        owner,
        "-constraint",
        "FinalOutput =!= undefined && (JobStatus == 1 || JobStatus == 2 || JobStatus == 6)",
        "-af",
        "FinalOutput",
    ]
    try:
        dag_out = subprocess.check_output(
            dag_cmd,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        dag_out = ""
    outputs.update(line.strip() for line in dag_out.splitlines() if line.strip())
    return outputs


def write_summary_row(summary_file, row):
    header = [
        "era",
        "group",
        "selected",
        "completed_existing",
        "queued_existing",
        "missing_outputs",
        "erased_existing",
        "jobs_to_submit",
        "output_dir",
        "monitoring_file",
        "submit_file",
    ]
    write_header = not summary_file.exists() or summary_file.stat().st_size == 0
    with summary_file.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=header)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def run_group(
    analysis_path,
    era,
    group,
    args,
    summary_file,
    queued_registry,
    remaining_jobs,
    materialize_limit,
):
    group_label = group.replace("/", "_")
    if args.dataset_name and group.startswith("dataset_"):
        selected_jobs = jobs_for_group(era, group, args.dataset_name, args.chunk_size)
    else:
        selected_jobs = jobs_for_group(era, group)
        selected_jobs = drop_unconfigured_jobs(selected_jobs, analysis_path, era)

    if args.output_dir:
        output_dir = Path(
            args.output_dir.format(
                era=era,
                output_suffix=args.output_suffix,
            )
        )
    else:
        output_dir = Path(f"/eos/user/v/vdamante/H_mumu/newHists_{era}{args.output_suffix}")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    submit_dir = analysis_path / "htcondor" / "hists" / f"{era}{args.output_suffix}_{group_label}_{timestamp}"
    stdout_dir = submit_dir / "output"
    stderr_dir = submit_dir / "error"
    log_dir = submit_dir / "log"
    jobs_file = submit_dir / "jobs.tsv"
    extra_opts_file = submit_dir / "extra_opts.txt"
    monitoring_file = submit_dir / "monitoring.txt"
    submit_file = submit_dir / "submit.sub"

    for directory in (stdout_dir, stderr_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)

    queued_outputs = queued_outputs_from_condor() | queued_registry
    completed_existing = 0
    queued_existing = 0
    erased_existing = 0
    missing_outputs = 0
    missing_output_files = []
    jobs_to_submit = []
    hit_max_jobs = False

    with monitoring_file.open("w") as mon:
        for item in selected_jobs:
            output_file = output_dir / f"{item['dataset']}{item['file_suffix']}.root"
            output_file_str = str(output_file)

            if output_exists(output_file):
                if args.erase_existing:
                    mon.write(f"[ERASE] {output_file_str}\n")
                    if not args.no_submit:
                        output_file.unlink(missing_ok=True)
                    erased_existing += 1
                elif not args.force:
                    mon.write(f"[DONE]  {output_file_str}\n")
                    completed_existing += 1
                    continue
            else:
                mon.write(f"[MISS]  {output_file_str}\n")
                missing_outputs += 1
                missing_output_files.append(output_file_str)

            if not args.force and not args.erase_existing and output_file_str in queued_outputs:
                mon.write(f"[QUEUE] {output_file_str}\n")
                queued_existing += 1
                continue

            if remaining_jobs is not None and len(jobs_to_submit) >= remaining_jobs:
                hit_max_jobs = True
                continue

            jobs_to_submit.append(item)

    with jobs_file.open("w") as handle:
        for item in jobs_to_submit:
            handle.write(
                "\t".join(
                    [
                        item["dataset"],
                        str(item["chunk_size"]),
                        item["file_suffix"],
                        shlex.join(item["specific_opts"]),
                    ]
                )
                + "\n"
            )

    extra_opts_file.write_text(
        shlex.join(resolve_hist_opts(args.hist_opts, era)) + "\n"
    )

    write_summary_row(
        summary_file,
        {
            "era": era,
            "group": group_label,
            "selected": len(selected_jobs),
            "completed_existing": completed_existing,
            "queued_existing": queued_existing,
            "missing_outputs": missing_outputs,
            "erased_existing": erased_existing,
            "jobs_to_submit": len(jobs_to_submit),
            "output_dir": str(output_dir),
            "monitoring_file": str(monitoring_file),
            "submit_file": str(submit_file),
        },
    )

    print("\n============================================================")
    print(f"[INFO] Era   : {era}")
    print(f"[INFO] Group : {group_label}")
    if not args.monitor and not args.watch:
        print("[INFO] Backend: direct hist_maker.py Condor submission")
    print("============================================================")

    print("\n========== HISTOGRAM CONDOR MONITORING ==========")
    print(f"era                : {era}")
    print(f"group              : {group_label}")
    print(f"selected datasets  : {len(selected_jobs)}")
    print(f"completed existing : {completed_existing}")
    print(f"already queued     : {queued_existing}")
    print(f"missing outputs    : {missing_outputs}")
    print(f"erased existing    : {erased_existing}")
    print(f"jobs to submit     : {len(jobs_to_submit)}")
    if missing_output_files:
        print("missing files      :")
        for missing_file in missing_output_files:
            print(f"  - {missing_file}")
    if remaining_jobs is not None:
        print(f"max jobs           : {remaining_jobs}")
        print(f"hit max jobs       : {int(hit_max_jobs)}")
    if materialize_limit is not None:
        print(f"max parallel jobs  : {materialize_limit}")
    print(f"output dir         : {output_dir}")
    print("===============================================")

    if len(jobs_to_submit) == 0:
        print("[INFO] All selected histogram outputs are already present or queued. No jobs to submit.")
        print(f"[INFO] Monitoring report: {monitoring_file}")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)

    if args.chunks_as_jobs:
        dag_file, total_chunk_jobs = write_chunk_dag(
            analysis_path=analysis_path,
            era=era,
            group_label=group_label,
            jobs_to_submit=jobs_to_submit,
            args=args,
            submit_dir=submit_dir,
            output_dir=output_dir,
            max_parallel_chunks=materialize_limit,
        )
        print("\n============================================================")
        print("[INFO] Chunk-per-job DAG prepared")
        print(f"[INFO] Era          : {era}")
        print(f"[INFO] Datasets     : {len(jobs_to_submit)}")
        print(f"[INFO] Chunk jobs   : {total_chunk_jobs}")
        print(f"[INFO] Merge jobs   : {len(jobs_to_submit)}")
        print(f"[INFO] DAG file     : {dag_file}")
        print("============================================================")

        if args.no_submit:
            dag_batch_name = f"DAG_Hists_{era}_{group_label}"
            print("[DRY RUN] Not submitting. To submit manually:")
            print(
                f"condor_submit_dag -batch-name "
                f"{shlex.quote(dag_batch_name)} {shlex.quote(str(dag_file))}"
            )
            return len(jobs_to_submit)

        dag_batch_name = f"DAG_Hists_{era}_{group_label}"
        subprocess.run(
            [
                "condor_submit_dag",
                "-batch-name",
                dag_batch_name,
                str(dag_file),
            ],
            check=True,
        )
        for item in jobs_to_submit:
            queued_registry.add(
                str(output_dir / f"{item['dataset']}{item['file_suffix']}.root")
            )
        return len(jobs_to_submit)

    wrapper = analysis_path / "htcondor" / "run_hist_condor.sh"
    submit_contents = f"""universe = vanilla
executable = {wrapper}
arguments = {analysis_path} {jobs_file} $(ProcId) {era} {args.input_folder} {output_dir} {extra_opts_file} {args.root_input_folder or "-"}

output = {stdout_dir}/$(ProcId).out
error  = {stderr_dir}/$(ProcId).err
log    = {log_dir}/condor.log

request_cpus = {args.request_cpus}
request_memory = {args.request_memory}
request_disk = {args.request_disk}
+JobFlavour = "{args.job_flavour}"
+Era = "{era}"
+HistGroup = "{group_label}"
batch_name = Hists_{era}_{group_label}

max_retries = 1
getenv = True
"""
    if materialize_limit is not None:
        submit_contents += f"max_materialize = {materialize_limit}\n\n"
    submit_contents += f"queue {len(jobs_to_submit)}\n"
    submit_file.write_text(submit_contents)

    print("\n============================================================")
    print("[INFO] Condor histogram submission prepared")
    print(f"[INFO] Era        : {era}")
    print(f"[INFO] Jobs       : {len(jobs_to_submit)}")
    print(f"[INFO] Completed  : {completed_existing}")
    print(f"[INFO] Queued     : {queued_existing}")
    print(f"[INFO] Missing    : {missing_outputs}")
    print(f"[INFO] Output dir : {output_dir}")
    print(f"[INFO] Submit file: {submit_file}")
    print(f"[INFO] Jobs table : {jobs_file}")
    print(f"[INFO] Monitoring : {monitoring_file}")
    print(f"[INFO] Stdout     : {stdout_dir}")
    print(f"[INFO] Stderr     : {stderr_dir}")
    print(f"[INFO] Event log  : {log_dir}")
    print("============================================================")

    if args.no_submit:
        print("[DRY RUN] Not submitting. To submit manually:")
        print(f"condor_submit {submit_file}")
        return len(jobs_to_submit)

    subprocess.run(["condor_submit", str(submit_file)], check=True)
    for item in jobs_to_submit:
        queued_registry.add(str(output_dir / f"{item['dataset']}{item['file_suffix']}.root"))
    return len(jobs_to_submit)


def main():
    parser = argparse.ArgumentParser(
        description="Submit histogram jobs to HTCondor with monitoring/refill logic."
    )
    parser.add_argument("-e", "--era", dest="eras", action="append", help="Era to process. Can be repeated.")
    parser.add_argument("--eras", dest="eras_csv", help="Comma-separated eras, or all.")
    parser.add_argument("--datasets", "--groups", dest="groups_csv", help="Comma-separated histogram groups.")
    parser.add_argument("--dataset-name", "--dataset", help="One explicit dataset to run.")
    parser.add_argument("--chunk-size", type=int, default=20, help="Chunk size for --dataset-name.")
    parser.add_argument(
        "--input-folder",
        default=DEFAULT_INPUT_FOLDER,
        help=(
            "Input skim folder or absolute prepath used for metadata/JSONs. Default: "
            f"{DEFAULT_INPUT_FOLDER}"
        ),
    )
    parser.add_argument(
        "--root-input-folder",
        help=(
            "Optional skim folder or absolute prepath used for ROOT files. "
            "Defaults to --input-folder."
        ),
    )
    parser.add_argument("--output-suffix", default="")
    parser.add_argument(
        "--output-dir",
        help=(
            "Complete histogram output directory. The placeholders {era} and "
            "{output_suffix} are supported."
        ),
    )
    parser.add_argument("--condor", action="store_true", help="Submit Condor jobs.")
    parser.add_argument(
        "--chunks-as-jobs",
        action="store_true",
        help="Submit one Condor DAG node per input-file chunk, followed by one hadd node per dataset.",
    )
    parser.add_argument(
        "--split-variable-groups",
        action="store_true",
        help=(
            "In --chunks-as-jobs mode, submit one node per chunk and logical "
            "variable group (muons, dimuon, jets, dijets, DNN, etc.)."
        ),
    )
    parser.add_argument(
        "--chunk-request-cpus",
        type=int,
        default=1,
        help="CPUs requested by each chunk node in --chunks-as-jobs mode.",
    )
    parser.add_argument(
        "--chunk-retries",
        type=int,
        default=10,
        help=(
            "Number of automatic DAGMan retries for a failed chunk node "
            "(default: 10). The dataset hadd remains blocked until every "
            "chunk succeeds."
        ),
    )
    parser.add_argument("--job-flavour", default="workday", help="HTCondor JobFlavour.")
    parser.add_argument("--request-cpus", type=int, default=4, help="HTCondor request_cpus.")
    parser.add_argument("--request-memory", default="8GB", help="HTCondor request_memory.")
    parser.add_argument("--request-disk", default="4GB", help="HTCondor request_disk.")
    parser.add_argument("--monitor", "--no-submit", dest="monitor", action="store_true", help="Monitor only; do not submit.")
    parser.add_argument("--watch", action="store_true", help="Repeat monitoring every --poll-interval seconds.")
    parser.add_argument(
        "--submit-missing",
        "--missing-only",
        "--refill",
        action="store_true",
        help="Submit missing outputs not already queued.",
    )
    parser.add_argument("--max-parallel-jobs", type=int, default=None)
    parser.add_argument("--poll-interval", type=int, default=120)
    parser.add_argument("--max-submit-jobs", "--max-jobs", type=int, default=None)
    parser.add_argument("--erase-existing", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare submission files without submitting them.",
    )
    parser.add_argument("hist_opts", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.hist_opts and args.hist_opts[0] == "--":
        args.hist_opts = args.hist_opts[1:]
    if args.chunk_retries < 0:
        raise SystemExit("[ERROR] --chunk-retries must be >= 0")
    if args.split_variable_groups and not args.chunks_as_jobs:
        raise SystemExit(
            "[ERROR] --split-variable-groups requires --chunks-as-jobs"
        )

    eras = []
    if args.eras:
        eras.extend(args.eras)
    if args.eras_csv:
        eras.extend(parse_csv(args.eras_csv))
    if not eras:
        raise SystemExit("[ERROR] Missing --era/--eras")
    if eras == ["all"]:
        eras = [
            "Run3_2022",
            "Run3_2022EE",
            "Run3_2023",
            "Run3_2023BPix",
            "Run3_2024",
            "Run3_2025",
            "Run3_2026",
        ]

    if args.dataset_name and args.groups_csv:
        raise SystemExit("[ERROR] Use either --dataset-name or --datasets, not both")

    groups_requested = parse_csv(args.groups_csv) if args.groups_csv else []
    if args.dataset_name and args.dataset_name in KNOWN_GROUPS:
        groups_requested = [args.dataset_name]
        args.dataset_name = None

    analysis_path = Path(os.environ.get("ANALYSIS_PATH", Path(__file__).resolve().parents[1]))

    submit_mode = args.condor or args.submit_missing
    monitor_mode = args.monitor or args.watch

    if args.dry_run:
        args.no_submit = True
    elif args.submit_missing:
        args.no_submit = False
    elif monitor_mode:
        args.no_submit = True
    else:
        args.no_submit = False

    with tempfile.TemporaryDirectory(prefix="hist_submit_") as tmpdir:
        tmpdir = Path(tmpdir)
        summary_file = tmpdir / "campaign_monitoring.tsv"
        queued_registry = set()

        while True:
            if summary_file.exists():
                summary_file.unlink()

            submitted_total = 0
            stop = False

            for era in eras:
                if args.dataset_name:
                    groups = [f"dataset_{args.dataset_name}"]
                else:
                    groups = normalize_groups(groups_requested, era)

                for group in groups:
                    if stop:
                        break

                    remaining_jobs = None
                    if args.max_submit_jobs is not None:
                        remaining_jobs = args.max_submit_jobs - submitted_total
                        if remaining_jobs <= 0:
                            stop = True
                            break

                    materialize_limit = None
                    if submit_mode and args.max_parallel_jobs is not None and not args.no_submit:
                        materialize_limit = wait_for_slots(args.max_parallel_jobs, args.poll_interval)

                    run_group(
                        analysis_path,
                        era,
                        group,
                        args,
                        summary_file,
                        queued_registry,
                        remaining_jobs,
                        materialize_limit,
                    )

                    if summary_file.exists():
                        with summary_file.open() as handle:
                            rows = list(csv.DictReader(handle, delimiter="\t"))
                        if rows:
                            submitted_total = sum(int(row["jobs_to_submit"]) for row in rows)

            print_summary(summary_file, monitor_mode, args.submit_missing)

            if not args.watch:
                break
            print(f"[WATCH] Sleeping {args.poll_interval}s before refreshing...")
            time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()
