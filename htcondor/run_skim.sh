#!/bin/bash
set -euo pipefail

export XRD_NETWORKSTACK=IPv4

proxy="$1"
analysis_path="$2"
era="$3"
input_list="$4"
dataset="$5"
output_file="$6"
report_file="$7"
cmssw_version="${8:-CMSSW_15_0_2}"
jerc_2025_mc_mode="${9:-config}"

cd "$analysis_path"

source ./env.sh --cmssw-version "$cmssw_version"
export X509_USER_PROXY="$proxy"

skim_extra_opts=()
case "$jerc_2025_mc_mode" in
  1|true)
    jerc_2025_mc_mode="jec2024_jer2025"
    ;;
  0|false)
    jerc_2025_mc_mode="config"
    ;;
esac

if [[ "$jerc_2025_mc_mode" != "config" ]]; then
  skim_extra_opts+=(--jerc-2025-mc-mode "$jerc_2025_mc_mode")
fi

python3 analysis/skim.py \
  --era "$era" \
  --input-file "$input_list" \
  --dataset-name "$dataset" \
  --output-file "$output_file" \
  --report-file "$report_file" \
  "${skim_extra_opts[@]}"
