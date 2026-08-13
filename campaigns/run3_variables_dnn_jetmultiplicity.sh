#!/usr/bin/env bash
#
# Campagne di istogrammi Run 3:
#   variables         tutte le variabili di config/<ERA>/maincfg.yaml
#   dnn               solo DNN_NNOutput
#   jet-multiplicity  variabili del maincfg in 0J/1J/>=2J per
#                     DY, EWK, ggH->mumu e VBFH->mumu
#
# Lo script stampa soltanto il piano, salvo ACTION=run. ACTION=check non
# modifica nulla e riporta output mancanti, job in coda e directory temporanee.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

ERAS=(2022 2022EE 2023 2023BPix 2024 2025)
SYSTEMATICS=(Central JERC ScaRe Muon PU QCDScale PDF)
MASS_REGIONS=(Signal_Fit Z_sideband H_sideband)
JET_CATEGORIES=(ggF_0J ggF_1J ggF_ge2J VBF_ge2J)
JET_DATASET_GROUPS=(DY_amcatnlo DY_amcatnlo_105_160 EWK signals)

INPUT_DIR="${INPUT_DIR:-/eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3}"
MANIFESTS="${MANIFESTS:-/eos/user/v/vdamante/H_mumu/manifests_skim_v3}"
OUTPUT_BASE="${OUTPUT_BASE:-/eos/user/v/vdamante/H_mumu/campaigns}"
CHUNK_SIZE="${CHUNK_SIZE:-1}"
CORES="${CORES:-1}"

join_csv() {
    local IFS=,
    printf '%s' "$*"
}

usage() {
    cat <<'EOF'
Uso:
  bash campaigns/run3_variables_dnn_jetmultiplicity.sh PROFILE MODE ACTION

PROFILE:
  variables          variabili definite in maincfg.yaml
  dnn                solo DNN_NNOutput
  jet-multiplicity   variabili di maincfg.yaml nelle categorie
                     ggF_0J, ggF_1J, ggF_ge2J, VBF_ge2J;
                     campioni DY, EWK e signals (ggH/VBFH -> mumu)
  all                esegue i tre profili

MODE:
  condor             crea/sottomette job HTCondor
  local              esegue localmente

ACTION:
  plan               mostra i comandi senza eseguirli
  check              controlla output mancanti/in coda/temporanei
  run                esegue o sottomette soltanto gli output mancanti

Esempi:
  bash campaigns/run3_variables_dnn_jetmultiplicity.sh all condor plan
  bash campaigns/run3_variables_dnn_jetmultiplicity.sh dnn condor run
  bash campaigns/run3_variables_dnn_jetmultiplicity.sh jet-multiplicity condor check

Override senza modificare lo script:
  OUTPUT_BASE=/eos/user/... INPUT_DIR=/eos/... MANIFESTS=/eos/... bash ...
EOF
}

profile_output() {
    case "$1" in
        variables)        printf '%s/Variables' "${OUTPUT_BASE}" ;;
        dnn)              printf '%s/DNN' "${OUTPUT_BASE}" ;;
        jet-multiplicity) printf '%s/VariablesJetMultiplicity' "${OUTPUT_BASE}" ;;
        *) return 2 ;;
    esac
}

profile_arguments() {
    local profile="$1"
    PROFILE_ARGS=()
    case "${profile}" in
        variables)
            # L'assenza di -v usa maincfg.yaml per ogni era.
            ;;
        dnn)
            PROFILE_ARGS+=(
                -v DNN_NNOutput
                -r "$(join_csv "${MASS_REGIONS[@]}")"
            )
            ;;
        jet-multiplicity)
            PROFILE_ARGS+=(
                --datasets "$(join_csv "${JET_DATASET_GROUPS[@]}")"
                -r "$(join_csv "${MASS_REGIONS[@]}")"
                -c "$(join_csv "${JET_CATEGORIES[@]}")"
            )
            ;;
        *) return 2 ;;
    esac
}

run_profile() {
    local profile="$1"
    local mode="$2"
    local action="$3"
    local output
    output="$(profile_output "${profile}")"
    profile_arguments "${profile}"

    local command=(
        ./hmumu hist
        -e "$(join_csv "${ERAS[@]}")"
        -s "$(join_csv "${SYSTEMATICS[@]}")"
        --input-dir "${INPUT_DIR}"
        --manifests "${MANIFESTS}"
        --output-base "${output}"
        --chunk-size "${CHUNK_SIZE}"
        --cores "${CORES}"
        "${PROFILE_ARGS[@]}"
    )

    case "${mode}" in
        condor) command+=(--condor) ;;
        local)  command+=(--local) ;;
        *) printf 'ERRORE: MODE deve essere condor o local\n' >&2; return 2 ;;
    esac
    case "${action}" in
        plan) ;;
        check) command+=(--check) ;;
        run) command+=(--run) ;;
        *) printf 'ERRORE: ACTION deve essere plan, check o run\n' >&2; return 2 ;;
    esac

    printf '\n========== %s / %s / %s ==========\n' \
        "${profile}" "${mode}" "${action}"
    "${command[@]}"
}

PROFILE="${1:-}"
MODE="${2:-}"
ACTION="${3:-}"

if [[ -z "${PROFILE}" || -z "${MODE}" || -z "${ACTION}" ]]; then
    usage
    exit 2
fi

case "${PROFILE}" in
    variables|dnn|jet-multiplicity)
        run_profile "${PROFILE}" "${MODE}" "${ACTION}"
        ;;
    all)
        for profile in variables dnn jet-multiplicity; do
            run_profile "${profile}" "${MODE}" "${ACTION}"
        done
        ;;
    *)
        usage
        printf '\nERRORE: PROFILE non valido: %s\n' "${PROFILE}" >&2
        exit 2
        ;;
esac
