#!/bin/bash
set -euo pipefail

export XRD_NETWORKSTACK=IPv4

proxy="$1"
analysis_path="$2"
era="$3"
input_list="$4"
dataset="$5"
output_list="$6"
cmssw_version="${7:-CMSSW_15_0_2}"
use_2024_jerc_for_2025_mc="${8:-0}"

cd "$analysis_path"

source ./env.sh --cmssw-version "$cmssw_version"
export X509_USER_PROXY="$proxy"

IFS=',' read -r -a INPUT_FILES <<< "$input_list"
IFS=',' read -r -a OUTPUT_FILES <<< "$output_list"

skim_extra_opts=()
if [[ "$use_2024_jerc_for_2025_mc" == "1" || "$use_2024_jerc_for_2025_mc" == "true" ]]; then
  skim_extra_opts+=(--use-2024-jerc-for-2025-mc)
fi

for i in "${!INPUT_FILES[@]}"; do
  python3 analysis/skim.py --era "$era" --input-file "${INPUT_FILES[$i]}" --dataset-name "$dataset" --output-file "${OUTPUT_FILES[$i]}" "${skim_extra_opts[@]}"
done
