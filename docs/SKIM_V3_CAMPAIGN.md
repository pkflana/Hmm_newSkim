# Skim v3 production campaign

This guide explains how to contribute to the new Run 3 \(H\to\mu\mu\) skim
production.


Eras to run: Run3_2022, Run3_2022EE, Run3_2023, Run3_2023BPix, Run3_2024, Run3_2025 (, Run3_2026)
Outputs are stored by era and dataset:

```text
/eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3/<ERA>/<DATASET>/
```

## To check before submitting the campaign:
- after loading the environment

```bash
cd /afs/cern.ch/work/v/vdamante/Hmm_newSkim
source env.sh
```
try running the era locally via `skim.py` (see [Local Skim Smoke Tests](RUNNING_INSTRUCTIONS.md#local-skim-smoke-tests)) with the specific ERA to run.

- Create/check your own VOMS proxy:

```bash
voms-proxy-init --voms cms --valid 192:00
export X509_USER_PROXY="$(voms-proxy-info -path)"
voms-proxy-info --timeleft
```

- Check that the shared destination is writable:

```bash
test -w /eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3 \
  && echo "EOS writable" \
  || echo "EOS is not writable for this user"
```
If the directory is not writable, contact Valeria.

- Check NanoAOD dataset versions

```bash
python3 htcondor/update_nanoaod_versions.py \
  --era <ERA> \
  --include-data \
  --in-place
```
Note: if you want to try dry-runs you replace ```--in-place``` with ```--dry-run```


- Regenerate the DAS file lists:

```bash
python3 htcondor/getfiles.py \
  --era <ERA>
```

## Mandatory test: one era and one job

Replace <ERA> with the era assigned to you.

First create the chunk plan without submitting:

```bash
campaigns/run3_skim_v3.sh dry-run \
  --era <ERA>
```

Check the following in the summary:

- selected datasets;
- output directory;
- absence of DAS or proxy errors.

Submit exactly one job:

```bash
campaigns/run3_skim_v3.sh submit \
  --era <ERA> \
  --max-submit-jobs 1
```

Do not start the full campaign until this job finishes successfully!!

## Checking the test job

To check condor queue:

```bash
condor_q "$USER"
```

The skim logs/outputs/error files are stored under:

```text
htcondor/log/<ERA>/<DATASET>/
htcondor/output/<ERA>/<DATASET>/
htcondor/error/<ERA>/<DATASET>/
```

Verify that both files were produced:

```text
skim_N.root
report_N.json
```

Run the missing-output check:

```bash
campaigns/run3_skim_v3.sh check \
  --era <ERA>
```

Perform a minimal manual ROOT check:

```bash
rootls -t \
  /eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3/<ERA>/<DATASET>/skim_0.root
```

Also check that the JSON report is readable:

```bash
python3 -m json.tool \
  /eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3/<ERA>/<DATASET>/report_0.json \
  >/dev/null
```

## Submitting a complete era

After the test succeeds:

```bash
campaigns/run3_skim_v3.sh submit \
  --era <ERA>
```

If (prior talking to Valeria about) you intend to use an alternative destination:

```bash
campaigns/run3_skim_v3.sh submit \
  --era <ERA> \
  --output-dir <OUTPUT_DIR>
```

## Dataset validation - AFTER final production

The missing-output check only verifies that the expected files exist and are
non-empty. The validation stage must also be run before histogram production.
It:

- opens every ROOT file and checks the `Events` tree;
- parses every required JSON report;
- pairs `skim_N.root` with `report_N.json`;
- checks completeness against `skim_chunks.json`;
- records valid, empty, corrupt, and missing inputs;
- writes one validation manifest per era and dataset.


```bash
bash analysis/scripts/validate.sh \
  --era <ERA> \
  --datasets skim_cfg \
  --root-input-folder /eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3 \
  --json-input-folder /eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3 \
  --output-dir /eos/user/v/vdamante/H_mumu/manifests_skim_v3
```
The expected output is:

```text
<MANIFEST_BASE>/Run3_2024/<DATASET>.json
```

After this test succeeds, validate all datasets configured for the era. To submit on condor one validation job per dataset:

```bash
bash analysis/scripts/validate.sh \
  --era <ERA> \
  --datasets skim_cfg \
  --root-input-folder /eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3 \
  --json-input-folder /eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3 \
  --output-dir /eos/user/v/vdamante/H_mumu/manifests_skim_v3
  --condor
```



