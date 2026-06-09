era=$1
input_folder=${2:-"skim_v1_noUnc"}

for dataset_name in TTH_Hto2Mu TTHto2B_M125 TTHtoNon2B_M125 TTWH TTWW TTZH_ZHto4B TTZ_Zto2Q TTto2L2Nu TTto4Q TTtoLNu2Q; do
    python3 histograms/hist_maker.py --era ${era} --dataset ${dataset_name} --input /eos/cms/store/group/phys_higgs/cmshmm/vdamante/${input_folder}/${era}/${dataset_name}/ --output-file /eos/user/v/vdamante/H_mumu/newHists_${era}/${dataset_name}.root --resume ;
    done


