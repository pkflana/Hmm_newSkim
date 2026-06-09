era=$1
input_folder=${2:-"skim_v1_noUnc"}

for dataset_name in TWminusto2L2Nu TWminusto4Q TWminustoLNu2Q TbarWplusto2L2Nu TbarWplusto4Q TbarWplustoLNu2Q TBbarQto2Q_t_channel_4FS TBbarQtoLNu_t_channel_4FS TBbartoLplusNuBbar_s_channel_4FS TbarBQto2Q_t_channel_4FS TbarBQtoLNu_t_channel_4FS TbarBtoLminusNuB_s_channel_4FS; do
    python3 histograms/hist_maker.py --era ${era} --dataset ${dataset_name} --input /eos/cms/store/group/phys_higgs/cmshmm/vdamante/${input_folder}/${era}/${dataset_name}/ --output-file /eos/user/v/vdamante/H_mumu/newHists_${era}/${dataset_name}.root ;
    done


