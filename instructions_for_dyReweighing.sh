#!/usr/bin/env bash

# DY reweighting workflow, written era by era.
#
# Important:
# - 2022/2022EE/2023/2023BPix have only:
#     DY_amcatnlo, DY_amcatnlo_105_160
# - 2024/2025 have also:
#     DY_amcatnlo_105_160_stitched, DY_amcatnlo_105_160_VBFFil, DY_minnlo
# - DY_minnlo is recalculated only in the final _weighted step, after both
#   pt(ll) and NJets reweights are available.
# - Do not manually cp DY 105-160 dataset files into hadded outputs anymore.
#   histograms/hadd_hists_to_processes.py now maps *_stitched and *_nonStitched
#   files to the proper process names.

source env.sh


###############################################################################
# Run3_2022
###############################################################################

era=Run3_2022

era=Run3_2022;sh histograms/scripts/hists.sh --datasets DY_amcatnlo,TT,data,EWK,SingleH,DiTriBoson,SingleTop,TTX,W --era ${era}  --output-suffix _ptllNJetsRW --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW --missing-only -- --variables pt_mumu N_SelectedJets --categories ggF_0J ggF_1J ggF_ge2J VBF_ge2J --mass-regions Z_sideband
era=Run3_2022;python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW/ --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/ --era ${era}

era=Run3_2022;sh histograms/scripts/hists.sh --datasets all --era ${era}  --missing-only
sh histograms/scripts/hists.sh --datasets all --era ${era}  --output-suffix _DNN --missing-only -- --variables DNN_NNOutput
era=Run3_2022;python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ --era ${era}

era=Run3_2022;python3 histograms/derive_dy_ptll_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/ --output-dir reweights/dy_ptll_reweight/${era}/plots_smart --output-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --output-root reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.root --smart-rebin

era=Run3_2022; sh histograms/scripts/hists.sh --datasets DY_amcatnlo,DY_amcatnlo_105_160 --era ${era} --output-suffix _with_ptll_only_rw --missing-only -- --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
era=Run3_2022; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/ --era ${era}
era=Run3_2022;cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DY_ptll.root
era=Run3_2022;cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_ptll.root

era=Run3_2022; python3 histograms/derive_dy_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ --output-dir reweights/dy_njets_reweight/${era}/plots --output-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json --output-root reweights/dy_njets_reweight/${era}/dy_njets_reweight.root --dy-sample DY_ptll

era=Run3_2022;sh histograms/scripts/hists.sh --datasets DY_amcatnlo,DY_amcatnlo_105_160 --era ${era}  --output-suffix _weighted --missing-only -- --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json
era=Run3_2022;python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/ --era ${era}
era=Run3_2022;cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DY_weighted.root
era=Run3_2022;cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_weighted.root


###############################################################################
# Run3_2022EE
###############################################################################

era=Run3_2022EE

era=Run3_2022EE;sh histograms/scripts/hists.sh --datasets DY_amcatnlo,TT,data,EWK,SingleH,DiTriBoson,SingleTop,TTX,W --era ${era}  --output-suffix _ptllNJetsRW --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW --missing-only -- --variables pt_mumu N_SelectedJets --categories ggF_0J ggF_1J ggF_ge2J VBF_ge2J --mass-regions Z_sideband
era=Run3_2022EE;python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW/ --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/ --era ${era}

era=Run3_2022EE;sh histograms/scripts/hists.sh --datasets all --era ${era}  --missing-only
era=Run3_2022EE;sh histograms/scripts/hists.sh --datasets all --era ${era}  --output-suffix _DNN --missing-only -- --variables DNN_NNOutput
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ --era ${era}

era=Run3_2022EE;python3 histograms/derive_dy_ptll_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/ --output-dir reweights/dy_ptll_reweight/${era}/plots_smart --output-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --output-root reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.root --smart-rebin

era=Run3_2022EE;sh histograms/scripts/hists.sh --datasets DY_amcatnlo,DY_amcatnlo_105_160 --era ${era}  --output-suffix _with_ptll_only_rw --missing-only -- --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
era=Run3_2022EE;python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/ --era ${era}
era=Run3_2022EE;cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DY_ptll.root
era=Run3_2022EE;cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_ptll.root

era=Run3_2022EE;python3 histograms/derive_dy_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ --output-dir reweights/dy_njets_reweight/${era}/plots --output-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json --output-root reweights/dy_njets_reweight/${era}/dy_njets_reweight.root --dy-sample DY_ptll

era=Run3_2022EE;sh histograms/scripts/hists.sh --datasets DY_amcatnlo,DY_amcatnlo_105_160 --era ${era}  --output-suffix _weighted --missing-only -- --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json
era=Run3_2022EE;python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/ --era ${era}
era=Run3_2022EE;cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DY_weighted.root
era=Run3_2022EE;cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_weighted.root


###############################################################################
# Run3_2023
###############################################################################

era=Run3_2023

sh histograms/scripts/hists.sh --datasets DY_amcatnlo,TT,data,EWK,SingleH,DiTriBoson,SingleTop,TTX,W --era ${era}  --output-suffix _ptllNJetsRW --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW --missing-only -- --variables pt_mumu N_SelectedJets --categories ggF_0J ggF_1J ggF_ge2J VBF_ge2J --mass-regions Z_sideband
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW/ --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/ --era ${era}

sh histograms/scripts/hists.sh --datasets all --era ${era}  --missing-only
sh histograms/scripts/hists.sh --datasets all --era ${era}  --output-suffix _DNN --missing-only -- --variables DNN_NNOutput
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ --era ${era}

python3 histograms/derive_dy_ptll_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/ --output-dir reweights/dy_ptll_reweight/${era}/plots_smart --output-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --output-root reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.root --smart-rebin

sh histograms/scripts/hists.sh --datasets DY_amcatnlo,DY_amcatnlo_105_160 --era ${era}  --output-suffix _with_ptll_only_rw --missing-only -- --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/ --era ${era}
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DY_ptll.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_ptll.root

python3 histograms/derive_dy_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ --output-dir reweights/dy_njets_reweight/${era}/plots --output-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json --output-root reweights/dy_njets_reweight/${era}/dy_njets_reweight.root --dy-sample DY_ptll

sh histograms/scripts/hists.sh --datasets DY_amcatnlo,DY_amcatnlo_105_160 --era ${era}  --output-suffix _weighted --missing-only -- --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/ --era ${era}
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DY_weighted.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_weighted.root


###############################################################################
# Run3_2023BPix
###############################################################################

era=Run3_2023BPix

sh histograms/scripts/hists.sh --datasets DY_amcatnlo,TT,data,EWK,SingleH,DiTriBoson,SingleTop,TTX,W --era ${era}  --output-suffix _ptllNJetsRW --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW --missing-only -- --variables pt_mumu N_SelectedJets --categories ggF_0J ggF_1J ggF_ge2J VBF_ge2J --mass-regions Z_sideband
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW/ --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/ --era ${era}

sh histograms/scripts/hists.sh --datasets all --era ${era}  --missing-only
sh histograms/scripts/hists.sh --datasets all --era ${era}  --output-suffix _DNN --missing-only -- --variables DNN_NNOutput
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ --era ${era}

python3 histograms/derive_dy_ptll_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/ --output-dir reweights/dy_ptll_reweight/${era}/plots_smart --output-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --output-root reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.root --smart-rebin

sh histograms/scripts/hists.sh --datasets DY_amcatnlo,DY_amcatnlo_105_160 --era ${era}  --output-suffix _with_ptll_only_rw --missing-only -- --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/ --era ${era}
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DY_ptll.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_ptll.root

python3 histograms/derive_dy_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ --output-dir reweights/dy_njets_reweight/${era}/plots --output-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json --output-root reweights/dy_njets_reweight/${era}/dy_njets_reweight.root --dy-sample DY_ptll

sh histograms/scripts/hists.sh --datasets DY_amcatnlo,DY_amcatnlo_105_160 --era ${era}  --output-suffix _weighted --missing-only -- --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/ --era ${era}
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DY_weighted.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_weighted.root


###############################################################################
# Run3_2024
###############################################################################

era=Run3_2024

sh histograms/scripts/hists.sh --datasets DY_amcatnlo,TT,data,EWK,SingleH,DiTriBoson,SingleTop,TTX,W --era ${era}  --output-suffix _ptllNJetsRW --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW --missing-only -- --variables pt_mumu N_SelectedJets --categories ggF_0J ggF_1J ggF_ge2J VBF_ge2J --mass-regions Z_sideband
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW/ --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/ --era ${era}

sh histograms/scripts/hists.sh --datasets all --era ${era}  --missing-only
sh histograms/scripts/hists.sh --datasets all --era ${era}  --output-suffix _DNN --missing-only -- --variables DNN_NNOutput
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ --era ${era}

python3 histograms/derive_dy_ptll_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/ --output-dir reweights/dy_ptll_reweight/${era}/plots_smart --output-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --output-root reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.root --smart-rebin

sh histograms/scripts/hists.sh --datasets DY_amcatnlo,DY_amcatnlo_105_160,DY_amcatnlo_105_160_stitched,DY_amcatnlo_105_160_VBFFil --era ${era}  --output-suffix _with_ptll_only_rw --missing-only -- --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/ --era ${era}
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DY_ptll.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_ptll.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DYto2Mu_MLL105To160_VBFFiltered.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_VBFFiltered_ptll.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DYto2Mu_MLL105To160_FlashSim.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_FlashSim_ptll.root

python3 histograms/derive_dy_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ --output-dir reweights/dy_njets_reweight/${era}/plots --output-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json --output-root reweights/dy_njets_reweight/${era}/dy_njets_reweight.root --dy-sample DY_ptll

sh histograms/scripts/hists.sh --datasets DY_amcatnlo,DY_amcatnlo_105_160,DY_amcatnlo_105_160_stitched,DY_amcatnlo_105_160_VBFFil,DY_minnlo --era ${era}  --output-suffix _weighted --missing-only -- --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/ --era ${era}
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DY_weighted.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_weighted.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_MLL105To160_VBFFiltered.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_VBFFiltered_weighted.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_MLL105To160_FlashSim.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_FlashSim_weighted.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_minnlo.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_minnlo_weighted.root


###############################################################################
# Run3_2025
###############################################################################

era=Run3_2025

sh histograms/scripts/hists.sh --datasets DY_amcatnlo,TT,data,EWK,SingleH,DiTriBoson,SingleTop,TTX,W --era ${era}  --output-suffix _ptllNJetsRW --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW --missing-only -- --variables pt_mumu N_SelectedJets --categories ggF_0J ggF_1J ggF_ge2J VBF_ge2J --mass-regions Z_sideband
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW/ --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/ --era ${era}

sh histograms/scripts/hists.sh --datasets all --era ${era}  --missing-only
sh histograms/scripts/hists.sh --datasets all --era ${era}  --output-suffix _DNN --missing-only -- --variables DNN_NNOutput
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ --era ${era}

python3 histograms/derive_dy_ptll_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/ --output-dir reweights/dy_ptll_reweight/${era}/plots_smart --output-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --output-root reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.root --smart-rebin

sh histograms/scripts/hists.sh --datasets DY_amcatnlo,DY_amcatnlo_105_160,DY_amcatnlo_105_160_stitched,DY_amcatnlo_105_160_VBFFil --era ${era}  --output-suffix _with_ptll_only_rw --missing-only -- --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/ --era ${era}
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DY_ptll.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_ptll.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DYto2Mu_MLL105To160_VBFFiltered.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_VBFFiltered_ptll.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DYto2Mu_MLL105To160_FlashSim.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_FlashSim_ptll.root

python3 histograms/derive_dy_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ --output-dir reweights/dy_njets_reweight/${era}/plots --output-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json --output-root reweights/dy_njets_reweight/${era}/dy_njets_reweight.root --dy-sample DY_ptll

sh histograms/scripts/hists.sh --datasets DY_amcatnlo,DY_amcatnlo_105_160,DY_amcatnlo_105_160_stitched,DY_amcatnlo_105_160_VBFFil,DY_minnlo --era ${era}  --output-suffix _weighted --missing-only -- --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json
python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/ --era ${era}
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DY_weighted.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_weighted.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_MLL105To160_VBFFiltered.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_VBFFiltered_weighted.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_MLL105To160_FlashSim.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_MLL105To160_FlashSim_weighted.root
cp /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_minnlo.root /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/DYto2Mu_minnlo_weighted.root


###############################################################################
# Optional cleanup, written era by era.
###############################################################################

# era=Run3_2022; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded
# era=Run3_2022EE; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded
# era=Run3_2023; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded
# era=Run3_2023BPix; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded
# era=Run3_2024; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded
# era=Run3_2025; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded


###############################################################################
# Hadd Run3_2022_23, explicit sample by sample.
###############################################################################

mkdir -p /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded

hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/DY.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/DY_ptll.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/DY_ptll.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/DY_ptll.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/DY_ptll.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/DY_ptll.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/DY_weighted.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/DY_weighted.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/DY_weighted.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/DY_weighted.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/DY_weighted.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/DYto2Mu_MLL105To160.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/DYto2Mu_MLL105To160.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/DYto2Mu_MLL105To160_ptll.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/DYto2Mu_MLL105To160_ptll.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/DYto2Mu_MLL105To160_ptll.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/DYto2Mu_MLL105To160_ptll.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/DYto2Mu_MLL105To160_ptll.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/DYto2Mu_MLL105To160_weighted.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/DYto2Mu_MLL105To160_weighted.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/DYto2Mu_MLL105To160_weighted.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/DYto2Mu_MLL105To160_weighted.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/DYto2Mu_MLL105To160_weighted.root

hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/Data_Muon.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/Data_Muon.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/Data_Muon.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/Data_Muon.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/Data_Muon.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/TT.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/TT.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/TT.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/TT.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/TT.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/W_NJets.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/W_NJets.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/W_NJets.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/W_NJets.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/W_NJets.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/EWK.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/EWK.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/EWK.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/EWK.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/EWK.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/EWK_2Mu2J_MLL_105to160_herwig.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/EWK_2Mu2J_MLL_105to160_herwig.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/EWK_2Mu2J_MLL_105to160_herwig.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/EWK_2Mu2J_MLL_105to160_herwig.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/EWK_2Mu2J_MLL_105to160_herwig.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/EWK_2Mu2J_MLL_105to160_pythia.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/EWK_2Mu2J_MLL_105to160_pythia.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/EWK_2Mu2J_MLL_105to160_pythia.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/EWK_2Mu2J_MLL_105to160_pythia.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/EWK_2Mu2J_MLL_105to160_pythia.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/GluGluHto2Mu.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/GluGluHto2Mu.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/GluGluHto2Mu.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/GluGluHto2Mu.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/GluGluHto2Mu.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/GluGluHto2Mu_M120.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/GluGluHto2Mu_M120.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/GluGluHto2Mu_M120.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/GluGluHto2Mu_M120.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/GluGluHto2Mu_M120.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/GluGluHto2Mu_M130.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/GluGluHto2Mu_M130.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/GluGluHto2Mu_M130.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/GluGluHto2Mu_M130.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/GluGluHto2Mu_M130.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/GluGluHto2Mu_MiNNLO.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/GluGluHto2Mu_MiNNLO.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/GluGluHto2Mu_MiNNLO.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/GluGluHto2Mu_MiNNLO.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/GluGluHto2Mu_MiNNLO.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/GluGluHto2Mu_amcatnlo.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/GluGluHto2Mu_amcatnlo.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/GluGluHto2Mu_amcatnlo.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/GluGluHto2Mu_amcatnlo.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/GluGluHto2Mu_amcatnlo.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/GluGluHto2Mu_tuneDown.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/GluGluHto2Mu_tuneDown.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/GluGluHto2Mu_tuneDown.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/GluGluHto2Mu_tuneDown.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/GluGluHto2Mu_tuneDown.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/GluGluHto2Mu_tuneUp.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/GluGluHto2Mu_tuneUp.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/GluGluHto2Mu_tuneUp.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/GluGluHto2Mu_tuneUp.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/GluGluHto2Mu_tuneUp.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/H_mainBckg.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/H_mainBckg.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/H_mainBckg.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/H_mainBckg.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/H_mainBckg.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/ST.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/ST.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/ST.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/ST.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/ST.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/TW.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/TW.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/TW.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/TW.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/TW.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/TTX.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/TTX.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/TTX.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/TTX.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/TTX.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/VBFHto2Mu_M125_powheg.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/VBFHto2Mu_M125_powheg.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/VBFHto2Mu_M125_powheg.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/VBFHto2Mu_M125_powheg.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/VBFHto2Mu_M125_powheg.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/VBFHto2Mu_m125_tuneDown.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/VBFHto2Mu_m125_tuneDown.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/VBFHto2Mu_m125_tuneDown.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/VBFHto2Mu_m125_tuneDown.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/VBFHto2Mu_m125_tuneDown.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/VBFHto2Mu_m125_tuneUp.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/VBFHto2Mu_m125_tuneUp.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/VBFHto2Mu_m125_tuneUp.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/VBFHto2Mu_m125_tuneUp.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/VBFHto2Mu_m125_tuneUp.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/VH_inclusive.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/VH_inclusive.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/VH_inclusive.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/VH_inclusive.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/VH_inclusive.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/VHto2Mu.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/VHto2Mu.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/VHto2Mu.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/VHto2Mu.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/VHto2Mu.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/TTH_inclusive.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/TTH_inclusive.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/TTH_inclusive.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/TTH_inclusive.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/TTH_inclusive.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/TTHto2Mu.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/TTHto2Mu.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/TTHto2Mu.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/TTHto2Mu.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/TTHto2Mu.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/VV.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/VV.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/VV.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/VV.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/VV.root
hadd -f /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/VVV.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/VVV.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/VVV.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/VVV.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/VVV.root


###############################################################################
# Checks, era by era.
###############################################################################

era=Run3_2022; ls /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/
era=Run3_2022EE; ls /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/
era=Run3_2023; ls /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/
era=Run3_2023BPix; ls /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/
era=Run3_2024; ls /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/
era=Run3_2025; ls /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/
ls /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/


###############################################################################
# Plot examples with corrected special DY process names.
###############################################################################

python3 histograms/hist_plotter.py --era Run3_2022_23 --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/ --output plots_DYamcatnlo_weighted/ --region Signal_Fit_ggF --samples DYto2Mu_MLL105To160_weighted Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY --wantData --rebin
python3 histograms/hist_plotter.py --era Run3_2022_23 --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/ --output plots_DYamcatnlo_unweighted/ --region Signal_Fit_ggF --samples DYto2Mu_MLL105To160 Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY --wantData --rebin

python3 histograms/hist_plotter.py --era Run3_2024 --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2024_hadded/ --output plots_DYamcatnlo_weighted/ --region Signal_Fit_ggF --samples DYto2Mu_MLL105To160_VBFFiltered_weighted DYto2Mu_MLL105To160_weighted Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY --wantData --rebin
python3 histograms/hist_plotter.py --era Run3_2024 --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2024_hadded/ --output plots_DYamcatnlo_unweighted/ --region Signal_Fit_ggF --samples DYto2Mu_MLL105To160_VBFFiltered DYto2Mu_MLL105To160 Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY --wantData --rebin
python3 histograms/hist_plotter.py --era Run3_2024 --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2024_hadded/ --output plots_Flashsim_weighted/ --region Signal_Fit_ggF --samples DYto2Mu_MLL105To160_FlashSim_weighted Data_Muon EWK_2Mu2J_MLL_105to160_pythia_Flashsim GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_m125_Flashsim DiTriBoson W TT --wantLogY --wantData --rebin
python3 histograms/hist_plotter.py --era Run3_2024 --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2024_hadded/ --output plots_Flashsim_unweighted/ --region Signal_Fit_ggF --samples DYto2Mu_MLL105To160_FlashSim Data_Muon EWK_2Mu2J_MLL_105to160_pythia_Flashsim GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_m125_Flashsim DiTriBoson W TT --wantLogY --wantData --rebin

python3 histograms/hist_plotter.py --era Run3_2024 --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2024_hadded/ --output plots_DYminnlo_weighted/ --region mass_inclusive_ggF --samples DYto2Mu_minnlo_weighted Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY --wantData --rebin

python3 histograms/hist_plotter.py --era Run3_2025 --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2025_hadded/ --output plots_DYamcatnlo_weighted/ --region Signal_Fit_ggF --samples DYto2Mu_MLL105To160_VBFFiltered_weighted DYto2Mu_MLL105To160_weighted Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY --wantData --rebin
python3 histograms/hist_plotter.py --era Run3_2025 --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2025_hadded/ --output plots_DYamcatnlo_unweighted/ --region Signal_Fit_ggF --samples DYto2Mu_MLL105To160_VBFFiltered DYto2Mu_MLL105To160 Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY --wantData --rebin
python3 histograms/hist_plotter.py --era Run3_2025 --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2025_hadded/ --output plots_Flashsim_weighted/ --region Signal_Fit_ggF --samples DYto2Mu_MLL105To160_FlashSim_weighted Data_Muon EWK_2Mu2J_MLL_105to160_pythia_Flashsim GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_m125_Flashsim DiTriBoson W TT --wantLogY --wantData --rebin
python3 histograms/hist_plotter.py --era Run3_2025 --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2025_hadded/ --output plots_Flashsim_unweighted/ --region Signal_Fit_ggF --samples DYto2Mu_MLL105To160_FlashSim Data_Muon EWK_2Mu2J_MLL_105to160_pythia_Flashsim GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_m125_Flashsim DiTriBoson W TT --wantLogY --wantData --rebin

python3 histograms/hist_plotter.py --era Run3_2025 --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2025_hadded/ --output plots_DYminnlo_weighted/ --region mass_inclusive_ggF --samples DYto2Mu_minnlo_weighted Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W TT --wantLogY --wantData --rebin
