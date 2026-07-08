
python3 analysis/skim.py --era Run3_2025 --dataset-name VBFHto2Mu_M125_amcatnlo --input-file /eos/cms/store/mc/RunIII2024Summer24NanoAODv15/VBF-Hto2Mu_Par-M-125_TuneCP5_13p6TeV_amcatnlo-pythia8/NANOAODSIM/150X_mcRun3_2024_realistic_v2-v2/2560000/003ede9b-bb5c-485e-9080-e73badd1530a.root --output-file test_skim_Run3_2025_VBF.root
--want-variations


python3 analysis/skim.py  --era Run3_2025  --dataset-name Muon0_Run2025C_v2  --input-file root://cms-xrd-global.cern.ch//store/data/Run2025C/Muon0/NANOAOD/PromptReco-v2/000/393/461/00000/9b293a67-d80f-40e3-a4d3-dd1348ed082b.root  --output-file test_skim_Run3_2025_data.root

source env.sh

python3 histograms/hist_maker.py \
  --era Run3_2024 \
  --dataset-name VBFHto2Mu_M125_powheg \
  --input example_skimTuple_VBF.root \
  --output-file /tmp/vdamante/hists_VBF_2024_allSyst.root \
  --systematics all \
  --mass-regions mass_inclusive Z_sideband Signal_Fit \
  --categories baseline ggF VBF \
  --chunk-size 1 \
  --n-cores 1 \
  --skip-file-validation




python3 histograms/hist_maker.py \
  --era Run3_2024 \
  --dataset-name VBFHto2Mu_M125_powheg \
  --input example_skimTuple_VBF.root \
  --output-file /tmp/vdamante/hists_VBF_2024_allSyst.root \
  --systematics jec-jer \
  --mass-regions mass_inclusive Z_sideband Signal_Fit \
  --categories baseline ggF VBF \
  --chunk-size 1 \
  --n-cores 1 \
  --skip-file-validation

  source env.sh

python3 histograms/hist_maker.py \
  --era Run3_2024 \
  --dataset-name VBFHto2Mu_M125_powheg \
  --input example_skimTuple_VBF.root \
  --output-file hists_VBF_2024_allSyst.root \
  --systematics all \
  --mass-regions mass_inclusive Z_sideband Signal_Fit \
  --categories baseline ggF VBF \
  --chunk-size 1 \
  --n-cores 1 \
  --skip-file-validation



  source env.sh

python3 analysis/skim.py \
  --era Run3_2024 \
  --dataset-name VBFHto2Mu_M125_powheg \
  --input-file INPUT_NANOAOD.root \
  --output-file /tmp/vdamante/qcd_test_skim.root \
  --want-variations

python3 analysis/skim.py --era Run3_2024 --dataset-name VBFHto2Mu_M125_amcatnlo --input-file /eos/cms/store/mc/RunIII2024Summer24NanoAODv15/VBF-Hto2Mu_Par-M-125_TuneCP5_13p6TeV_amcatnlo-pythia8/NANOAODSIM/150X_mcRun3_2024_realistic_v2-v2/2560000/003ede9b-bb5c-485e-9080-e73badd1530a.root --output-file test_skim_Run3_2024_VBF.root --want-variations

jq '.qcd_scale__muR0p5_muF0p5,
    .qcd_scale__muR0p5_muF1,
    .qcd_scale__muR1_muF0p5,
    .qcd_scale__muR1_muF2,
    .qcd_scale__muR2_muF1,
    .qcd_scale__muR2_muF2' \
  test_skim_Run3_2024_VBF_report.json

python3 histograms/hist_maker.py \
  --era Run3_2024 \
  --dataset-name VBFHto2Mu_M125_powheg \
  --input test_skim_Run3_2024_VBF.root \
  --output-file qcd_test_hists.root \
  --variables m_mumu \
  --systematics all \
  --chunk-size 1 \
  --n-cores 1