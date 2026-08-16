#!/usr/bin/env bash
#
# Driver completo per tre campagne Run 3:
#   dnn   : DNN_NNOutput, tre mass region, categoria VBF
#   jets  : componenti DY hard/PU e sottocategorie di molteplicità dei jet
#   plain : configurazione standard dei maincfg, senza override
#
# Esempi:
#   bash campaigns/run3_histogram_workflows.sh dnn produce condor plan
#   bash campaigns/run3_histogram_workflows.sh dnn produce condor check
#   bash campaigns/run3_histogram_workflows.sh dnn produce condor run
#   bash campaigns/run3_histogram_workflows.sh dnn hadd-processes - run
#   bash campaigns/run3_histogram_workflows.sh dnn merge-eras - run
#   bash campaigns/run3_histogram_workflows.sh dnn merge-systematics - run

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

ERAS=(2022 2022EE 2023 2023BPix 2024 2025)
SYSTEMATICS=(Central JERC ScaRe Muon PU QCDScale PDF)
MASS_REGIONS=(Signal_Fit Z_sideband H_sideband)

EOS_BASE="/eos/user/v/vdamante/H_mumu/campaigns"
INPUT_DIR="/eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3"
MANIFESTS="/eos/user/v/vdamante/H_mumu/manifests_skim_v3"

CHUNK_SIZE=1
CORES=1

join_csv() {
    local IFS=,
    printf '%s' "$*"
}

usage() {
    cat <<'EOF'
Uso:
  bash campaigns/run3_histogram_workflows.sh PROFILE STAGE MODE ACTION

PROFILE:
  dnn       DNN_NNOutput in Signal_Fit, Z_sideband, H_sideband; categoria VBF
  jets      componenti DY hard/PU e sottocategorie dei jet
  plain     variabili, regioni e categorie prese dai maincfg
  all       applica lo stage a tutte e tre le campagne

STAGE:
  produce               produzione per-dataset
  hadd-processes        dataset -> processi, separatamente per sistematica
  merge-eras            crea Run3_2022_23 nei file per-processo
  merge-systematics     Central + shifted nei file per-processo

MODE (usato soltanto da "produce"):
  local
  condor
  -                     per gli stage di merge

ACTION:
  plan                   stampa senza eseguire
  check                  controlla missing, queued e directory *_tmp
                         (solo per produce)
  run                    esegue o sottomette soltanto gli output mancanti

Esempio end-to-end per DNN:
  ... dnn produce condor check
  ... dnn produce condor run
  # attendere il completamento dei job
  ... dnn produce condor check
  ... dnn hadd-processes - run
  ... dnn merge-eras - run
  ... dnn merge-systematics - run
EOF
}

campaign_root() {
    case "$1" in
        dnn)   printf '%s/DNN' "${EOS_BASE}" ;;
        jets)  printf '%s/JetComponents' "${EOS_BASE}" ;;
        plain) printf '%s/Plain' "${EOS_BASE}" ;;
        *) return 2 ;;
    esac
}

profile_hist_args() {
    local profile="$1"
    PROFILE_ARGS=()
    case "${profile}" in
        dnn)
            PROFILE_ARGS+=(
                -v DNN_NNOutput
                -r "$(join_csv "${MASS_REGIONS[@]}")"
                -c VBF
            )
            ;;
        jets)
            PROFILE_ARGS+=(
                --datasets DY_amcatnlo,DY_amcatnlo_105_160
                -r "$(join_csv "${MASS_REGIONS[@]}")"
                --dy-jet-components
            )
            ;;
        plain)
            # Nessun -v, -r o -c: usa integralmente il maincfg di ogni era.
            ;;
        *) return 2 ;;
    esac
}

produce() {
    local profile="$1"
    local mode="$2"
    local action="$3"
    local root
    root="$(campaign_root "${profile}")"
    profile_hist_args "${profile}"

    local command=(
        ./hmumu hist
        -e "$(join_csv "${ERAS[@]}")"
        -s "$(join_csv "${SYSTEMATICS[@]}")"
        --input-dir "${INPUT_DIR}"
        --manifests "${MANIFESTS}"
        --output-base "${root}"
        --chunk-size "${CHUNK_SIZE}"
        --cores "${CORES}"
        "${PROFILE_ARGS[@]}"
    )

    case "${mode}" in
        local)  command+=(--local) ;;
        condor) command+=(--condor) ;;
        *) printf 'ERRORE: MODE deve essere local o condor per produce\n' >&2; return 2 ;;
    esac
    case "${action}" in
        plan) ;;
        check) command+=(--check) ;;
        run) command+=(--run) ;;
        *) printf 'ERRORE: ACTION non valida: %s\n' "${action}" >&2; return 2 ;;
    esac
    "${command[@]}"
}

hadd_processes() {
    local profile="$1"
    local action="$2"
    local root systematic
    root="$(campaign_root "${profile}")"

    [[ "${action}" != check ]] || {
        printf 'ERRORE: usare plan o run per hadd-processes\n' >&2
        return 2
    }
    for systematic in "${SYSTEMATICS[@]}"; do
        command=(
            ./hmumu hadd-processes
            "${root}/Hists_${systematic}"
            -e "$(join_csv "${ERAS[@]}")"
            -o "${root}/hadded/Hists_${systematic}"
        )
        [[ "${action}" == run ]] && command+=(--run)
        "${command[@]}"
    done
}

merge_eras() {
    local profile="$1"
    local action="$2"
    local root systematic
    root="$(campaign_root "${profile}")"

    [[ "${action}" != check ]] || {
        printf 'ERRORE: usare plan o run per merge-eras\n' >&2
        return 2
    }
    for systematic in "${SYSTEMATICS[@]}"; do
        command=(
            ./hmumu merge-eras
            "${root}/hadded/Hists_${systematic}"
        )
        [[ "${action}" == run ]] && command+=(--run)
        "${command[@]}"
    done
}

merge_systematics() {
    local profile="$1"
    local action="$2"
    local root
    root="$(campaign_root "${profile}")"

    [[ "${action}" != check ]] || {
        printf 'ERRORE: usare plan o run per merge-systematics\n' >&2
        return 2
    }
    command=(
        ./hmumu merge-systematics
        "${root}/hadded/Hists_Central"
        -s "$(join_csv "${SYSTEMATICS[@]}")"
        -o "${root}/hadded/Hists_merged"
    )
    [[ "${action}" == run ]] && command+=(--run)
    "${command[@]}"
}

run_profile() {
    local profile="$1"
    local stage="$2"
    local mode="$3"
    local action="$4"
    printf '\n========== %s / %s / %s ==========\n' "${profile}" "${stage}" "${action}"
    case "${stage}" in
        produce)             produce "${profile}" "${mode}" "${action}" ;;
        hadd-processes)      hadd_processes "${profile}" "${action}" ;;
        merge-eras)          merge_eras "${profile}" "${action}" ;;
        merge-systematics)   merge_systematics "${profile}" "${action}" ;;
        *) printf 'ERRORE: STAGE non valido: %s\n' "${stage}" >&2; return 2 ;;
    esac
}

PROFILE="${1:-}"
STAGE="${2:-}"
MODE="${3:-}"
ACTION="${4:-}"

if [[ -z "${PROFILE}" || -z "${STAGE}" || -z "${MODE}" || -z "${ACTION}" ]]; then
    usage
    exit 2
fi

case "${PROFILE}" in
    dnn|jets|plain)
        run_profile "${PROFILE}" "${STAGE}" "${MODE}" "${ACTION}"
        ;;
    all)
        for profile in dnn jets plain; do
            run_profile "${profile}" "${STAGE}" "${MODE}" "${ACTION}"
        done
        ;;
    *)
        usage
        printf '\nERRORE: PROFILE non valido: %s\n' "${PROFILE}" >&2
        exit 2
        ;;
esac
