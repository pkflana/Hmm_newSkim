era=$1
input_folder=${2:-"skim_v1_noUnc"}

for dataset_name in  WW WWW_4F WWZ_4F WWto2L2Nu_powheg WWto4Q_powheg WWtoLNu2Q_powheg WZ WZZ WZto2L2Q_powheg WZto3LNu_powheg WZtoLNu2Q_powheg  ZZ ZZZ ZZto2L2Nu_powheg ZZto2L2Q_powheg ZZto2Nu2Q_powheg ZZto4L_powheg  ; do
    python3 histograms/hist_maker.py --era ${era} --dataset ${dataset_name} --input /eos/cms/store/group/phys_higgs/cmshmm/vdamante/${input_folder}/${era}/${dataset_name}/ --output-file /eos/user/v/vdamante/H_mumu/newHists_${era}/${dataset_name}.root ;
    done


