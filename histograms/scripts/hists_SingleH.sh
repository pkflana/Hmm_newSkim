era=$1
input_folder=${2:-"skim_v1_noUnc"}

for dataset_name in GluGluHto2B_M125 GluGluHto2Tau_UncorrelatedDecay_UnFiltered GluGluHto2Wto2L2Nu_M125   VBFHto2B_M125 VBFHto2Tau_UncorrelatedDecay_UnFiltered VBFHto2Wto2L2Nu_M125 ggZH_Hto2B_Zto2L ggZH_Hto2B_Zto2Q ggZH_Hto2Mu_ZtoAll_M125 ZH_Hto2B_Zto2L ZH_Hto2B_Zto2Q ZH_Hto2Mu WminusH_Hto2B_WtoLNu WminusH_Hto2Mu WminusHto2Tau_UncorrelatedDecay_UnFiltered WplusH_Hto2B_WtoLNu WplusH_Hto2Mu WplusHto2Tau_UncorrelatedDecay_UnFiltered; do
    python3 histograms/hist_maker.py --era ${era} --dataset ${dataset_name} --input /eos/cms/store/group/phys_higgs/cmshmm/vdamante/${input_folder}/${era}/${dataset_name}/ --output-file /eos/user/v/vdamante/H_mumu/newHists_${era}/${dataset_name}.root --chunk-size 15;
    done


