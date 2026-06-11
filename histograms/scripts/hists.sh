#!/usr/bin/env bash
set -euo pipefail

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
  DY_minnlo
  EWK
  signals
  SingleH
  SingleTop
  TTX
  W

Options:
  --datasets GROUPS       Comma-separated list of groups, or "all".
  --era ERA              Era to run, e.g. Run3_2022.
  --input-folder NAME    Input skim folder. Default: skim_v1_noUnc.
  --output-suffix TEXT   Suffix appended to newHists_${era}.
  --extra-opts TEXT      Extra hist_maker.py options as a quoted string.
  --dry-run              Print commands without running them.
  -h, --help             Show this help.

Examples:
  histograms/scripts/hists.sh --datasets DiTriBoson,data --era Run3_2022
  histograms/scripts/hists.sh --datasets DY_amcatnlo --era Run3_2024 --output-suffix _DNN -- --variables DNN_NNOutput --skip-file-validation
  histograms/scripts/hists.sh --datasets all --era Run3_2025 --extra-opts "--n-cores 8 --resume"
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

require_known_era() {
  local era="$1"
  case "${era}" in
    Run3_2022|Run3_2022EE|Run3_2023|Run3_2023BPix|Run3_2024|Run3_2025|Run3_2026) ;;
    *) die "Unknown era '${era}'" ;;
  esac
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

add_data_jobs() {
  local era="$1"
  local datasets=()

  case "${era}" in
    Run3_2022)
      datasets=(Muon_Run2022C Muon_Run2022D SingleMuon_Run2022C)
      ;;
    Run3_2022EE)
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
    add_job "${dataset_name}" 6 "" --resume
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
        WW WWW_4F WWZ_4F WWto2L2Nu_powheg WWto4Q_powheg WWtoLNu2Q_powheg
        WZ WZZ WZto2L2Q_powheg WZto3LNu_powheg WZtoLNu2Q_powheg
        ZZ ZZZ ZZto2L2Nu_powheg ZZto2L2Q_powheg ZZto2Nu2Q_powheg ZZto4L_powheg
      )
      ;;
    DY_minnlo)
      chunk_size=30
      datasets=(DYto2Mu_MLL_50to130_powheg_minnlo)
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
    SingleH)
      datasets=(
        GluGluHto2B_M125 GluGluHto2Tau_UncorrelatedDecay_UnFiltered GluGluHto2Wto2L2Nu_M125
        VBFHto2B_M125 VBFHto2Tau_UncorrelatedDecay_UnFiltered VBFHto2Wto2L2Nu_M125
        ggZH_Hto2B_Zto2L ggZH_Hto2B_Zto2Q ggZH_Hto2Mu_ZtoAll_M125
        ZH_Hto2B_Zto2L ZH_Hto2B_Zto2Q ZH_Hto2Mu
        WminusH_Hto2B_WtoLNu WminusH_Hto2Mu WminusHto2Tau_UncorrelatedDecay_UnFiltered
        WplusH_Hto2B_WtoLNu WplusH_Hto2Mu WplusHto2Tau_UncorrelatedDecay_UnFiltered
      )
      ;;
    SingleTop)
      datasets=(
        TWminusto2L2Nu TWminusto4Q TWminustoLNu2Q TbarWplusto2L2Nu TbarWplusto4Q TbarWplustoLNu2Q
        TBbarQto2Q_t_channel_4FS TBbarQtoLNu_t_channel_4FS TBbartoLplusNuBbar_s_channel_4FS
        TbarBQto2Q_t_channel_4FS TbarBQtoLNu_t_channel_4FS TbarBtoLminusNuB_s_channel_4FS
      )
      ;;
    TTX)
      chunk_size=10
      datasets=(TTto4Q TTtoLNu2Q)
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
      datasets=(WtoENu_amcatnloFXFX WtoLNu_1J_madgraphMLM WtoLNu_2J_madgraphMLM WtoLNu_3J_madgraphMLM WtoLNu_4J_madgraphMLM WtoMuNu_amcatnloFXFX WtoTauNu_amcatnloFXFX)
      ;;
    Run3_2022|Run3_2022EE|Run3_2023|Run3_2023BPix)
      datasets=(WtoLNu_0J_amcatnloFXFX WtoLNu_1J_amcatnloFXFX WtoLNu_2J_amcatnloFXFX)
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
    dy_minnlo|DY_minnlo) echo "DY_minnlo" ;;
    ewk|EWK) echo "EWK" ;;
    signals|Signals) echo "signals" ;;
    singleh|SingleH) echo "SingleH" ;;
    singletop|SingleTop) echo "SingleTop" ;;
    ttx|TTX) echo "TTX" ;;
    w|W) echo "W" ;;
    all|All) echo "all" ;;
    *) die "Unknown dataset group '$1'. Run with --help for the list." ;;
  esac
}

dataset_groups=()
era=""
input_folder="skim_v1_noUnc"
output_suffix=""
extra_opts=()
dry_run=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --datasets|--dataset-groups|--groups)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      split_csv "$2" dataset_groups
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
    --extra-opts|--extra-options)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      append_extra_opts_string "$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
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

[[ ${#dataset_groups[@]} -gt 0 ]] || die "Missing --datasets"
[[ -n "${era}" ]] || die "Missing --era"
require_known_era "${era}"

all_groups=(data DiTriBoson DY_amcatnlo DY_amcatnlo_105_160 DY_amcatnlo_105_160_stitched DY_minnlo EWK signals SingleH SingleTop TTX W)
normalized_groups=()
for group in "${dataset_groups[@]}"; do
  group="$(normalize_group "${group}")"
  if [[ "${group}" == "all" ]]; then
    normalized_groups=("${all_groups[@]}")
    break
  fi
  normalized_groups+=("${group}")
done

job_datasets=()
job_chunk_sizes=()
job_file_suffixes=()
job_specific_opts=()

for group in "${normalized_groups[@]}"; do
  case "${group}" in
    data) add_data_jobs "${era}" ;;
    DY_amcatnlo) add_dy_amcatnlo_jobs "${era}" ;;
    DY_amcatnlo_105_160) add_dy_105_160_jobs "${era}" ;;
    DY_amcatnlo_105_160_stitched) add_dy_105_160_stitched_jobs "${era}" ;;
    W) add_w_jobs "${era}" ;;
    DiTriBoson|DY_minnlo|EWK|signals|SingleH|SingleTop|TTX) add_static_group_jobs "${group}" ;;
    *) die "Internal error: unhandled group '${group}'" ;;
  esac
done

[[ ${#job_datasets[@]} -gt 0 ]] || die "No jobs selected"

output_dir="/eos/user/v/vdamante/H_mumu/newHists_${era}${output_suffix}"
if [[ ${dry_run} -eq 0 ]]; then
  mkdir -p "${output_dir}"
fi

for i in "${!job_datasets[@]}"; do
  dataset_name="${job_datasets[$i]}"
  chunk_size="${job_chunk_sizes[$i]}"
  file_suffix="${job_file_suffixes[$i]}"
  input_path="/eos/cms/store/group/phys_higgs/cmshmm/vdamante/${input_folder}/${era}/${dataset_name}/"
  output_file="${output_dir}/${dataset_name}${file_suffix}.root"

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
    echo "[WARNING] Input directory does not exist, skipping:"
    echo "          ${input_path}"
    continue
  fi

  if [[ ${dry_run} -eq 1 ]]; then
    continue
  fi

  "${command[@]}"
done
