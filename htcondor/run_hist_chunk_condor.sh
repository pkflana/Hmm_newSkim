#!/usr/bin/env bash
set -euo pipefail

analysis_path="$1"
era="$2"
dataset_name="$3"
input_path="$4"
manifest="$5"
output_file="$6"
specific_opts_file="$7"
extra_opts_file="$8"
metadata_input_path="${9:-}"

cd "${analysis_path}"
_saved_args=("$@")
set --
source "${analysis_path}/env.sh"
set -- "${_saved_args[@]}"
unset _saved_args

mkdir -p "$(dirname "${output_file}")"
rm -f "${output_file}" "${output_file}.failed_chunks.txt"

specific_opts=()
if [[ -s "${specific_opts_file}" ]]; then
  specific_opts_string="$(<"${specific_opts_file}")"
  # shellcheck disable=SC2206
  specific_opts=(${specific_opts_string})
fi

extra_opts=()
if [[ -s "${extra_opts_file}" ]]; then
  extra_opts_string="$(<"${extra_opts_file}")"
  # shellcheck disable=SC2206
  extra_opts=(${extra_opts_string})
fi

command=(
  python3 histograms/hist_maker.py
  --era "${era}"
  --dataset-name "${dataset_name}"
  --input "${input_path}"
  --input-files-file "${manifest}"
  --output-file "${output_file}"
  --chunk-size 1000000000
  --n-cores 1
  --skip-file-validation
)
if [[ -n "${metadata_input_path}" && "${metadata_input_path}" != "-" ]]; then
  command+=(--metadata-input "${metadata_input_path}")
fi
command+=("${specific_opts[@]}")
command+=("${extra_opts[@]}")

echo "============================================================"
echo "[INFO] Era      : ${era}"
echo "[INFO] Dataset  : ${dataset_name}"
echo "[INFO] Input    : ${input_path}"
echo "[INFO] Metadata : ${metadata_input_path:-${input_path}}"
echo "[INFO] Manifest : ${manifest}"
echo "[INFO] Output   : ${output_file}"
echo "[INFO] Command  : ${command[*]}"
echo "============================================================"

if [[ ! -d "${input_path}" ]]; then
  echo "[WARNING] Input directory does not exist: ${input_path}" >&2
  echo "[WARNING] Producing empty histograms for ${dataset_name}." >&2
fi
if [[ ! -e "${manifest}" ]]; then
  echo "[ERROR] Missing chunk manifest: ${manifest}" >&2
  exit 3
fi
if [[ ! -s "${manifest}" ]]; then
  echo "[WARNING] Empty chunk manifest: ${manifest}" >&2
  echo "[WARNING] Producing empty histograms for ${dataset_name}." >&2
fi

"${command[@]}"

if [[ ! -s "${output_file}" ]]; then
  echo "[ERROR] Histogram command completed without a non-empty output: ${output_file}" >&2
  exit 6
fi

rm -f "${output_file}.failed_chunks.txt"
