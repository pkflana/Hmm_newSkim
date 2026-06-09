era=$1
input_folder=${2:-"skim_v1_noUnc"}

for dataset_name in GluGluHto2Mu GluGluHto2Mu_M120 GluGluHto2Mu_M130 GluGluHto2Mu_MiNNLO GluGluHto2Mu_amcatnlo GluGluHto2Mu_tuneDown GluGluHto2Mu_tuneUp ; do
    python3 histograms/hist_maker.py --era ${era} --dataset ${dataset_name} --input /eos/cms/store/group/phys_higgs/cmshmm/vdamante/${input_folder}/${era}/${dataset_name}/ --output-file /eos/user/v/vdamante/H_mumu/newHists_${era}/${dataset_name}.root --skip-failed-chunks ;
    done


for dataset_name in VBFHto2Mu_M120 VBFHto2Mu_M125_amcatnlo VBFHto2Mu_M125_powheg VBFHto2Mu_M130 VBFHto2Mu_m125_Flashsim VBFHto2Mu_m125_tuneCP5Down_amcatnlo VBFHto2Mu_m125_tuneCP5Up_amcatnlo ; do
    python3 histograms/hist_maker.py --era ${era} --dataset ${dataset_name} --input /eos/cms/store/group/phys_higgs/cmshmm/vdamante/${input_folder}/${era}/${dataset_name}/ --output-file /eos/user/v/vdamante/H_mumu/newHists_${era}/${dataset_name}.root --skip-failed-chunks;
    done


