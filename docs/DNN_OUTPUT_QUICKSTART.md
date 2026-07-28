# DNN Output Quick Start

This is the short workflow for producing and plotting `DNN_NNOutput` across
all Run 3 eras.

Use the [complete campaign guide](RUN3_CAMPAIGN_WORKFLOW.md) for advanced
options, recovery procedures, and the default-observable campaign.

## What this workflow produces

For every era, it produces `DNN_NNOutput` in:

```text
Signal_Fit_VBF/{incl,CC,CF,FF}
Z_sideband_VBF/{incl,CC,CF,FF}
H_sideband_VBF/{incl,CC,CF,FF}
```

The jet-eta regions are:

```text
CC: both VBF jets have |eta| < 2.5
CF: one VBF jet has |eta| < 2.5 and the other has |eta| >= 2.5
FF: both VBF jets have |eta| >= 2.5
incl: no additional jet-eta selection
```

The same updated DNN configuration and models are used for every era:

```text
common/updated_DNN_configs
common/updated_DNN_models
```

## Step 1: set up the environment

Run everything from the repository root:

```bash
source env.sh
```

Initialize a CMS proxy if required by the storage system:

```bash
voms-proxy-init --rfc --voms cms -valid 192:00
```

Set the three paths for your account or production area:

```bash
export SKIM_BASE="/path/to/validated/skims"
export MANIFESTS="/path/to/validation/manifests"
export DNN_BASE="/path/to/campaign/output/DNN_VBFEta"
export PLOT_BASE="/path/to/plot/output"
```

Define the common selections:

```bash
ERAS="2022,2022EE,2023,2023BPix,2024,2025"

MC_DATASETS="DiTriBoson,DY_amcatnlo,DY_amcatnlo_105_160,EWK,signals,SingleH,SingleTop,TTX,TT,W"
ALL_DATASETS="data,${MC_DATASETS}"
```

## Step 2: produce Central histograms

Central production includes data and MC:

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

Output:

```text
${DNN_BASE}/Hists_Central
```

## Step 3: produce systematic variations

Shifted systematics run on MC only. Never include data in this command.

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

This creates:

```text
${DNN_BASE}/Hists_JERC
${DNN_BASE}/Hists_ScaRe
${DNN_BASE}/Hists_Muon
${DNN_BASE}/Hists_PU
${DNN_BASE}/Hists_QCDScale
${DNN_BASE}/Hists_PDF
```

Each shifted directory contains only its own variations, not Central.

## Step 4: check that production is complete

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

Check the variations:

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

Wait until no required jobs are queued and no outputs are missing.

## Step 5: combine datasets into physics processes

```bash
for systematic in Central JERC ScaRe Muon PU QCDScale PDF; do
  ./hmumu hadd-processes \
    "${DNN_BASE}/Hists_${systematic}" \
    -e "${ERAS}" \
    -o "${DNN_BASE}/hadded/Hists_${systematic}" \
    --run
done
```

## Step 6: merge Central and systematic variations

Preview the merge:

```bash
./hmumu merge-systematics \
  "${DNN_BASE}/hadded/Hists_Central" \
  -s Central,JERC,ScaRe,Muon,PU,QCDScale,PDF \
  -e "${ERAS}" \
  -o "${DNN_BASE}/hadded/Hists_merged"
```

Execute it:

```bash
./hmumu merge-systematics \
  "${DNN_BASE}/hadded/Hists_Central" \
  -s Central,JERC,ScaRe,Muon,PU,QCDScale,PDF \
  -e "${ERAS}" \
  -o "${DNN_BASE}/hadded/Hists_merged" \
  --run
```

## Step 7: combine the 2022 and 2023 eras

Preview:

```bash
./hmumu merge-eras "${DNN_BASE}/hadded/Hists_merged"
```

Execute:

```bash
./hmumu merge-eras \
  "${DNN_BASE}/hadded/Hists_merged" \
  --run
```

This creates:

```text
${DNN_BASE}/hadded/Hists_merged/Run3_2022_23
```

## Step 8: make the plots

Define the regions and samples:

```bash
ETA_REGIONS="Signal_Fit_VBF/incl,Signal_Fit_VBF/CC,Signal_Fit_VBF/CF,Signal_Fit_VBF/FF,Z_sideband_VBF/incl,Z_sideband_VBF/CC,Z_sideband_VBF/CF,Z_sideband_VBF/FF,H_sideband_VBF/incl,H_sideband_VBF/CC,H_sideband_VBF/CF,H_sideband_VBF/FF"

PLOT_SAMPLES="DY_amcatnlo Data_Muon EWK GluGluHto2Mu SingleH SingleTop TTX VBFHto2Mu_M125_powheg DiTriBoson W_NJets TT"
```

Plot all individual eras and the combined 2022–2023 era:

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

## Quick checklist

Before moving to the next step, verify:

- [ ] Central production contains data and MC.
- [ ] Shifted production contains MC only.
- [ ] `Hists_JERC` contains only JERC variations, and similarly for the other
      shifted directories.
- [ ] The production check reports no missing outputs.
- [ ] Per-process hadded files exist for every era.
- [ ] Merged MC files contain Central and all shifted templates.
- [ ] Merged data files contain Central only.
- [ ] `Run3_2022_23` was created from the four 2022/2023 periods.
- [ ] Plots exist for `incl`, `CC`, `CF`, and `FF`.

The full sequence is:

```text
Central + shifted production
            |
            v
           check
            |
            v
  dataset-to-process hadd
            |
            v
    systematic merge
            |
            v
     2022–2023 merge
            |
            v
          plots
```
