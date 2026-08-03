# Skim v3 production campaign

This guide explains how to contribute to the new Run 3 \(H\to\mu\mu\) skim
production.

## Campaign scope

The campaign covers:

- `Run3_2022`
- `Run3_2022EE`
- `Run3_2023`
- `Run3_2023BPix`
- `Run3_2024`
- `Run3_2025`
- `Run3_2026`

Outputs are stored by era and dataset:

```text
/eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3/<ERA>/<DATASET>/
```

Each chunk produces one matching pair:

```text
skim_0.root  <-> report_0.json
skim_1.root  <-> report_1.json
...
```

A chunk contains at most 5 GiB of NanoAOD input and no more than five input
files. The complete input/output mapping is saved in:

```text
htcondor/log/<ERA>/<DATASET>/skim_chunks.json
```

## Coordination between contributors

Assign each era explicitly to one person before starting.

Do not submit the same era concurrently from the same checkout. Both processes
would update the same local logs and chunk manifests. Different eras can be
produced in parallel.

Record the following information for every era:

- responsible person;
- commit or exact code state;
- submission date;
- number of jobs;
- failed jobs, if any;
- final validation result.

## Environment setup

Enter the repository and load the environment:

```bash
cd /afs/cern.ch/work/v/vdamante/Hmm_newSkim
source env.sh
export ANALYSIS_PATH="$PWD"
```

Create your own VOMS proxy:

```bash
voms-proxy-init --voms cms --valid 192:00
export X509_USER_PROXY="$(voms-proxy-info -path)"
voms-proxy-info --timeleft
```

Every contributor must use their own proxy. Never copy or share another
person's proxy.

Check that the shared destination is writable:

```bash
test -w /eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3 \
  && echo "EOS writable" \
  || echo "EOS is not writable for this user"
```

If the directory is not writable, agree on an alternative destination and pass
it through `--output-dir`.

## Checking NanoAOD dataset versions

This step must be coordinated by one person before splitting production among
contributors.

To inspect one era without modifying any files:

```bash
python3 htcondor/update_nanoaod_versions.py \
  --era Run3_2024 \
  --include-data \
  --dry-run
```

To inspect all eras:

```bash
ERAS="Run3_2022,Run3_2022EE,Run3_2023,Run3_2023BPix,Run3_2024,Run3_2025,Run3_2026"

python3 htcondor/update_nanoaod_versions.py \
  --era "$ERAS" \
  --include-data \
  --dry-run
```

Review every proposed replacement manually. If the updates are correct, update
the `samples.yaml` files:

```bash
python3 htcondor/update_nanoaod_versions.py \
  --era "$ERAS" \
  --include-data \
  --in-place
```

Then regenerate the DAS file lists:

```bash
python3 htcondor/getfiles.py \
  --era "$ERAS" \
  --use-ext
```

Review the changes before submitting:

```bash
git diff -- config/Run3_*/samples.yaml config/Run3_*/samples_withfiles.yaml
```

The `--use-ext` option includes both nominal datasets and their configured
extensions.

## Mandatory test: one era and one job

Replace `Run3_2024` with the era assigned to you.

First create the chunk plan without submitting:

```bash
campaigns/run3_skim_v3.sh dry-run \
  --era Run3_2024
```

Check the following in the summary:

- selected datasets;
- output directory;
- number of inputs and chunks;
- chunk sizes;
- absence of DAS or proxy errors.

Submit exactly one job:

```bash
campaigns/run3_skim_v3.sh submit \
  --era Run3_2024 \
  --max-submit-jobs 1
```

Do not start the full campaign until this job finishes successfully.

## Checking the test job

Inspect the queue:

```bash
condor_q "$USER"
```

Logs are stored under:

```text
htcondor/log/<ERA>/<DATASET>/
```

Verify that both files were produced:

```text
skim_N.root
report_N.json
```

Run the missing-output check:

```bash
campaigns/run3_skim_v3.sh check \
  --era Run3_2024
```

Perform a minimal manual ROOT check:

```bash
rootls -t \
  /eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3/Run3_2024/<DATASET>/skim_0.root
```

Also check that the JSON report is readable:

```bash
python3 -m json.tool \
  /eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3/Run3_2024/<DATASET>/report_0.json \
  >/dev/null
```

## Submitting a complete era

After the test succeeds:

```bash
campaigns/run3_skim_v3.sh submit \
  --era Run3_2024
```

The submitter considers a chunk complete when both its non-empty ROOT file and
non-empty report are present.

To use an alternative destination:

```bash
campaigns/run3_skim_v3.sh submit \
  --era Run3_2024 \
  --output-dir /eos/user/X/USERNAME/skim_v3
```

Replace `X` with the first letter of the CERN username.

## Special Run3_2025 configuration

The campaign default is JEC 2025 with JER 2025:

```bash
campaigns/run3_skim_v3.sh submit \
  --era Run3_2025 
```

Do not change this mode without agreement from the production coordinator. The
available alternatives are:

```text
jec2024_jer2025
2024
```

They write to separate output directories.

## Dataset validation

The missing-output check only verifies that the expected files exist and are
non-empty. The validation stage must also be run before histogram production.
It:

- opens every ROOT file and checks the `Events` tree;
- parses every required JSON report;
- pairs `skim_N.root` with `report_N.json`;
- checks completeness against `skim_chunks.json`;
- records valid, empty, corrupt, and missing inputs;
- writes one validation manifest per era and dataset.

Choose an agreed manifest destination:

```bash
SKIM_BASE=/eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3
MANIFEST_BASE=/eos/user/v/vdamante/H_mumu/manifests_skim_v3
```

First inspect the validation commands for the assigned era:

```bash
bash analysis/scripts/validate.sh \
  --era Run3_2024 \
  --datasets skim_cfg \
  --root-input-folder "$SKIM_BASE" \
  --json-input-folder "$SKIM_BASE" \
  --output-dir "$MANIFEST_BASE" \
  --chunk-size 8 \
  --dry-run
```

Validate one dataset locally before launching the complete validation stage:

```bash
bash analysis/scripts/validate.sh \
  --era Run3_2024 \
  --dataset-name <DATASET> \
  --root-input-folder "$SKIM_BASE" \
  --json-input-folder "$SKIM_BASE" \
  --output-dir "$MANIFEST_BASE" \
  --chunk-size 8
```

The expected output is:

```text
<MANIFEST_BASE>/Run3_2024/<DATASET>.json
```

After this test succeeds, validate all datasets configured for the era. To
submit one validation job per dataset:

```bash
bash analysis/scripts/validate.sh \
  --era Run3_2024 \
  --datasets skim_cfg \
  --root-input-folder "$SKIM_BASE" \
  --json-input-folder "$SKIM_BASE" \
  --output-dir "$MANIFEST_BASE" \
  --chunk-size 8 \
  --condor
```

Alternatively, omit `--condor` to run datasets locally and sequentially.

Inspect the resulting manifest statuses:

```bash
python3 - "$MANIFEST_BASE/Run3_2024" <<'PY'
import json
import pathlib
import sys

for path in sorted(pathlib.Path(sys.argv[1]).glob("*.json")):
    with path.open() as handle:
        manifest = json.load(handle)
    summary = manifest.get("summary", {})
    print(
        path.stem,
        manifest.get("status"),
        f"valid={summary.get('root_valid', 0)}",
        f"invalid={summary.get('root_invalid', 0)}",
        f"missing={summary.get('input_missing', 0)}",
    )
PY
```

Do not start histogram production while any required dataset manifest has
`status: failed`, missing inputs, or unexplained invalid files.

## Relevant content of the new skims

Final physics categories, both nominal and shifted, are not stored in the
skims. They are defined later at histogram level by
`DefineHistogramSelections`.

The skims contain the objects and intermediate flags needed to reconstruct
those categories, including the muon and jet variations.

Newly stored information includes:

- `GenJet_idx`;
- `GenJet_pt`, `GenJet_eta`, `GenJet_phi`, and `GenJet_mass`;
- GenJet flavour and hadron counts, when available;
- `Jet_genJetIdx`;
- nominal and shifted `SelectedJet_genJetIdx`;
- the BSC/raw muon \(p_T\) uncertainty;
- scale and resolution corrections and variations, with and without FSR.

The selected muon \(p_T\) uncertainty is:

```text
Muon_bsConstrainedPtErr  if Muon_bsConstrainedChi2 < 30
Muon_ptErr               otherwise
```

FSR does not modify the track-fit uncertainty.

## End-of-production handoff

At the end of each era, run:

```bash
campaigns/run3_skim_v3.sh check \
  --era Run3_2024
```

Then complete the dataset-validation stage described above.

Send the production coordinator:

- completed era;
- responsible username;
- numbers of completed and missing chunks;
- list of failed jobs;
- validation-manifest location and status;
- output location;
- log location;
- JERC mode for Run3_2025;
- any excluded datasets or files.

Do not delete outputs, reports, manifests, or logs without agreement from the
production coordinator.



