#!/usr/bin/env bash
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYSIS_PATH="${ANALYSIS_PATH:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
export ANALYSIS_PATH
cd "${ANALYSIS_PATH}"

usage() {
  cat <<'EOF'
Usage:
  histograms/scripts/hists.sh --datasets GROUP[,GROUP...] --era ERA [options] [-- HIST_MAKER_OPTS...]

Dataset groups:
  data
  DiTriBoson
  DY_amcatnlo
  DY_amcatnlo_105_160
  DY_amcatnlo_105_160_stitched
  DY_amcatnlo_105_160_VBFFil
  DY_minnlo
  EWK
  signals
  SingleH
  SingleTop
  TTX
  TT
  W
  other_signals

Options:
  --datasets GROUPS       Comma-separated list of groups, or "all".
  --dataset-name NAME     Run one explicit dataset instead of a group.
  --chunk-size N          Override chunk size for selected jobs. Default: group-specific;
                          for --dataset-name default is 20.
  --era ERA              Era to run, e.g. Run3_2022.
  --input-folder NAME    Input skim folder. Default: skim_v2_noUnc.
  --output-suffix TEXT   Suffix appended to newHists_${era}.
  --output-dir DIR       Override the complete output directory.
  --extra-opts TEXT      Extra hist_maker.py options as a quoted string.
  --condor               Submit one HTCondor job per selected dataset.
  --condor-dir DIR       Directory for Condor submit/log files. Default: htcondor/hists.
  --job-flavour TEXT     HTCondor JobFlavour. Default: workday.
  --request-cpus N       HTCondor request_cpus. Default: 4.
  --request-memory TEXT  HTCondor request_memory. Default: 8GB.
  --request-disk TEXT    HTCondor request_disk. Default: 4GB.
  --max-jobs N           Submit at most N missing histogram jobs.
  --max-parallel-jobs N  Materialize at most N jobs at a time in this submission.
  --summary-file FILE    Append one TSV monitoring summary line to FILE.
  --queued-registry-file FILE
                          Treat outputs listed in FILE as already submitted.
  --missing-only         In local mode, run only outputs that are missing.
  --erase-existing       Remove already produced histogram files before submitting.
  --force                Submit selected jobs even if output files already exist.
  --dry-run              Print commands without running them.
  -h, --help             Show this help.

Examples:
  histograms/scripts/hists.sh --datasets DiTriBoson,data --era Run3_2022
  histograms/scripts/hists.sh --datasets DY_amcatnlo --era Run3_2024 --output-suffix _DNN -- --variables DNN_NNOutput --skip-file-validation
  histograms/scripts/hists.sh --datasets all --era Run3_2025 --extra-opts "--n-cores 8"
  histograms/scripts/hists.sh --datasets signals,EWK --era Run3_2024 --condor -- --variables m_mumu --skip-file-validation
EOF
}

die() {
  echo "[ERROR] $*" >&2
  exit 1
}

append_words() {
  local target_name="$1"
  shift
  local -n target_ref="${target_name}"
  local word
  for word in "$@"; do
    target_ref+=("${word}")
  done
}

append_extra_opts_string() {
  local opts_string="$1"
  [[ -z "${opts_string}" ]] && return
  # shellcheck disable=SC2206
  local opts_array=(${opts_string})
  append_words extra_opts "${opts_array[@]}"
}

split_csv() {
  local csv="$1"
  local -n out_ref="$2"
  local item
  IFS=',' read -r -a out_ref <<< "${csv}"
  for item in "${out_ref[@]}"; do
    [[ -n "${item}" ]] || die "Empty dataset group in --datasets '${csv}'"
  done
}

strip_condor_arg_quotes() {
  local value="$1"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "${value}"
}

hist_output_exists() {
  local output_file="$1"
  [[ -s "${output_file}" ]] && return 0

  local size
  size="$(stat -c '%s' "${output_file}" 2>/dev/null || true)"
  [[ "${size}" =~ ^[0-9]+$ && "${size}" -gt 0 ]]
}

is_output_already_queued() {
  local wanted_output="$1"
  command -v condor_q >/dev/null 2>&1 || return 1

  local owner
  owner="$(id -un)"

  local line ad_proc analysis_arg jobs_file_arg queued_proc_id queued_era queued_input queued_output_dir rest
  local job_line queued_dataset queued_chunk queued_suffix queued_opts queued_output

  while IFS= read -r line; do
    [[ -n "${line}" ]] || continue
    read -r ad_proc analysis_arg jobs_file_arg queued_proc_id queued_era queued_input queued_output_dir rest <<< "${line}"
    jobs_file_arg="$(strip_condor_arg_quotes "${jobs_file_arg:-}")"
    queued_proc_id="$(strip_condor_arg_quotes "${queued_proc_id:-}")"
    queued_output_dir="$(strip_condor_arg_quotes "${queued_output_dir:-}")"
    [[ -n "${jobs_file_arg:-}" && -n "${queued_proc_id:-}" && -n "${queued_output_dir:-}" ]] || continue
    [[ -r "${jobs_file_arg}" ]] || continue
    [[ "${queued_proc_id}" =~ ^[0-9]+$ ]] || continue

    job_line="$(sed -n "$((queued_proc_id + 1))p" "${jobs_file_arg}" 2>/dev/null || true)"
    [[ -n "${job_line}" ]] || continue

    IFS=$'\t' read -r queued_dataset queued_chunk queued_suffix queued_opts <<< "${job_line}"
    queued_output="${queued_output_dir}/${queued_dataset}${queued_suffix}.root"

    if [[ "${queued_output}" == "${wanted_output}" ]]; then
      return 0
    fi
  done < <(
    condor_q "${owner}" \
      -constraint 'regexp("^Hists_", JobBatchName) && (JobStatus == 1 || JobStatus == 2 || JobStatus == 6)' \
      -af ProcId Arguments 2>/dev/null || true
  )

  return 1
}

is_output_in_registry() {
  local output_file="$1"
  [[ -n "${queued_registry_file}" && -s "${queued_registry_file}" ]] || return 1
  grep -Fxq "${output_file}" "${queued_registry_file}"
}

require_known_era() {
  local era="$1"
  case "${era}" in
    Run3_2022|Run3_2022EE|Run3_2023|Run3_2023BPix|Run3_2024|Run3_2025|Run3_2026) ;;
    *) die "Unknown era '${era}'" ;;
  esac
}

dataset_is_configured() {
  local era="$1"
  local dataset_name="$2"
  local samples_file="config/${era}/samples.yaml"

  [[ -r "${samples_file}" ]] || return 0
  awk -v dataset="${dataset_name}" '
    $0 ~ "^[A-Za-z0-9_]+:" {
      key = $1
      sub(/:$/, "", key)
      if (key == dataset) {
        found = 1
        exit
      }
    }
    END { exit(found ? 0 : 1) }
  ' "${samples_file}"
}

add_job() {
  local dataset_name="$1"
  local chunk_size="$2"
  local file_suffix="${3:-}"
  local specific_opts=()

  if [[ $# -ge 3 ]]; then
    shift 3
    specific_opts=("$@")
  fi

  job_datasets+=("${dataset_name}")
  job_chunk_sizes+=("${chunk_size}")
  job_file_suffixes+=("${file_suffix}")
  job_specific_opts+=("${specific_opts[*]}")
}

drop_unconfigured_jobs() {
  local era="$1"
  local filtered_datasets=()
  local filtered_chunk_sizes=()
  local filtered_file_suffixes=()
  local filtered_specific_opts=()
  local dataset_name
  local skipped=0

  for i in "${!job_datasets[@]}"; do
    dataset_name="${job_datasets[$i]}"
    if dataset_is_configured "${era}" "${dataset_name}"; then
      filtered_datasets+=("${job_datasets[$i]}")
      filtered_chunk_sizes+=("${job_chunk_sizes[$i]}")
      filtered_file_suffixes+=("${job_file_suffixes[$i]}")
      filtered_specific_opts+=("${job_specific_opts[$i]}")
    else
      echo "[INFO] Skipping ${dataset_name}: not present in config/${era}/samples.yaml"
      skipped=$((skipped + 1))
    fi
  done

  if [[ ${skipped} -gt 0 ]]; then
    job_datasets=("${filtered_datasets[@]}")
    job_chunk_sizes=("${filtered_chunk_sizes[@]}")
    job_file_suffixes=("${filtered_file_suffixes[@]}")
    job_specific_opts=("${filtered_specific_opts[@]}")
  fi
}

add_data_jobs() {
  local era="$1"
  local datasets=()

  case "${era}" in
    Run3_2022)
      datasets=(Muon_Run2022C Muon_Run2022D SingleMuon_Run2022C)
      ;;
    Run3_2022EE)
      # datasets=(Muon_Run2022G)
      datasets=(Muon_Run2022E Muon_Run2022F Muon_Run2022G)
      ;;
    Run3_2023)
      datasets=(
        Muon0_Run2023C_v1 Muon0_Run2023C_v2 Muon0_Run2023C_v3 Muon0_Run2023C_v4
        Muon1_Run2023C_v1 Muon1_Run2023C_v2 Muon1_Run2023C_v3 Muon1_Run2023C_v4
      )
      ;;
    Run3_2023BPix)
      datasets=(Muon0_Run2023D_v1 Muon0_Run2023D_v2 Muon1_Run2023D_v1 Muon1_Run2023D_v2)
      ;;
    Run3_2024)
      datasets=(
        Muon0_Run2024C Muon0_Run2024D Muon0_Run2024E Muon0_Run2024F
        Muon0_Run2024G Muon0_Run2024H Muon0_Run2024I_v1 Muon0_Run2024I_v2
        Muon1_Run2024C Muon1_Run2024D Muon1_Run2024E Muon1_Run2024F
        Muon1_Run2024G Muon1_Run2024H Muon1_Run2024I_v1 Muon1_Run2024I_v2
      )
      ;;
    Run3_2025)
      datasets=(
        Muon0_Run2025C_v1 Muon0_Run2025C_v2 Muon0_Run2025D_v1 Muon0_Run2025E_v1
        Muon0_Run2025F_v1 Muon0_Run2025F_v2 Muon0_Run2025G_v1
        Muon1_Run2025C_v1 Muon1_Run2025C_v2 Muon1_Run2025D_v1 Muon1_Run2025E_v1
        Muon1_Run2025F_v1 Muon1_Run2025F_v2 Muon1_Run2025G_v1
      )
      ;;
    Run3_2026)
      datasets=()
      ;;
  esac

  [[ ${#datasets[@]} -gt 0 ]] || die "No data datasets configured for era ${era}"

  local dataset_name
  for dataset_name in "${datasets[@]}"; do
    add_job "${dataset_name}" 6 ""
  done
}

add_dy_amcatnlo_jobs() {
  local era="$1"
  local datasets=()

  case "${era}" in
    Run3_2024|Run3_2025|Run3_2026)
      datasets=(DYto2Mu_M_50_amcatnloFXFX DYto2Tau_M_50_amcatnloFXFX DYto2E_M_50_amcatnloFXFX)
      ;;
    Run3_2022|Run3_2022EE|Run3_2023|Run3_2023BPix)
      datasets=(DYto2L_M_50_amcatnloFXFX)
      ;;
  esac

  local dataset_name
  for dataset_name in "${datasets[@]}"; do
    add_job "${dataset_name}" 20
  done
}

add_dy_105_160_jobs() {
  local era="$1"
  local datasets=()

  case "${era}" in
    Run3_2024|Run3_2025|Run3_2026)
      datasets=(
        DYto2Mu_MLL_105to160_amcatnloFXFX
        DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF
        DYto2Mu_MLL_105to160_amcatnloFXFX_Flashsim
      )
      ;;
    Run3_2022|Run3_2022EE|Run3_2023|Run3_2023BPix)
      datasets=(DYto2Mu_MLL_105to160_amcatnloFXFX)
      ;;
  esac

  local dataset_name
  for dataset_name in "${datasets[@]}"; do
    add_job "${dataset_name}" 20 "_nonStitched"
  done
}
add_dy_105_160_VBFFil_stitched_jobs() {
  local era="$1"

  case "${era}" in
    Run3_2024|Run3_2025|Run3_2026) ;;
    *) die "DY_amcatnlo_105_160_VBF_FIl_stitched is only configured for Run3_2024, Run3_2025, Run3_2026" ;;
  esac

  add_job DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF 20 "_stitched" --additional-cuts "GenVBFFilter==1"
}


add_dy_105_160_stitched_jobs() {
  local era="$1"

  case "${era}" in
    Run3_2024|Run3_2025|Run3_2026) ;;
    *) die "DY_amcatnlo_105_160_stitched is only configured for Run3_2024, Run3_2025, Run3_2026" ;;
  esac

  add_job DYto2Mu_MLL_105to160_amcatnloFXFX 20 "_stitched" --additional-cuts "GenVBFFilter==0"
}

add_static_group_jobs() {
  local group="$1"
  local datasets=()
  local chunk_size=15

  case "${group}" in
    DiTriBoson)
      chunk_size=30
      datasets=(
        WWW_4F WWZ_4F WWto2L2Nu_powheg WWto4Q_powheg WWtoLNu2Q_powheg
        WZZ WZto2L2Q_powheg WZto3LNu_powheg WZtoLNu2Q_powheg
        ZZZ ZZto2L2Nu_powheg ZZto2L2Q_powheg ZZto2Nu2Q_powheg ZZto4L_powheg
      )
      ;;
    DY_minnlo)
      chunk_size=30
      datasets=(  DYto2Mu_MLL_130to200_powheg_minnlo DYto2Mu_MLL_1000to1500_powheg_minnlo  DYto2Mu_MLL_1500to2000_powheg_minnlo DYto2Mu_MLL_2000to4000_powheg_minnlo DYto2Mu_MLL_200to400_powheg_minnlo DYto2Mu_MLL_4000to6000_powheg_minnlo DYto2Mu_MLL_400to600_powheg_minnlo DYto2Mu_MLL_50to130_powheg_minnlo DYto2Mu_MLL_6000to13600_powheg_minnlo DYto2Mu_MLL_600to800_powheg_minnlo )
      ;;
    EWK)
      datasets=(EWK_2L2J_madgraph_herwig EWK_2Mu2J_MLL_105to160_herwig EWK_2Mu2J_MLL_105to160_pythia EWK_2Mu2J_MLL_105to160_pythia_Flashsim)
      ;;
    signals)
      datasets=(
        GluGluHto2Mu GluGluHto2Mu_M120 GluGluHto2Mu_M130 GluGluHto2Mu_MiNNLO
        GluGluHto2Mu_amcatnlo GluGluHto2Mu_tuneDown GluGluHto2Mu_tuneUp
        VBFHto2Mu_M120 VBFHto2Mu_M125_amcatnlo VBFHto2Mu_M125_powheg VBFHto2Mu_M130
        VBFHto2Mu_m125_Flashsim VBFHto2Mu_m125_tuneCP5Down_amcatnlo VBFHto2Mu_m125_tuneCP5Up_amcatnlo
      )
      ;;
    other_signals)
      datasets=(
      TTH_Hto2Mu ZH_Hto2Mu ggZH_Hto2Mu ggZH_Hto2Mu_ZtoAll_M125 WminusH_Hto2Mu WplusH_Hto2Mu
      )
      ;;
    SingleH)
      datasets=(
        GluGluHto2B_M125 GluGluHto2Tau_UncorrelatedDecay_UnFiltered GluGluHto2Wto2L2Nu_M125
        VBFHto2B_M125 VBFHto2Tau_UncorrelatedDecay_UnFiltered VBFHto2Wto2L2Nu_M125
        ggZH_Hto2B_Zto2L ggZH_Hto2B_Zto2Q
        ZH_Hto2B_Zto2L ZH_Hto2B_Zto2Q
        WminusH_Hto2B_WtoLNu WminusHto2Tau_UncorrelatedDecay_UnFiltered
        WplusH_Hto2B_WtoLNu WplusHto2Tau_UncorrelatedDecay_UnFiltered
      )
      ;;
    SingleTop)
      datasets=(
        TWminusto2L2Nu TWminusto4Q TWminustoLNu2Q TbarWplusto2L2Nu TbarWplusto4Q TbarWplustoLNu2Q
        TBbarQto2Q_t_channel_4FS TBbarQtoLNu_t_channel_4FS TBbartoLplusNuBbar_s_channel_4FS
        TbarBQto2Q_t_channel_4FS TbarBQtoLNu_t_channel_4FS TbarBtoLminusNuB_s_channel_4FS
      )
      ;;
    TT)
      chunk_size=10
      datasets=(TTto2L2Nu TTto4Q TTtoLNu2Q)
      ;;
    TTX)
      chunk_size=10
      datasets=(TTHto2B_M125 TTHtoNon2B_M125 TTWH TTWW TTZH_ZHto4B TTZ_Zto2Q)
      ;;
    *)
      die "Internal error: unknown static group '${group}'"
      ;;
  esac

  local dataset_name
  for dataset_name in "${datasets[@]}"; do
    add_job "${dataset_name}" "${chunk_size}"
  done
}

add_w_jobs() {
  local era="$1"
  local datasets=()

  case "${era}" in
    Run3_2024|Run3_2025|Run3_2026)
      datasets=(WtoMuNu_amcatnloFXFX WtoTauNu_amcatnloFXFX) # WtoENu_amcatnloFXFX WtoLNu_1J_madgraphMLM WtoLNu_2J_madgraphMLM WtoLNu_3J_madgraphMLM WtoLNu_4J_madgraphMLM
      ;;
    Run3_2022|Run3_2022EE|Run3_2023|Run3_2023BPix)
      datasets=(WtoLNu_0J_amcatnloFXFX WtoLNu_1J_amcatnloFXFX WtoLNu_2J_amcatnloFXFX WtoLNu_amcatnloFXFX)
      ;;
  esac

  local dataset_name
  for dataset_name in "${datasets[@]}"; do
    add_job "${dataset_name}" 15
  done
}

normalize_group() {
  case "$1" in
    data|Data) echo "data" ;;
    ditriboson|DiTriBoson) echo "DiTriBoson" ;;
    dy_amcatnlo|DY_amcatnlo) echo "DY_amcatnlo" ;;
    dy_amcatnlo_105_160|DY_amcatnlo_105_160) echo "DY_amcatnlo_105_160" ;;
    dy_amcatnlo_105_160_stitched|DY_amcatnlo_105_160_stitched) echo "DY_amcatnlo_105_160_stitched" ;;
    DY_amcatnlo_105_160_VBFFil|dy_amcatnlo_105_160_VBFFil) echo "DY_amcatnlo_105_160_VBFFil";;
    dy_minnlo|DY_minnlo) echo "DY_minnlo" ;;
    ewk|EWK) echo "EWK" ;;
    signals|Signals) echo "signals" ;;
    other_signals) echo "other_signals" ;;
    singleh|SingleH) echo "SingleH" ;;
    singletop|SingleTop) echo "SingleTop" ;;
    ttx|TTX) echo "TTX" ;;
    tt|TT) echo "TT" ;;
    w|W) echo "W" ;;
    all|All) echo "all" ;;
    *) die "Unknown dataset group '$1'. Run with --help for the list." ;;
  esac
}

groups_for_era() {
  local era="$1"

  case "${era}" in
    Run3_2024|Run3_2025|Run3_2026)
      echo "data DiTriBoson DY_amcatnlo DY_amcatnlo_105_160 DY_amcatnlo_105_160_stitched DY_amcatnlo_105_160_VBFFil DY_minnlo EWK signals other_signals SingleH SingleTop TTX TT W"
      ;;
    Run3_2022|Run3_2022EE|Run3_2023|Run3_2023BPix)
      echo "data DiTriBoson DY_amcatnlo DY_amcatnlo_105_160 EWK signals other_signals SingleH SingleTop TTX TT W"
      ;;
    *)
      die "Unknown era '${era}'"
      ;;
  esac
}

dataset_groups=()
single_dataset_name=""
single_dataset_chunk_size=20
chunk_size_override=""
era=""
input_folder="skim_v2_noUnc"
output_suffix=""
output_dir_override=""
extra_opts=()
dry_run=0
condor=0
condor_dir="htcondor/hists"
job_flavour="workday"
request_cpus=4
request_memory="8GB"
request_disk="4GB"
max_jobs=""
max_parallel_jobs=""
summary_file=""
queued_registry_file=""
job_count_file=""
erase_existing=0
force_submit=0
missing_only=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --datasets|--dataset-groups|--groups)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      split_csv "$2" dataset_groups
      shift 2
      ;;
    --dataset-name|--dataset)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      single_dataset_name="$2"
      shift 2
      ;;
    --chunk-size)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      single_dataset_chunk_size="$2"
      [[ "${single_dataset_chunk_size}" =~ ^[0-9]+$ ]] || die "$1 must be a positive integer"
      [[ "${single_dataset_chunk_size}" -ge 1 ]] || die "$1 must be >= 1"
      chunk_size_override="${single_dataset_chunk_size}"
      shift 2
      ;;
    --era)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      era="$2"
      shift 2
      ;;
    --input-folder)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      input_folder="$2"
      shift 2
      ;;
    --output-suffix)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      output_suffix="$2"
      shift 2
      ;;
    --output-dir)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      [[ -n "$2" ]] || die "$1 requires a non-empty value"
      output_dir_override="$2"
      shift 2
      ;;
    --extra-opts|--extra-options)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      append_extra_opts_string "$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --condor)
      condor=1
      shift
      ;;
    --condor-dir)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      condor_dir="$2"
      shift 2
      ;;
    --job-flavour)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      job_flavour="$2"
      shift 2
      ;;
    --request-cpus)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      request_cpus="$2"
      shift 2
      ;;
    --request-memory)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      request_memory="$2"
      shift 2
      ;;
    --request-disk)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      request_disk="$2"
      shift 2
      ;;
    --max-jobs|--max-submit-jobs)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      max_jobs="$2"
      [[ "${max_jobs}" =~ ^[0-9]+$ ]] || die "$1 must be a non-negative integer"
      shift 2
      ;;
    --max-parallel-jobs)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      max_parallel_jobs="$2"
      [[ "${max_parallel_jobs}" =~ ^[0-9]+$ ]] || die "$1 must be a non-negative integer"
      [[ "${max_parallel_jobs}" -ge 1 ]] || die "$1 must be >= 1"
      shift 2
      ;;
    --summary-file)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      summary_file="$2"
      shift 2
      ;;
    --queued-registry-file)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      queued_registry_file="$2"
      shift 2
      ;;
    --missing-only|--run-missing-only)
      missing_only=1
      shift
      ;;
    --job-count-file)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      job_count_file="$2"
      shift 2
      ;;
    --erase-existing|--erase-already-present|--overwrite)
      erase_existing=1
      shift
      ;;
    --force|--submit-existing)
      force_submit=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      append_words extra_opts "$@"
      break
      ;;
    *)
      die "Unknown option '$1'. Run with --help for usage."
      ;;
  esac
done

[[ ${#dataset_groups[@]} -gt 0 || -n "${single_dataset_name}" ]] || die "Missing --datasets or --dataset-name"
[[ -n "${era}" ]] || die "Missing --era"
require_known_era "${era}"

normalized_groups=()
if [[ -n "${single_dataset_name}" ]]; then
  normalized_groups=("dataset_${single_dataset_name}")
else
  for group in "${dataset_groups[@]}"; do
    group="$(normalize_group "${group}")"
    if [[ "${group}" == "all" ]]; then
      read -r -a normalized_groups <<< "$(groups_for_era "${era}")"
      break
    fi
    normalized_groups+=("${group}")
  done
fi

job_datasets=()
job_chunk_sizes=()
job_file_suffixes=()
job_specific_opts=()

if [[ -n "${single_dataset_name}" ]]; then
  add_job "${single_dataset_name}" "${single_dataset_chunk_size}"
else
  for group in "${normalized_groups[@]}"; do
    case "${group}" in
      data) add_data_jobs "${era}" ;;
      DY_amcatnlo) add_dy_amcatnlo_jobs "${era}" ;;
      DY_amcatnlo_105_160) add_dy_105_160_jobs "${era}" ;;
      DY_amcatnlo_105_160_stitched) add_dy_105_160_stitched_jobs "${era}" ;;
      DY_amcatnlo_105_160_VBFFil) add_dy_105_160_VBFFil_stitched_jobs "${era}" ;;
      W) add_w_jobs "${era}" ;;
      DiTriBoson|DY_minnlo|EWK|signals|SingleH|SingleTop|TTX|other_signals|TT) add_static_group_jobs "${group}" ;;
      *) die "Internal error: unhandled group '${group}'" ;;
    esac
  done
fi

if [[ -z "${single_dataset_name}" ]]; then
  drop_unconfigured_jobs "${era}"
fi

[[ ${#job_datasets[@]} -gt 0 ]] || die "No jobs selected"

if [[ -n "${chunk_size_override}" ]]; then
  for i in "${!job_chunk_sizes[@]}"; do
    job_chunk_sizes[$i]="${chunk_size_override}"
  done
fi

output_dir="${output_dir_override:-/eos/user/v/vdamante/H_mumu/newHists_${era}${output_suffix}}"
if [[ ${dry_run} -eq 0 ]]; then
  mkdir -p "${output_dir}"
fi

if [[ ${condor} -eq 1 ]]; then
  analysis_path="${ANALYSIS_PATH:-$(pwd)}"
  timestamp="$(date +%Y%m%d_%H%M%S)"
  group_label="$(IFS=_; echo "${normalized_groups[*]}")"
  group_label="${group_label//[^A-Za-z0-9_.-]/_}"
  submit_dir="${condor_dir}/${era}${output_suffix}_${group_label}_${timestamp}"
  condor_output_dir="${submit_dir}/output"
  condor_error_dir="${submit_dir}/error"
  condor_log_dir="${submit_dir}/log"
  jobs_file="${submit_dir}/jobs.tsv"
  extra_opts_file="${submit_dir}/extra_opts.txt"
  monitoring_file="${submit_dir}/monitoring.txt"
  submit_file="${submit_dir}/submit.sub"
  wrapper="${analysis_path}/htcondor/run_hist_condor.sh"

  mkdir -p "${condor_output_dir}" "${condor_error_dir}" "${condor_log_dir}"

  : > "${jobs_file}"
  : > "${monitoring_file}"

  total_selected=0
  completed_existing=0
  queued_existing=0
  erased_existing=0
  missing_outputs=0
  missing_output_files=()
  jobs_to_submit=0
  hit_max_jobs=0

  for i in "${!job_datasets[@]}"; do
    dataset_name="${job_datasets[$i]}"
    file_suffix="${job_file_suffixes[$i]}"
    output_file="${output_dir}/${dataset_name}${file_suffix}.root"
    total_selected=$((total_selected + 1))

    if hist_output_exists "${output_file}"; then
      if [[ ${erase_existing} -eq 1 ]]; then
        echo "[ERASE] ${output_file}" | tee -a "${monitoring_file}"
        if [[ ${dry_run} -eq 0 ]]; then
          rm -f "${output_file}"
        fi
        erased_existing=$((erased_existing + 1))
      elif [[ ${force_submit} -eq 0 ]]; then
        echo "[DONE]  ${output_file}" >> "${monitoring_file}"
        completed_existing=$((completed_existing + 1))
        continue
      fi
    else
      echo "[MISS]  ${output_file}" >> "${monitoring_file}"
      missing_outputs=$((missing_outputs + 1))
      missing_output_files+=("${output_file}")
    fi

    if [[ ${condor} -eq 1 && ${force_submit} -eq 0 && ${erase_existing} -eq 0 ]]; then
      if is_output_in_registry "${output_file}" || is_output_already_queued "${output_file}"; then
        echo "[QUEUE] ${output_file}" >> "${monitoring_file}"
        queued_existing=$((queued_existing + 1))
        continue
      fi
    fi

    if [[ -n "${max_jobs}" && ${jobs_to_submit} -ge ${max_jobs} ]]; then
      hit_max_jobs=1
      continue
    fi

    printf '%s\t%s\t%s\t%s\n' \
      "${dataset_name}" \
      "${job_chunk_sizes[$i]}" \
      "${file_suffix}" \
      "${job_specific_opts[$i]}" \
      >> "${jobs_file}"
    jobs_to_submit=$((jobs_to_submit + 1))
  done

  printf '%s\n' "${extra_opts[*]}" > "${extra_opts_file}"
  if [[ -n "${job_count_file}" ]]; then
    printf '%s\n' "${jobs_to_submit}" > "${job_count_file}"
  fi
  if [[ -n "${summary_file}" ]]; then
    if [[ ! -s "${summary_file}" ]]; then
      printf 'era\tgroup\tselected\tcompleted_existing\tqueued_existing\tmissing_outputs\terased_existing\tjobs_to_submit\toutput_dir\tmonitoring_file\tsubmit_file\n' > "${summary_file}"
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "${era}" \
      "${group_label}" \
      "${total_selected}" \
      "${completed_existing}" \
      "${queued_existing}" \
      "${missing_outputs}" \
      "${erased_existing}" \
      "${jobs_to_submit}" \
      "${output_dir}" \
      "${monitoring_file}" \
      "${submit_file}" \
      >> "${summary_file}"
  fi

  {
    echo
    echo "========== HISTOGRAM CONDOR MONITORING =========="
    echo "era                : ${era}"
    echo "group              : ${group_label}"
    echo "selected datasets  : ${total_selected}"
    echo "completed existing : ${completed_existing}"
    echo "already queued     : ${queued_existing}"
    echo "missing outputs    : ${missing_outputs}"
    echo "erased existing    : ${erased_existing}"
    echo "jobs to submit     : ${jobs_to_submit}"
    if [[ ${#missing_output_files[@]} -gt 0 ]]; then
      echo "missing files      :"
      for missing_file in "${missing_output_files[@]}"; do
        echo "  - ${missing_file}"
      done
    fi
    if [[ -n "${max_jobs}" ]]; then
      echo "max jobs           : ${max_jobs}"
      echo "hit max jobs       : ${hit_max_jobs}"
    fi
    if [[ -n "${max_parallel_jobs}" ]]; then
      echo "max parallel jobs  : ${max_parallel_jobs}"
    fi
    echo "output dir         : ${output_dir}"
    echo "==============================================="
  } | tee -a "${monitoring_file}"

  if [[ ${jobs_to_submit} -eq 0 ]]; then
    echo "[INFO] All selected histogram outputs are already present. No jobs to submit."
    echo "[INFO] Monitoring report: ${monitoring_file}"
    exit 0
  fi

  cat > "${submit_file}" <<EOF
universe = vanilla
executable = ${wrapper}
arguments = ${analysis_path} ${analysis_path}/${jobs_file} \$(ProcId) ${era} ${input_folder} ${output_dir} ${analysis_path}/${extra_opts_file}

output = ${analysis_path}/${condor_output_dir}/\$(ProcId).out
error  = ${analysis_path}/${condor_error_dir}/\$(ProcId).err
log    = ${analysis_path}/${condor_log_dir}/condor.log

request_cpus = ${request_cpus}
request_memory = ${request_memory}
request_disk = ${request_disk}
+JobFlavour = "${job_flavour}"
+Era = "${era}"
+HistGroup = "${group_label}"
batch_name = Hists_${era}_${group_label}

max_retries = 1
getenv = True
EOF

  if [[ -n "${max_parallel_jobs}" ]]; then
    {
      echo "max_materialize = ${max_parallel_jobs}"
      echo
    } >> "${submit_file}"
  fi

  echo "queue ${jobs_to_submit}" >> "${submit_file}"

  echo
  echo "============================================================"
  echo "[INFO] Condor histogram submission prepared"
  echo "[INFO] Era        : ${era}"
  echo "[INFO] Jobs       : ${jobs_to_submit}"
  echo "[INFO] Completed  : ${completed_existing}"
  echo "[INFO] Queued     : ${queued_existing}"
  echo "[INFO] Missing    : ${missing_outputs}"
  if [[ -n "${max_parallel_jobs}" ]]; then
    echo "[INFO] Max parall.: ${max_parallel_jobs}"
  fi
  echo "[INFO] Output dir : ${output_dir}"
  echo "[INFO] Submit file: ${submit_file}"
  echo "[INFO] Jobs table : ${jobs_file}"
  echo "[INFO] Monitoring : ${monitoring_file}"
  echo "[INFO] Stdout     : ${condor_output_dir}"
  echo "[INFO] Stderr     : ${condor_error_dir}"
  echo "[INFO] Event log  : ${condor_log_dir}"
  echo "============================================================"

  if [[ ${dry_run} -eq 1 ]]; then
    echo "[DRY RUN] Not submitting. To submit manually:"
    echo "condor_submit ${submit_file}"
    exit 0
  fi

  condor_submit "${submit_file}"
  if [[ -n "${queued_registry_file}" ]]; then
    mkdir -p "$(dirname "${queued_registry_file}")"
    while IFS=$'\t' read -r submitted_dataset submitted_chunk submitted_suffix submitted_opts; do
      [[ -n "${submitted_dataset}" ]] || continue
      printf '%s\n' "${output_dir}/${submitted_dataset}${submitted_suffix}.root" >> "${queued_registry_file}"
    done < "${jobs_file}"
    sort -u -o "${queued_registry_file}" "${queued_registry_file}"
  fi
  exit 0
fi

for i in "${!job_datasets[@]}"; do
  dataset_name="${job_datasets[$i]}"
  chunk_size="${job_chunk_sizes[$i]}"
  file_suffix="${job_file_suffixes[$i]}"
  input_path="/eos/cms/store/group/phys_higgs/cmshmm/vdamante/${input_folder}/${era}/${dataset_name}/"
  output_file="${output_dir}/${dataset_name}${file_suffix}.root"

  if [[ ${missing_only} -eq 1 && ${force_submit} -eq 0 && ${erase_existing} -eq 0 ]]; then
    if hist_output_exists "${output_file}"; then
      echo "[DONE]  ${output_file}"
      echo "[INFO] --missing-only: output already exists, skipping ${dataset_name}."
      continue
    fi
  fi

  specific_opts=()
  if [[ -n "${job_specific_opts[$i]}" ]]; then
    # shellcheck disable=SC2206
    specific_opts=(${job_specific_opts[$i]})
  fi

  command=(
    python3 histograms/hist_maker.py
    --era "${era}"
    --dataset-name "${dataset_name}"
    --input "${input_path}"
    --output-file "${output_file}"
    --chunk-size "${chunk_size}"
  )
  command+=("${specific_opts[@]}")
  command+=("${extra_opts[@]}")

  echo
  echo "============================================================"
  echo "[INFO] Era     : ${era}"
  echo "[INFO] Dataset : ${dataset_name}"
  echo "[INFO] Input   : ${input_path}"
  echo "[INFO] Output  : ${output_file}"
  echo "[INFO] Command : ${command[*]}"
  echo "============================================================"

  if [[ ! -d "${input_path}" ]]; then
    echo "[WARNING] Input directory does not exist:"
    echo "          ${input_path}"
    echo "[WARNING] hist_maker.py will create an empty histogram file."
  fi

  if [[ ${dry_run} -eq 1 ]]; then
    continue
  fi

  "${command[@]}"
done
