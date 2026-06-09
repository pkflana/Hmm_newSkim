era=$1
input_folder=${2:-"skim_v1_noUnc"}

for dataset_name in EWK_2L2J_madgraph_herwig EWK_2Mu2J_MLL_105to160_herwig EWK_2Mu2J_MLL_105to160_pythia EWK_2Mu2J_MLL_105to160_pythia_Flashsim; do
    python3 histograms/hist_maker.py --era ${era} --dataset ${dataset_name} --input /eos/cms/store/group/phys_higgs/cmshmm/vdamante/${input_folder}/${era}/${dataset_name}/ --output-file /eos/user/v/vdamante/H_mumu/newHists_${era}/${dataset_name}.root ;
    done
