#!/usr/bin/env bash
set -euo pipefail

analysis_path="$1"
jobs_file="$2"
proc_id="$3"
mode="$4"
era="$5"
manifest_input_folder="$6"
root_input_folder="$7"
json_input_folder="$8"
output_dir="$9"
extra_opts_file="${10:-}"
file_open_retries="${11:-3}"
file_open_retry_delay="${12:-2}"
additional_metadata_bases_csv="${13:-}"

cd "${analysis_path}"
_saved_args=("$@")
set --
source "${analysis_path}/env.sh"
set -- "${_saved_args[@]}"

job_line="$(sed -n "$((proc_id + 1))p" "${jobs_file}")"
[[ -n "${job_line}" ]] || { echo "Missing job ${proc_id}" >&2; exit 2; }
# A tab belongs to Bash's IFS whitespace class, so `read` collapses adjacent
# tabs.  That used to shift the fourth field into `file_suffix` whenever the
# suffix was empty, e.g. `--additional-cuts ...` became part of the ROOT name.
# Translate tabs to a non-whitespace separator first so empty TSV fields survive.
job_record="${job_line//$'\t'/$'\x1f'}"
IFS=$'\x1f' read -r dataset chunk_size file_suffix specific_opts_string \
  <<< "${job_record}"
[[ "${file_suffix}" == "-" ]] && file_suffix=""
[[ "${specific_opts_string}" == "-" ]] && specific_opts_string=""

dataset_path() {
  local base="$1"
  if [[ "${base}" = /* ]]; then
    printf '%s/%s/%s' "${base}" "${era}" "${dataset}"
  else
    printf '/eos/cms/store/group/phys_higgs/cmshmm/vdamante/%s/%s/%s' "${base}" "${era}" "${dataset}"
  fi
}

manifest_path() {
  local era_manifest="${manifest_input_folder}/${era}/${dataset}.json"
  local flat_manifest="${manifest_input_folder}/${dataset}.json"

  if [[ -f "${era_manifest}" || ! -f "${flat_manifest}" ]]; then
    printf '%s' "${era_manifest}"
  else
    printf '%s' "${flat_manifest}"
  fi
}

histogram_output_path() {
  printf '%s/%s/%s%s.root' "${output_dir}" "${era}" "${dataset}" "${file_suffix}"
}

json_input="$(dataset_path "${json_input_folder}")"
root_input="$(dataset_path "${root_input_folder}")"
additional_metadata_args=()
if [[ -n "${additional_metadata_bases_csv}" ]]; then
  IFS=',' read -r -a additional_metadata_bases <<< "${additional_metadata_bases_csv}"
  for metadata_base in "${additional_metadata_bases[@]}"; do
    [[ -n "${metadata_base}" ]] || continue
    additional_metadata_args+=(--additional-metadata-input "$(dataset_path "${metadata_base}")")
  done
fi
specific_opts=()
[[ -z "${specific_opts_string}" ]] || read -r -a specific_opts <<< "${specific_opts_string}"
extra_opts=()
if [[ -s "${extra_opts_file}" ]]; then
  read -r -a extra_opts <<< "$(<"${extra_opts_file}")"
fi

case "${mode}" in
  validation)
    output="${output_dir}/${era}/${dataset}.json"
    command=(python3 analysis/validate_dataset.py --era "${era}" --dataset-name "${dataset}" --root-input "${root_input}" --json-input "${json_input}" --output-manifest "${output}" --workers "${chunk_size}" --retries "${file_open_retries}" --retry-delay "${file_open_retry_delay}")
    ;;
  systematics)
    manifest="$(manifest_path)"
    output="$(histogram_output_path)"
    command=(python3 histograms/hist_maker.py --era "${era}" --root-input "${root_input}" --json-input "${json_input}" "${additional_metadata_args[@]}" --dataset-name "${dataset}" --input-manifest "${manifest}" --output-file "${output}" --chunk-size "${chunk_size}" --file-open-retries "${file_open_retries}" --file-open-retry-delay "${file_open_retry_delay}")
    ;;
  histograms)
    manifest="$(manifest_path)"
    output="$(histogram_output_path)"
    command=(python3 histograms/hist_maker.py --era "${era}" --root-input "${root_input}" --json-input "${json_input}" "${additional_metadata_args[@]}" --dataset-name "${dataset}" --input-manifest "${manifest}" --output-file "${output}" --chunk-size "${chunk_size}" --file-open-retries "${file_open_retries}" --file-open-retry-delay "${file_open_retry_delay}")
    ;;
  *) echo "Unknown mode: ${mode}" >&2; exit 2 ;;
esac
command+=("${specific_opts[@]}" "${extra_opts[@]}")
mkdir -p "$(dirname "${output}")"
echo "[STAGE] ${mode} ${era}/${dataset}"
echo "[COMMAND] ${command[*]}"
"${command[@]}"
