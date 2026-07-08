# Running Guide: Skim, Histograms, Hadd, Plots

This is the practical end-to-end running guide for the framework: local tests, skim campaigns, histogram campaigns, hadd, and plotting.

## Setup

Start from the repository root:

```bash
cd Hmm_newSkim
source env.sh
```

For EOS/XRootD access, make sure you have a valid CMS proxy:

```bash
voms-proxy-init --rfc --voms cms -valid 192:00
voms-proxy-info
```

Condor jobs source `env.sh` inside the worker executable, so the submit shell does not need to carry the full runtime environment.

## Main Scripts

### Skim: `analysis/skim.py`

Produces one skim ROOT file from one NanoAOD input file.

```bash
python3 analysis/skim.py \
  --era Run3_2024 \
  --dataset-name DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF \
  --input-file /eos/cms/store/mc/.../INPUT.root \
  --output-file /tmp/vdamante/test_skim.root \
  --want-variations
```

Required options:

```text
--era
--dataset-name
--input-file
--output-file
```

Use `--want-variations` for MC systematic variations. It has no effect for data.

### Histograms: `histograms/hist_maker.py`

Produces one histogram ROOT file from a skim directory or a skim ROOT file.

```bash
python3 histograms/hist_maker.py \
  --era Run3_2024 \
  --dataset-name DYto2Mu_M_50_amcatnloFXFX \
  --input /eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v2_noUnc/Run3_2024/DYto2Mu_M_50_amcatnloFXFX/ \
  --output-file /tmp/vdamante/DYto2Mu_M_50_amcatnloFXFX.root \
  --variables DNN_NNOutput \
  --mass-regions Z_sideband \
  --categories baseline ggF VBF \
  --skip-file-validation
```

Required options:

```text
--era
--dataset-name
--input
--output-file
```

Common options:

```text
--variables VAR [VAR ...]
--mass-regions REGION [REGION ...]
--categories CATEGORY [CATEGORY ...]
--systematics central|all
--chunk-size N
--n-cores N
--skip-file-validation
--additional-cuts "CUT"
--shift-z-sideband-dnn-mass
```

Defaults:

```text
--systematics central
--chunk-size 6
--n-cores 4
--mass-regions mass_inclusive Z_sideband Signal_Fit
--categories baseline ggF VBF
```

### Plotting: `histograms/hist_plotter.py`

Reads hadded ROOT files and makes plots.

```bash
python3 histograms/hist_plotter.py \
  --era Run3_2024 \
  --input /eos/user/v/vdamante/H_mumu/newHists_Run3_2024_hadded/ \
  --output plots_DYamcatnlo/ \
  --region Z_sideband_ggF \
  --samples Data_Muon DY_amcatnlo EWK SingleTop TTX W DiTriBoson GluGluHto2Mu VBFHto2Mu_M125_powheg \
  --vars m_mumu,DNN_NNOutput \
  --wantData \
  --wantLogY \
  --rebin
```

Useful options:

```text
--region REGION_CATEGORY
--samples SAMPLE_OR_GROUP [SAMPLE_OR_GROUP ...]
--vars VAR1,VAR2
--wantData
--wantLogY
--rebin
--systematics
--no-stack
--no-fill-hists
--ratio-reference SAMPLE_OR_GROUP
--normalize-dy-to-data
--normalize-mc-to-data
```

`--samples` can be ROOT filenames without `.root`, process names from `config/<ERA>/process_names.yaml`, or groups from `config/plot/process_groups.yaml`.

## Skim Campaigns

Check missing skim outputs:

```bash
python3 htcondor/check_missing_files.py -e Run3_2024 --only-missing
```

Dry-run skim submission:

```bash
python3 htcondor/condorsubmit.py -e Run3_2024 --no-submit
```

Submit one era:

```bash
python3 htcondor/condorsubmit.py \
  -e Run3_2024 \
  --max-parallel-jobs 5000 \
  --poll-interval 120
```

Main skim outputs:

```text
/eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v2_noUnc/<ERA>/<DATASET>/
```

## Histogram Campaigns

The preferred histogram Condor submitter is:

```bash
python3 htcondor/hist_condorsubmit.py
```

Submit one era and one group:

```bash
python3 htcondor/hist_condorsubmit.py \
  --eras Run3_2024 \
  --datasets DY_amcatnlo \
  --condor \
  --submit-missing \
  --max-parallel-jobs 5000 \
  -- --skip-file-validation
```

Submit one explicit dataset:

```bash
python3 htcondor/hist_condorsubmit.py \
  --eras Run3_2024 \
  --dataset-name TTto2L2Nu \
  --chunk-size 10 \
  --condor \
  --submit-missing \
  -- --skip-file-validation
```

Pass `hist_maker.py` options after a standalone `--`:

```bash
python3 htcondor/hist_condorsubmit.py \
  --eras Run3_2024 \
  --datasets signals \
  --condor \
  --dry-run \
  -- \
  --variables DNN_NNOutput \
  --mass-regions Z_sideband \
  --categories ggF_0J ggF_1J ggF_ge2J VBF_ge2J \
  --skip-file-validation
```

Do not use `--hist_opts`; it is not a parser option. Also make sure line-continuation backslashes have no trailing spaces.

Submit every input-file chunk as an independent Condor job and run `hadd`
automatically after all chunks of a dataset succeed:

```bash
python3 htcondor/hist_condorsubmit.py \
  --eras Run3_2022,Run3_2022EE,Run3_2023,Run3_2023BPix,Run3_2024 \
  --datasets DY_amcatnlo,DY_amcatnlo_105_160 \
  --output-suffix _with_ptll_only_rw \
  --input-folder skim_v2_noUnc \
  --chunks-as-jobs \
  --split-variable-groups \
  --missing-only \
  -- \
  --dy-ptll-reweight-json 'reweights/dy_ptll_reweight/{era}/dy_ptll_reweight_smart.json'
```

`{era}` and `{ERA}` in forwarded histogram options are expanded separately for
each era.

With `--split-variable-groups`, each input chunk is processed independently for
logical groups such as muons, dimuon, jets, dijets, soft activity, and DNN.
All chunk/group outputs are merged into the usual single dataset ROOT file.

Common groups:

```text
data
DiTriBoson
DY_amcatnlo
DY_amcatnlo_105_160
DY_amcatnlo_105_160_stitched
DY_amcatnlo_105_160_VBFFil
DY_minnlo
EWK
signals
other_signals
SingleH
SingleTop
TTX
W
```

Histogram outputs:

```text
/eos/user/v/vdamante/H_mumu/newHists_<ERA><SUFFIX>/
```

## Hadd

Merge per-dataset histograms into physics-process files:

```bash
era=Run3_2024

python3 histograms/hadd_hists_to_processes.py \
  --input-dir /eos/user/v/vdamante/H_mumu/newHists_${era}/ \
  --output-dir /eos/user/v/vdamante/H_mumu/newHists_${era}_hadded/ \
  --era ${era}
```

Dry-run:

```bash
python3 histograms/hadd_hists_to_processes.py \
  --input-dir /eos/user/v/vdamante/H_mumu/newHists_Run3_2024/ \
  --output-dir /eos/user/v/vdamante/H_mumu/newHists_Run3_2024_hadded/ \
  --era Run3_2024 \
  --dryRun
```

## DY MLL 105-160 Special Outputs

For 2024, 2025, and 2026:

```text
DY_amcatnlo_105_160           -> nonStitched outputs
DY_amcatnlo_105_160_stitched  -> GenVBFFilter==0, suffix _stitched
DY_amcatnlo_105_160_VBFFil    -> GenVBFFilter==1, suffix _stitched
```

Produce the pieces:

```bash
python3 htcondor/hist_condorsubmit.py \
  --eras Run3_2024 \
  --datasets DY_amcatnlo_105_160,DY_amcatnlo_105_160_stitched,DY_amcatnlo_105_160_VBFFil \
  --condor \
  --submit-missing \
  --max-parallel-jobs 5000 \
  --output-suffix TT \
  -- --skip-file-validation
```

Copy special files into the hadded directory with plotter-friendly names:

```bash
era=Run3_2024
suffix=TT
input_dir=/eos/user/v/vdamante/H_mumu/newHists_${era}${suffix}
hadded_dir=/eos/user/v/vdamante/H_mumu/newHists_${era}${suffix}_hadded

cp ${input_dir}/DYto2Mu_MLL_105to160_amcatnloFXFX_stitched.root \
   ${hadded_dir}/DYto2Mu_MLL105To160.root

cp ${input_dir}/DYto2Mu_MLL_105to160_amcatnloFXFX_nonStitched.root \
   ${hadded_dir}/DYto2Mu_MLL105To160_nonStitched.root

cp ${input_dir}/DYto2Mu_MLL_105to160_amcatnloFXFX_Flashsim_nonStitched.root \
   ${hadded_dir}/DYto2Mu_MLL105To160_Flashsim.root

cp ${input_dir}/DYto2Mu_MLL_105to160_amcatnloFXFX_Fil_VBF_stitched.root \
   ${hadded_dir}/DYto2Mu_MLL105To160_VBFFiltered.root
```

## Useful Recipes

Z-sideband shifted DNN:

```bash
python3 htcondor/hist_condorsubmit.py \
  --eras Run3_2022EE \
  --datasets signals \
  --condor \
  --submit-missing \
  --output-suffix _ZSideband_mass_shifted \
  -- \
  --variables DNN_NNOutput \
  --mass-regions Z_sideband \
  --shift-z-sideband-dnn-mass \
  --skip-file-validation
```

Low-pT/TT categories:

```bash
python3 htcondor/hist_condorsubmit.py \
  --eras Run3_2024 \
  --datasets signals \
  --condor \
  --submit-missing \
  --output-suffix TT \
  -- \
  --categories baseline_lowPtTT ggF_lowPtTT VBF_lowPtTT \
  --variables DNN_NNOutput m_mumu pt_mumu eta_mumu \
  --skip-file-validation
```

Local DNN smoke test:

```bash
dataset_name=GluGluHto2Mu

python3 histograms/hist_maker.py \
  --era Run3_2022 \
  --dataset-name ${dataset_name} \
  --input /eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v2_noUnc/Run3_2022/${dataset_name}/ \
  --output-file prova_DNN_NNOutput_${dataset_name}.root \
  --variables DNN_NNOutput \
  --skip-file-validation
```

## Debug

```bash
condor_q
condor_q -hold
ls htcondor/hists/
ls /eos/user/v/vdamante/H_mumu/newHists_Run3_2024/
ls /eos/user/v/vdamante/H_mumu/newHists_Run3_2024_hadded/
```

If the plotter cannot find a sample, check the exact ROOT filename in the hadded directory and pass that name without `.root`.
