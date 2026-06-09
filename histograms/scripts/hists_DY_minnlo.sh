era=$1
input_folder=${2:-"skim_v1_noUnc"}

for dataset_name in DYto2Mu_MLL_1000to1500_powheg_minnlo DYto2Mu_MLL_130to200_powheg_minnlo DYto2Mu_MLL_1500to2000_powheg_minnlo DYto2Mu_MLL_2000to4000_powheg_minnlo DYto2Mu_MLL_200to400_powheg_minnlo DYto2Mu_MLL_4000to6000_powheg_minnlo DYto2Mu_MLL_400to600_powheg_minnlo DYto2Mu_MLL_50to130_powheg_minnlo DYto2Mu_MLL_6000to13600_powheg_minnlo DYto2Mu_MLL_600to800_powheg_minnlo ; do
    python3 histograms/hist_maker.py --era ${era} --dataset ${dataset_name} --input /eos/cms/store/group/phys_higgs/cmshmm/vdamante/${input_folder}/${era}/${dataset_name}/ --output-file /eos/user/v/vdamante/H_mumu/newHists_${era}/${dataset_name}.root ;
    done
