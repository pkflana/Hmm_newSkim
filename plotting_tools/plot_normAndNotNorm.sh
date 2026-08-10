#!/usr/bin/env bash
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi

set -e

chunk="${1:-all}"

print_chunks() {
    cat <<'EOF'
Available chunks:
  all
  2022_23_norm_zmass
  2022_23_norm_signal
  2022_23_plain_zmass
  2022_23_plain_signal
  2024_2025_norm_signal
  2024_2025_norm_zmass
  2024_2025_plain_signal
  2024_2025_plain_zmass

Era-level chunks for 2024/2025:
  2024_norm_signal
  2024_norm_zmass
  2024_plain_signal
  2024_plain_zmass
  2025_norm_signal
  2025_norm_zmass
  2025_plain_signal
  2025_plain_zmass

Fine-grained chunks for signal regions:
  Use: ERA_NORM_SIGNAL_COMPONENT
  ERA: 2024, 2025, 2024_2025
  NORM: norm, plain
  SIGNAL: signal
  COMPONENT: amcatnlo, flashsim, minnlo
  Examples:
  2024_norm_signal_amcatnlo
  2024_norm_signal_flashsim
  2024_norm_signal_minnlo
  2025_norm_signal_amcatnlo
  2025_norm_signal_flashsim
  2025_norm_signal_minnlo
  2025_plain_signal_amcatnlo
  2025_plain_signal_flashsim
  2025_plain_signal_minnlo
  2024_2025_norm_signal_flashsim

Fine-grained chunks for Z sideband and mass inclusive:
  Use: ERA_NORM_zmass_COMPONENT
  ERA: 2024, 2025, 2024_2025
  NORM: norm, plain
  COMPONENT: amcatnlo, minnlo
  Examples:
  2024_norm_zmass_amcatnlo
  2024_norm_zmass_minnlo
  2024_plain_zmass_amcatnlo
  2024_plain_zmass_minnlo
  2025_norm_zmass_amcatnlo
  2025_norm_zmass_minnlo
  2025_plain_zmass_amcatnlo
  2025_plain_zmass_minnlo
  2024_2025_plain_zmass_minnlo
EOF
}

should_run() {
    [[ "${chunk}" == "all" || "${chunk}" == "$1" ]]
}

should_enter_2024_2025_block() {
    local norm_state="$1"
    local scope="$2"

    [[ "${chunk}" == "all" ]] && return 0
    [[ "${chunk}" == "2024_2025_${norm_state}_${scope}" ]] && return 0
    [[ "${chunk}" == 2024_2025_${norm_state}_${scope}_* ]] && return 0
    [[ "${chunk}" == 2024_${norm_state}_${scope} ]] && return 0
    [[ "${chunk}" == 2024_${norm_state}_${scope}_* ]] && return 0
    [[ "${chunk}" == 2025_${norm_state}_${scope} ]] && return 0
    [[ "${chunk}" == 2025_${norm_state}_${scope}_* ]] && return 0

    return 1
}

should_run_2024_2025_component() {
    local era="$1"
    local norm_state="$2"
    local scope="$3"
    local component="$4"

    [[ "${chunk}" == "all" ]] && return 0
    [[ "${chunk}" == "2024_2025_${norm_state}_${scope}" ]] && return 0
    [[ "${chunk}" == "2024_2025_${norm_state}_${scope}_${component}" ]] && return 0
    [[ "${chunk}" == "${era}_${norm_state}_${scope}" ]] && return 0
    [[ "${chunk}" == "${era}_${norm_state}_${scope}_${component}" ]] && return 0

    return 1
}

eras_2024_2025() {
    case "${chunk}" in
        2024_*) echo "2024" ;;
        2025_*) echo "2025" ;;
        *) echo "2024 2025" ;;
    esac
}

if [[ "${chunk}" == "--list" || "${chunk}" == "list" ]]; then
    print_chunks
    exit 0
fi

known_chunk=0
for known in \
    all \
    2022_23_norm_zmass 2022_23_norm_signal 2022_23_plain_zmass 2022_23_plain_signal \
    2024_2025_norm_signal 2024_2025_norm_zmass 2024_2025_plain_signal 2024_2025_plain_zmass \
    2024_2025_norm_signal_amcatnlo 2024_2025_norm_signal_flashsim 2024_2025_norm_signal_minnlo \
    2024_2025_norm_zmass_amcatnlo 2024_2025_norm_zmass_minnlo \
    2024_2025_plain_signal_amcatnlo 2024_2025_plain_signal_flashsim 2024_2025_plain_signal_minnlo \
    2024_2025_plain_zmass_amcatnlo 2024_2025_plain_zmass_minnlo \
    2024_norm_signal 2024_norm_signal_amcatnlo 2024_norm_signal_flashsim 2024_norm_signal_minnlo \
    2024_norm_zmass 2024_norm_zmass_amcatnlo 2024_norm_zmass_minnlo \
    2024_plain_signal 2024_plain_signal_amcatnlo 2024_plain_signal_flashsim 2024_plain_signal_minnlo \
    2024_plain_zmass 2024_plain_zmass_amcatnlo 2024_plain_zmass_minnlo \
    2025_norm_signal 2025_norm_signal_amcatnlo 2025_norm_signal_flashsim 2025_norm_signal_minnlo \
    2025_norm_zmass 2025_norm_zmass_amcatnlo 2025_norm_zmass_minnlo \
    2025_plain_signal 2025_plain_signal_amcatnlo 2025_plain_signal_flashsim 2025_plain_signal_minnlo \
    2025_plain_zmass 2025_plain_zmass_amcatnlo 2025_plain_zmass_minnlo; do
    if [[ "${chunk}" == "${known}" ]]; then
        known_chunk=1
        break
    fi
done

if [[ "${known_chunk}" -ne 1 ]]; then
    echo "[ERROR] Unknown chunk: ${chunk}"
    print_chunks
    exit 1
fi

if should_run 2022_23_norm_zmass; then
for region in Z_sideband mass_inclusive;
    do for era in 2022_23;
        do for category in ggF VBF baseline;
            do
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_amcatnlo_weighted/  --region "${region}_${category}"  --samples DY_weighted Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W_NJets TT --wantLogY  --wantData  --rebin --normalize-dy-to-data --dy-normalization-sample DY_weighted;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_amcatnlo_pt_ll/  --region "${region}_${category}"  --samples DY_ptll Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W_NJets TT --wantLogY  --wantData  --rebin --normalize-dy-to-data --dy-normalization-sample DY_ptll;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_amcatnlo_unweighted/  --region "${region}_${category}"  --samples DY Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W_NJets TT --wantLogY  --wantData  --rebin --normalize-dy-to-data --dy-normalization-sample DY;
        done
    done
done
fi

if should_run 2022_23_norm_signal; then
for region in Signal_Fit;
    do for era in 2022_23;
        do for category in ggF VBF baseline;
            do
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_amcatnlo_weighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_weighted Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W_NJets TT --wantLogY  --wantData  --rebin --normalize-dy-to-data --dy-normalization-sample DYto2Mu_MLL105To160_weighted;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_amcatnlo_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160 Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W_NJets TT --wantLogY  --wantData  --rebin --normalize-dy-to-data --dy-normalization-sample DYto2Mu_MLL105To160;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_amcatnlo_pt_ll/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_ptll Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W_NJets TT --wantLogY  --wantData  --rebin --normalize-dy-to-data --dy-normalization-sample DYto2Mu_MLL105To160_ptll;
        done
    done
done
fi

if should_run 2022_23_plain_zmass; then
for region in Z_sideband mass_inclusive;
    do for era in 2022_23;
        do for category in ggF VBF baseline;
            do
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_amcatnlo_weighted/  --region "${region}_${category}"  --samples DY_weighted Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W_NJets TT --wantLogY  --wantData  --rebin ;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_amcatnlo_pt_ll/  --region "${region}_${category}"  --samples DY_ptll Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W_NJets TT --wantLogY  --wantData  --rebin ;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_amcatnlo_unweighted/  --region "${region}_${category}"  --samples DY Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W_NJets TT --wantLogY  --wantData  --rebin ;
        done
    done
done
fi

if should_run 2022_23_plain_signal; then
for region in Signal_Fit;
    do for era in 2022_23;
        do for category in ggF VBF baseline;
            do
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_amcatnlo_weighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_weighted Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W_NJets TT --wantLogY  --wantData  --rebin ;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_amcatnlo_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160 Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W_NJets TT --wantLogY  --wantData  --rebin ;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_amcatnlo_pt_ll/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_ptll Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W_NJets TT --wantLogY  --wantData  --rebin ;
        done
    done
done
fi

if should_enter_2024_2025_block norm signal; then
for region in Signal_Fit;
    do for era in $(eras_2024_2025);
        do for category in ggF VBF baseline;
            do


            if should_run_2024_2025_component "${era}" norm signal amcatnlo; then
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_amcatnlo_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160 DYto2Mu_MLL105To160_VBFFiltered Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu_amcatnlo SingleH SingleTop TTX VBFHto2Mu_M125_amcatnlo  DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data;

            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_amcatnlo_pt_ll/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_ptll DYto2Mu_MLL105To160_VBFFiltered_ptll Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu_amcatnlo SingleH SingleTop TTX VBFHto2Mu_M125_amcatnlo  DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data;

            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_amcatnlo_weighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_weighted DYto2Mu_MLL105To160_VBFFiltered_weighted Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu_amcatnlo SingleH SingleTop TTX VBFHto2Mu_M125_amcatnlo  DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data;
            fi



            if should_run_2024_2025_component "${era}" norm signal flashsim; then
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_FlashSim_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_FlashSim Data_Muon EWK_2Mu2J_MLL_105to160_pythia_Flashsim GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_m125_Flashsim  DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data;

            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_FlashSim_pt_ll/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_FlashSim_ptll Data_Muon EWK_2Mu2J_MLL_105to160_pythia_Flashsim GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_m125_Flashsim  DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data;

            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_FlashSim_weighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_FlashSim_weighted Data_Muon EWK_2Mu2J_MLL_105to160_pythia_Flashsim GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_m125_Flashsim  DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data;
            fi

            if should_run_2024_2025_component "${era}" norm signal minnlo; then
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_minnlo_weighted/  --region "${region}_${category}"  --samples DYto2Mu_minnlo_weighted Data_Muon EWK GluGluHto2Mu_MiNNLO SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data;

            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_minnlo_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_minnlo Data_Muon EWK GluGluHto2Mu_MiNNLO SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data;
            fi


        done
    done
done
fi


if should_enter_2024_2025_block norm zmass; then
for region in Z_sideband mass_inclusive;
    do for era in $(eras_2024_2025);
        do for category in ggF VBF baseline;
            do
            if should_run_2024_2025_component "${era}" norm zmass amcatnlo; then
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_amcatnlo_weighted/  --region "${region}_${category}"  --samples DY_weighted Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data --dy-normalization-sample DY_weighted;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_amcatnlo_pt_ll/  --region "${region}_${category}"  --samples DY_ptll Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data --dy-normalization-sample DY_ptll;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_amcatnlo_unweighted/  --region "${region}_${category}"  --samples DY Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data --dy-normalization-sample DY;
            fi

            if should_run_2024_2025_component "${era}" norm zmass minnlo; then
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_minnlo_weighted/  --region "${region}_${category}"  --samples DYto2Mu_minnlo_weighted Data_Muon EWK GluGluHto2Mu_MiNNLO SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data --dy-normalization-sample DYto2Mu_minnlo_weighted;

            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9_DYNorm/DY_minnlo_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_minnlo Data_Muon EWK GluGluHto2Mu_MiNNLO SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin --normalize-dy-to-data --dy-normalization-sample DYto2Mu_minnlo;
            fi

        done
    done
done
fi

if should_enter_2024_2025_block plain signal; then
for region in Signal_Fit;
    do for era in $(eras_2024_2025);
        do for category in ggF VBF baseline;
            do


            if should_run_2024_2025_component "${era}" plain signal amcatnlo; then
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_amcatnlo_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160 DYto2Mu_MLL105To160_VBFFiltered Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu_amcatnlo SingleH SingleTop TTX VBFHto2Mu_M125_amcatnlo  DiTriBoson W TT --wantLogY  --wantData  --rebin;

            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_amcatnlo_pt_ll/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_ptll DYto2Mu_MLL105To160_VBFFiltered_ptll Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu_amcatnlo SingleH SingleTop TTX VBFHto2Mu_M125_amcatnlo  DiTriBoson W TT --wantLogY  --wantData  --rebin;

            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_amcatnlo_weighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_weighted DYto2Mu_MLL105To160_VBFFiltered_weighted Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu_amcatnlo SingleH SingleTop TTX VBFHto2Mu_M125_amcatnlo  DiTriBoson W TT --wantLogY  --wantData  --rebin;
            fi



            if should_run_2024_2025_component "${era}" plain signal flashsim; then
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_FlashSim_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_FlashSim Data_Muon EWK_2Mu2J_MLL_105to160_pythia_Flashsim GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_m125_Flashsim  DiTriBoson W TT --wantLogY  --wantData  --rebin;

            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_FlashSim_pt_ll/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_FlashSim_ptll Data_Muon EWK_2Mu2J_MLL_105to160_pythia_Flashsim GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_m125_Flashsim  DiTriBoson W TT --wantLogY  --wantData  --rebin;

            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_FlashSim_weighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160_FlashSim_weighted Data_Muon EWK_2Mu2J_MLL_105to160_pythia_Flashsim GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_m125_Flashsim  DiTriBoson W TT --wantLogY  --wantData  --rebin;
            fi

            if should_run_2024_2025_component "${era}" plain signal minnlo; then
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_minnlo_weighted/  --region "${region}_${category}"  --samples DYto2Mu_minnlo_weighted Data_Muon EWK GluGluHto2Mu_MiNNLO SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY  --wantData  --rebin;

            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_minnlo_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_minnlo Data_Muon EWK GluGluHto2Mu_MiNNLO SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin;
            fi


        done
    done
done
fi


if should_enter_2024_2025_block plain zmass; then
for region in Z_sideband mass_inclusive;
    do for era in $(eras_2024_2025);
        do for category in ggF VBF baseline;
            do
            if should_run_2024_2025_component "${era}" plain zmass amcatnlo; then
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_amcatnlo_weighted/  --region "${region}_${category}"  --samples DY_weighted Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY  --wantData  --rebin ;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_amcatnlo_pt_ll/  --region "${region}_${category}"  --samples DY_ptll Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin ;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_amcatnlo_unweighted/  --region "${region}_${category}"  --samples DY Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin ;
            fi

            if should_run_2024_2025_component "${era}" plain zmass minnlo; then
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_minnlo_weighted/  --region "${region}_${category}"  --samples DYto2Mu_minnlo_weighted Data_Muon EWK GluGluHto2Mu_MiNNLO SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY  --wantData  --rebin ;

            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_data_mc_Jul9/DY_minnlo_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_minnlo Data_Muon EWK GluGluHto2Mu_MiNNLO SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin ;
            fi

        done
    done
done
fi
