# Run 3 Histogram Campaign Workflow

For a shorter student-oriented guide covering only `DNN_NNOutput`, see
[DNN Output Quick Start](DNN_OUTPUT_QUICKSTART.md).

This guide describes the complete workflow for two reusable Run 3 histogram
campaigns:

1. `DNN_VBFEta`: `DNN_NNOutput` only.
2. `InputFeatures_VBFEta`: the default observables configured in each era's
   `maincfg.yaml`.

Both campaigns cover:

- all Run 3 eras;
- separate Central and shifted-systematic production;
- `Z_sideband`, `H_sideband`, and `Signal_Fit`;
- nested VBF jet-eta regions `incl`, `CC`, `CF`, and `FF`;
- per-dataset to per-process hadd;
- systematic merging;
- combined 2022–2023 output;
- plotting.

The VBF jet-eta regions are defined as:

```text
C:    |eta(jet)| < 2.5
F:    |eta(jet)| >= 2.5
CC:   both VBF jets are central
CF:   exactly one VBF jet is central and one is forward
FF:   both VBF jets are forward
incl: no additional jet-eta requirement
```

`CF` is unordered, so it also includes the configuration sometimes called
`FC`.

## 1. Setup and reusable paths

Start from the repository root and load the analysis environment:

```bash
source env.sh
```

Initialize a CMS proxy if the selected storage requires one:

```bash
voms-proxy-init --rfc --voms cms -valid 192:00
voms-proxy-info
```

Define the paths for the current user or production account. These values are
examples of the required layout, not fixed locations:

```bash
export SKIM_BASE="/path/to/validated/skims"
export MANIFESTS="/path/to/validation/manifests"
export CAMPAIGN_BASE="/path/to/campaign/output"
export PLOT_BASE="/path/to/plot/output"
```

Define the common campaign selections:

```bash
ERAS="2022,2022EE,2023,2023BPix,2024,2025"

MC_DATASETS="DiTriBoson,DY_amcatnlo,DY_amcatnlo_105_160,EWK,signals,SingleH,SingleTop,TTX,TT,W"
ALL_DATASETS="data,${MC_DATASETS}"

SYSTEMATICS="Central,JERC,ScaRe,Muon,PU,QCDScale,PDF"

DNN_BASE="${CAMPAIGN_BASE}/DNN_VBFEta"
FEATURES_BASE="${CAMPAIGN_BASE}/InputFeatures_VBFEta"
```

The DNN application uses the same payload for every era:

```text
common/updated_DNN_configs
common/updated_DNN_models
```

This also applies when the DNN is reevaluated with a shifted dimuon mass in
the sidebands.

## 2. DNN campaign

### 2.1 Central production

Central production includes both data and MC:

```bash
./hmumu hist \
  -e "${ERAS}" \
  -s Central \
  --datasets "${ALL_DATASETS}" \
  -v DNN_NNOutput \
  -r Z_sideband,H_sideband,Signal_Fit \
  --vbf-eta-regions \
  --input-dir "${SKIM_BASE}" \
  --manifests "${MANIFESTS}" \
  --output-base "${DNN_BASE}" \
  --chunk-size 5 \
  --cores 1 \
  --condor \
  --run
```

### 2.2 Shifted-systematic production

Shifted production contains MC only. Each output directory contains only its
requested family of variations and no nominal histograms.

```bash
./hmumu hist \
  -e "${ERAS}" \
  -s JERC,ScaRe,Muon,PU,QCDScale,PDF \
  --datasets "${MC_DATASETS}" \
  -v DNN_NNOutput \
  -r Z_sideband,H_sideband,Signal_Fit \
  --vbf-eta-regions \
  --input-dir "${SKIM_BASE}" \
  --manifests "${MANIFESTS}" \
  --output-base "${DNN_BASE}" \
  --chunk-size 5 \
  --cores 1 \
  --condor \
  --run \
  -- \
  --skip-failed-chunks
```

### 2.3 Check production status

Check Central:

```bash
./hmumu hist \
  -e "${ERAS}" \
  -s Central \
  --datasets "${ALL_DATASETS}" \
  -v DNN_NNOutput \
  -r Z_sideband,H_sideband,Signal_Fit \
  --vbf-eta-regions \
  --input-dir "${SKIM_BASE}" \
  --manifests "${MANIFESTS}" \
  --output-base "${DNN_BASE}" \
  --condor \
  --check
```

Check shifted systematics:

```bash
./hmumu hist \
  -e "${ERAS}" \
  -s JERC,ScaRe,Muon,PU,QCDScale,PDF \
  --datasets "${MC_DATASETS}" \
  -v DNN_NNOutput \
  -r Z_sideband,H_sideband,Signal_Fit \
  --vbf-eta-regions \
  --input-dir "${SKIM_BASE}" \
  --manifests "${MANIFESTS}" \
  --output-base "${DNN_BASE}" \
  --condor \
  --check
```

Do not start the hadd stage until the check reports no missing outputs and no
relevant jobs still in the queue.

## 3. Default-observable campaign

Omitting `-v` makes `hist_maker.py` use the observables configured in the
`maincfg.yaml` for each era.

### 3.1 Central production

```bash
./hmumu hist \
  -e "${ERAS}" \
  -s Central \
  --datasets "${ALL_DATASETS}" \
  -r Z_sideband,H_sideband,Signal_Fit \
  --vbf-eta-regions \
  --input-dir "${SKIM_BASE}" \
  --manifests "${MANIFESTS}" \
  --output-base "${FEATURES_BASE}" \
  --chunk-size 5 \
  --cores 1 \
  --condor \
  --run
```

### 3.2 Shifted-systematic production

```bash
./hmumu hist \
  -e "${ERAS}" \
  -s JERC,ScaRe,Muon,PU,QCDScale,PDF \
  --datasets "${MC_DATASETS}" \
  -r Z_sideband,H_sideband,Signal_Fit \
  --vbf-eta-regions \
  --input-dir "${SKIM_BASE}" \
  --manifests "${MANIFESTS}" \
  --output-base "${FEATURES_BASE}" \
  --chunk-size 5 \
  --cores 1 \
  --condor \
  --run \
  -- \
  --skip-failed-chunks
```

### 3.3 Check production status

Check Central:

```bash
./hmumu hist \
  -e "${ERAS}" \
  -s Central \
  --datasets "${ALL_DATASETS}" \
  -r Z_sideband,H_sideband,Signal_Fit \
  --vbf-eta-regions \
  --input-dir "${SKIM_BASE}" \
  --manifests "${MANIFESTS}" \
  --output-base "${FEATURES_BASE}" \
  --condor \
  --check
```

Check shifted systematics:

```bash
./hmumu hist \
  -e "${ERAS}" \
  -s JERC,ScaRe,Muon,PU,QCDScale,PDF \
  --datasets "${MC_DATASETS}" \
  -r Z_sideband,H_sideband,Signal_Fit \
  --vbf-eta-regions \
  --input-dir "${SKIM_BASE}" \
  --manifests "${MANIFESTS}" \
  --output-base "${FEATURES_BASE}" \
  --condor \
  --check
```

## 4. Hadd datasets into physics processes

Run the per-process hadd independently for every systematic and campaign:

```bash
for campaign in "${DNN_BASE}" "${FEATURES_BASE}"; do
  for systematic in Central JERC ScaRe Muon PU QCDScale PDF; do
    ./hmumu hadd-processes \
      "${campaign}/Hists_${systematic}" \
      -e "${ERAS}" \
      -o "${campaign}/hadded/Hists_${systematic}" \
      --run
  done
done
```

Data are present only in `hadded/Hists_Central`. Shifted directories contain
MC variations only.

## 5. Merge Central and shifted systematics

First inspect the plans:

```bash
for campaign in "${DNN_BASE}" "${FEATURES_BASE}"; do
  ./hmumu merge-systematics \
    "${campaign}/hadded/Hists_Central" \
    -s "${SYSTEMATICS}" \
    -e "${ERAS}" \
    -o "${campaign}/hadded/Hists_merged"
done
```

Then execute:

```bash
for campaign in "${DNN_BASE}" "${FEATURES_BASE}"; do
  ./hmumu merge-systematics \
    "${campaign}/hadded/Hists_Central" \
    -s "${SYSTEMATICS}" \
    -e "${ERAS}" \
    -o "${campaign}/hadded/Hists_merged" \
    --run
done
```

The merged data files contain only Central histograms. The merged MC files
contain the nominal histograms and all requested shifted templates.

## 6. Combine the 2022 and 2023 eras

The default `merge-eras` input set is:

```text
Run3_2022
Run3_2022EE
Run3_2023
Run3_2023BPix
```

Inspect the plans:

```bash
./hmumu merge-eras "${DNN_BASE}/hadded/Hists_merged"
./hmumu merge-eras "${FEATURES_BASE}/hadded/Hists_merged"
```

Execute:

```bash
./hmumu merge-eras \
  "${DNN_BASE}/hadded/Hists_merged" \
  --run

./hmumu merge-eras \
  "${FEATURES_BASE}/hadded/Hists_merged" \
  --run
```

This creates:

```text
${DNN_BASE}/hadded/Hists_merged/Run3_2022_23
${FEATURES_BASE}/hadded/Hists_merged/Run3_2022_23
```

The 2024 and 2025 directories remain separate.

## 7. Plotting

Define the nested ROOT regions:

```bash
ETA_REGIONS="Signal_Fit_VBF/incl,Signal_Fit_VBF/CC,Signal_Fit_VBF/CF,Signal_Fit_VBF/FF,Z_sideband_VBF/incl,Z_sideband_VBF/CC,Z_sideband_VBF/CF,Z_sideband_VBF/FF,H_sideband_VBF/incl,H_sideband_VBF/CC,H_sideband_VBF/CF,H_sideband_VBF/FF"
```

Define the standard plot samples:

```bash
PLOT_SAMPLES="DY_amcatnlo Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W_NJets TT"
```

### 7.1 Plot DNN output

Without `--run`, `hmumu plot` prints the commands without creating plots.
The following block executes them:

```bash
for era in \
  Run3_2022 \
  Run3_2022EE \
  Run3_2023 \
  Run3_2023BPix \
  Run3_2024 \
  Run3_2025 \
  Run3_2022_23
do
  ./hmumu plot \
    -e "${era}" \
    -i "${DNN_BASE}/hadded/Hists_merged/${era}" \
    -o "${PLOT_BASE}/DNN_VBFEta" \
    -r "${ETA_REGIONS}" \
    --samples ${PLOT_SAMPLES} \
    -v DNN_NNOutput \
    --data \
    --log-y \
    --rebin \
    --systematics \
    --normalize-dy-to-data \
    --dy-normalization-sample DY_amcatnlo \
    --run
done
```

### 7.2 Plot default observables

Omit `-v` to plot every available configured observable:

```bash
for era in \
  Run3_2022 \
  Run3_2022EE \
  Run3_2023 \
  Run3_2023BPix \
  Run3_2024 \
  Run3_2025 \
  Run3_2022_23
do
  ./hmumu plot \
    -e "${era}" \
    -i "${FEATURES_BASE}/hadded/Hists_merged/${era}" \
    -o "${PLOT_BASE}/InputFeatures_VBFEta" \
    -r "${ETA_REGIONS}" \
    --samples ${PLOT_SAMPLES} \
    --data \
    --log-y \
    --rebin \
    --systematics \
    --normalize-dy-to-data \
    --dy-normalization-sample DY_amcatnlo \
    --run
done
```

To plot only selected observables, add, for example:

```bash
-v m_mumu,N_SelectedJets,m_jj,delta_eta_jj
```

## 8. Workflow summary

```text
Central production ─────┐
                        ├─> status check
shifted MC production ──┘
                              |
                              v
                    dataset-to-process hadd
                              |
                              v
                    merge Central + shifts
                              |
                              v
                    combine 2022–2023 eras
                              |
                              v
                           plotting
```

Never include data in shifted production. Never merge old shifted outputs that
contain nominal histograms: reproduce those outputs with one systematic family
per directory before running the systematic merge.
