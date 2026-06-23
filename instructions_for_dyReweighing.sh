#### before anything:
###### for the pt(Z) reweighing ######

sh histograms/scripts/hists.sh --datasets DY_amcatnlo --era Run3_2022 --input-folder skim_v2_noUnc --output-suffix _ptllNJetsRW --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_Run3_2022_ptllNJetsRW -- --variables pt_mumu N_SelectedJets --categories ggF_0J ggF_1J ggF_ge2J VBF_ge2J --mass-regions Z_sideband
sh histograms/scripts/hists.sh --datasets TT --era Run3_2022 --input-folder skim_v2_noUnc --output-suffix _ptllNJetsRW --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_Run3_2022_ptllNJetsRW -- --variables pt_mumu N_SelectedJets --categories ggF_0J ggF_1J ggF_ge2J VBF_ge2J --mass-regions Z_sideband
sh histograms/scripts/hists.sh --datasets data --era Run3_2022 --input-folder skim_v2_noUnc --output-suffix _ptllNJetsRW --output-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_Run3_2022_ptllNJetsRW -- --variables pt_mumu N_SelectedJets --categories ggF_0J ggF_1J ggF_ge2J VBF_ge2J --mass-regions Z_sideband



### non reweighted histos #####

sh histograms/scripts/hists.sh  --datasets DY_amcatnlo  --era Run3_2022 --input-folder skim_v2_noUnc/ --output-suffix _v2Skim
sh histograms/scripts/hists.sh  --datasets TT  --era Run3_2022 --input-folder skim_v2_noUnc/ --output-suffix _v2Skim x
sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160  --era Run3_2022 --input-folder skim_v2_noUnc/ --output-suffix _v2Skim
sh histograms/scripts/hists.sh  --datasets data  --era Run3_2022 --input-folder skim_v2_noUnc/ --output-suffix _v2Skim



### non reweighted histos -- DNN NN Output #####

sh histograms/scripts/hists.sh  --datasets DY_amcatnlo  --era Run3_2022 --input-folder skim_v2_noUnc/ --output-suffix _v2Skim_DNN -- --variables DNN_NNOutput
sh histograms/scripts/hists.sh  --datasets TT  --era Run3_2022 --input-folder skim_v2_noUnc/ --output-suffix _v2Skim_DNN -- --variables DNN_NNOutput
sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160  --era Run3_2022 --input-folder skim_v2_noUnc/ --output-suffix _v2Skim_DNN -- --variables DNN_NNOutput
sh histograms/scripts/hists.sh  --datasets data  --era Run3_2022 --input-folder skim_v2_noUnc/ --output-suffix _v2Skim_DNN -- --variables DNN_NNOutput





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
  W
  other_signals


####### after
era=Run3_2022; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/ --era ${era}
era=Run3_2022EE; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/ --era ${era}
era=Run3_2023; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/ --era ${era}
era=Run3_2023BPix; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/ --era ${era}
era=Run3_2024; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/ --era ${era}


era=Run3_2022; cp /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root
era=Run3_2022EE; cp /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root
era=Run3_2023; cp /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root
era=Run3_2023BPix; cp /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root


### derive pt(ll) reweighting from special hists
Run3_2024
for era in Run3_2022 Run3_2022EE Run3_2023 Run3_2023BPix ; do python3 histograms/derive_dy_ptll_njets_reweight.py  --era ${era}  --input-dir /eos/user/v/vdamante/H_mumu/reweighting_hists/newHists_${era}_ptllNJetsRW_hadded/  --output-dir reweights/dy_ptll_reweight/${era}/plots_smart  --output-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json  --output-root reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.root  --smart-rebin; done

### redo only DY amcatnlo inclusive hists with pt(ll)
era=Run3_2022; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo  --era ${era} --input-folder skim_v2_noUnc --output-suffix _with_ptll_only_rw  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
era=Run3_2022EE; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo  --era ${era} --input-folder skim_v2_noUnc --output-suffix _with_ptll_only_rw  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
era=Run3_2023; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo  --era ${era} --input-folder skim_v2_noUnc --output-suffix _with_ptll_only_rw  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
era=Run3_2023BPix; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo  --era ${era} --input-folder skim_v2_noUnc --output-suffix _with_ptll_only_rw  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
era=Run3_2024; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo  --era ${era} --input-folder skim_v2_noUnc --output-suffix _with_ptll_only_rw  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json


era=Run3_2022; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160  --era ${era} --input-folder skim_v2_noUnc --output-suffix _with_ptll_only_rw  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
era=Run3_2022EE; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160  --era ${era} --input-folder skim_v2_noUnc --output-suffix _with_ptll_only_rw  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
era=Run3_2023; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160  --era ${era} --input-folder skim_v2_noUnc --output-suffix _with_ptll_only_rw  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
era=Run3_2023BPix; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160  --era ${era} --input-folder skim_v2_noUnc --output-suffix _with_ptll_only_rw  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json
era=Run3_2024; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160  --era ${era} --input-folder skim_v2_noUnc --output-suffix _with_ptll_only_rw  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json

### hadd these intermediate histograms
era=Run3_2022; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/ --era ${era}
era=Run3_2022EE; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/ --era ${era}
era=Run3_2023; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/ --era ${era}
era=Run3_2023BPix; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/ --era ${era}
era=Run3_2024; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/ --era ${era}

### move these intermediate histograms in the hadded folder in the name DY_ptll.root

era=Run3_2022; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DY_ptll.root
era=Run3_2022EE; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DY_ptll.root
era=Run3_2023; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DY_ptll.root
era=Run3_2023BPix; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DY_ptll.root
era=Run3_2024; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DY_ptll.root

era=Run3_2022; cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched_ptll.root
era=Run3_2022EE; cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched_ptll.root
era=Run3_2023; cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched_ptll.root
era=Run3_2023BPix; cp /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched_ptll.root




### clean --> remove these intermediate folders
era=Run3_2022; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw*
era=Run3_2022EE; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw*
era=Run3_2023; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw*
era=Run3_2023BPix; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw*
era=Run3_2024; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_with_ptll_only_rw*

### derive NJets reweighing
era=Run3_2022; python3 histograms/derive_dy_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/ --output-dir reweights/dy_njets_reweight/${era}/plots --output-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json --output-root reweights/dy_njets_reweight/${era}/dy_njets_reweight.root --dy-sample DY_ptll

era=Run3_2022EE; python3 histograms/derive_dy_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/ --output-dir reweights/dy_njets_reweight/${era}/plots --output-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json --output-root reweights/dy_njets_reweight/${era}/dy_njets_reweight.root --dy-sample DY_ptll

era=Run3_2023; python3 histograms/derive_dy_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/ --output-dir reweights/dy_njets_reweight/${era}/plots --output-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json --output-root reweights/dy_njets_reweight/${era}/dy_njets_reweight.root --dy-sample DY_ptll

era=Run3_2023BPix; python3 histograms/derive_dy_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/ --output-dir reweights/dy_njets_reweight/${era}/plots --output-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json --output-root reweights/dy_njets_reweight/${era}/dy_njets_reweight.root --dy-sample DY_ptll

era=Run3_2024; python3 histograms/derive_dy_njets_reweight.py --era ${era} --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/ --output-dir reweights/dy_njets_reweight/${era}/plots --output-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json --output-root reweights/dy_njets_reweight/${era}/dy_njets_reweight.root --dy-sample DY_ptll



### derive all DY contributions histograms with both reweighting applied

era=Run3_2022 ; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo  --era ${era}  --output-suffix _weighted  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json

era=Run3_2022; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160  --era ${era}  --output-suffix _weighted  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json


era=Run3_2022EE ; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160,DY_amcatnlo  --era ${era}  --output-suffix _weighted  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json

era=Run3_2023 ; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160,DY_amcatnlo  --era ${era}  --output-suffix _weighted  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json

era=Run3_2023BPix ; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160,DY_amcatnlo  --era ${era}  --output-suffix _weighted  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json



era=Run3_2024 ; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo  --era ${era}  --output-suffix _weighted  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json

era=Run3_2024; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160  --era ${era}  --output-suffix _weighted  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json

era=Run3_2024; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160_stitched  --era ${era}  --output-suffix _weighted  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json

era=Run3_2024; sh histograms/scripts/hists.sh  --datasets DY_amcatnlo_105_160_VBFFil  --era ${era}  --output-suffix _weighted  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.json

era=Run3_2024; sh histograms/scripts/hists.sh  --datasets DY_minnlo  --era ${era}  --output-suffix _weighted  --  --dy-ptll-reweight-json reweights/dy_ptll_reweight/${era}/dy_ptll_reweight_smart.json --dy-njets-reweight-json reweights/dy_njets_reweight/${era}/dy_njets_reweight.jsonls


### hadd these intermediate histograms
era=Run3_2022; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/ --era ${era}
era=Run3_2022EE; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/ --era ${era}
era=Run3_2023; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/ --era ${era}
era=Run3_2023BPix; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/ --era ${era}
era=Run3_2024; python3 histograms/hadd_hists_to_processes.py --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/ --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/ --era ${era}

### move these intermediate histograms in the hadded folder in the name DY_*_weighted.root

era=Run3_2022; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_MLL_105to160_weighted.root
era=Run3_2022; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DY_weighted.root

era=Run3_2022EE; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_MLL_105to160_weighted.root
era=Run3_2022EE; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DY_weighted.root


era=Run3_2023; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_MLL_105to160_weighted.root
era=Run3_2023; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DY_weighted.root



era=Run3_2023BPix; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_MLL_105to160_weighted.root
era=Run3_2023BPix; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DY_weighted.root



for sample in DYto2Mu_MLL_105to160_amcatnloFXFX_stitched DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF_nonStitched DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF_stitched DYto2Mu_MLL_105to160_amcatnloFXFX_Flashsim_nonStitched DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched ; do mv /eos/user/v/vdamante/H_mumu/newHists_Run3_2024_weighted/${sample}.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2024_hadded/${sample}_weighted.root ; done

era=Run3_2024; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DYto2Mu_minnlo.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DYto2Mu_minnlo_weighted.root
era=Run3_2024; mv /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded/DY.root /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/DY_weighted.root

# remove intermediate folders
era=Run3_2022; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted
era=Run3_2022; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded
era=Run3_2022EE; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted
era=Run3_2022EE; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded
era=Run3_2023; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted
era=Run3_2023; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded
era=Run3_2023BPix; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted
era=Run3_2023BPix; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded

era=Run3_2024; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted
era=Run3_2024; rm -rf /eos/user/v/vdamante/H_mumu/newHists_${era}_weighted_hadded

# check that everything is there

era=Run3_2022; ls /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/
era=Run3_2022EE; ls /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/
era=Run3_2023; ls /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/
era=Run3_2023BPix; ls /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/
era=Run3_2024; ls /eos/user/v/vdamante/H_mumu/newHists_${era}_v2Skim_hadded/

### hadd 22_23:

for sample in  DY EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu_tuneDown TTX VV DY_ptll EWK_2Mu2J_MLL_105to160_pythia GluGluHto2Mu_tuneUp TW VVV DY_weighted GluGluHto2Mu H_mainBckg VBFHto2Mu_M125_powheg W_NJets DYto2Mu_MLL105To160 GluGluHto2Mu_M120 ST VBFHto2Mu_m125_tuneDown DYto2Mu_MLL_105to160_weighted GluGluHto2Mu_M130 TT VBFHto2Mu_m125_tuneUp Data_Muon GluGluHto2Mu_MiNNLO TTH_inclusive VH_inclusive EWK GluGluHto2Mu_amcatnlo TTHto2Mu VHto2Mu ; do hadd /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_23_hadded/${sample}.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022_hadded/${sample}.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2022EE_hadded/${sample}.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023_hadded/${sample}.root /eos/user/v/vdamante/H_mumu/newHists_Run3_2023BPix_hadded/${sample}.root; done

### plot without weights
## Z sideband and mass inclusive


for region in Z_sideband mass_inclusive;
    do for era in 2024
        do for category in ggF VBF baseline;
            do
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_DYamcatnlo_weighted/  --region "${region}_${category}"  --samples DY_weighted Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin ;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_DYamcatnlo_unweighted/  --region "${region}_${category}"  --samples DY Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin ;
        done
    done
done

## 2024 has also minnlo
for region in Z_sideband mass_inclusive;
    do for era in 2024
        do for category in ggF VBF baseline;
            do
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_DYminnlo_weighted/  --region "${region}_${category}"  --samples DYto2Mu_minnlo_weighted Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin ;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_DYminnlo_unweighted/  --region "${region}_${category}"  --samples DY_minnlo Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin ;
        done
    done
done





## signal

for region in Signal_Fit;
    do for era in 2022_23
        do for category in ggF VBF baseline;
            do
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_DYamcatnlo_weighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL_105to160_weighted Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin ;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_DYamcatnlo_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL105To160 Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin ;
        done
    done
done
# 2024 has the stitching and flashsim samples
for region in Signal_Fit;
    do for era in 2024
        do for category in ggF VBF baseline;
            do
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_DYamcatnlo_weighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF_stitched_weighted DYto2Mu_MLL_105to160_amcatnloFXFX_stitched_weighted Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin ;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_DYamcatnlo_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF_stitched DYto2Mu_MLL_105to160_amcatnloFXFX_stitched Data_Muon EWK_2Mu2J_MLL_105to160_herwig GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg  DiTriBoson W TT --wantLogY  --wantData  --rebin ;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_Flashsim_weighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL_105to160_amcatnloFXFX_Flashsim_nonStitched_weighted Data_Muon EWK_2Mu2J_MLL_105to160_pythia_Flashsim GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_m125_Flashsim  DiTriBoson W TT --wantLogY  --wantData  --rebin ;
            python3 histograms/hist_plotter.py  --era Run3_${era}  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_${era}_hadded/  --output plots_Flashsim_unweighted/  --region "${region}_${category}"  --samples DYto2Mu_MLL_105to160_amcatnloFXFX_Flashsim_nonStitched Data_Muon EWK_2Mu2J_MLL_105to160_pythia_Flashsim GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_m125_Flashsim  DiTriBoson W TT --wantLogY  --wantData  --rebin ;

        done
    done
done

