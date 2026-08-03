# Analysis workflow

Production is split into two manifest-driven stages. Histogram jobs consume the
validation manifests directly; there is no intermediate tuple production step.

## 1. Validate skim outputs

The validation stage checks every ROOT `Events` tree and parses every JSON skim
report. It writes one manifest per era and dataset containing valid and invalid
ROOT/JSON lists.

```bash
bash analysis/scripts/validate.sh \
  --era Run3_2024 \
  --datasets data,EWK,DY_amcatnlo,DY_amcatnlo_105_160,signals \
  --input-folder skim_v2 \
  --output-dir /eos/user/v/vdamante/H_mumu/manifests \
  --chunk-size 8
```

Here `--chunk-size` is the number of parallel validation workers per dataset.
Add `--condor` to submit one validation job per dataset.

Output:

```text
manifests/Run3_2024/DATASET.json
```

## 2. Produce histograms

The histogram stage reads validation manifests and then opens the validated skim
ROOT and JSON inputs.

```bash
bash histograms/scripts/hists.sh \
  --era Run3_2024 \
  --datasets data,EWK,DY_amcatnlo,DY_amcatnlo_105_160,signals \
  --input-folder /eos/user/v/vdamante/H_mumu/manifests \
  --root-input-folder skim_v2 \
  --json-input-folder skim_v2 \
  --output-dir /eos/user/v/vdamante/H_mumu/hists \
  --chunk-size 20 \
  -- \
  --variables DNN_NNOutput
```

Add `--condor` to submit one histogram job per dataset. Use
`histograms/scripts/systematics.sh` for shifted histograms; it defaults to
`--systematics all`.

For the standard Run3 2024 central plus shifted Condor submissions:

```bash
bash histograms/scripts/submit_2024_histograms_condor.sh --dry-run
```

Run with `--submit` when the generated submit files look right.

## Shared implementation

- `common/scripts/dataset_campaign.sh`: dataset groups and local/Condor campaign handling.
- `htcondor/run_stage_condor.sh`: common Condor worker for validation, central histograms, and shifted histograms.
- `common/manifest_utilities.py`: manifest schema, resolution, and atomic writes.
- `common/rdf_utilities.py`: shared RDF construction and histogram helpers.
- `histograms/histogram_pipeline.py`: shared selections and weight composition.
- `common/dnn_application.py`: shared DNN inference.
