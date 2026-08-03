# Run 3 H→μμ analysis

This repository contains the NanoAOD-to-datacard workflow for the Run 3
\(H\to\mu\mu\) analysis.

The single operational guide is:

[Run 3 H→μμ analysis workflow](docs/ANALYSIS_WORKFLOW.md)

The complete documentation is available at:

[https://valeriadamante.github.io/Hmm_newSkim/](https://valeriadamante.github.io/Hmm_newSkim/)

It covers environment setup, NanoAOD discovery, skim production and
validation, central and shifted histograms, DY/EWK routing, reco/gen jet
components, hadd and merge stages, plotting, and Combine datacards.

For command help:

```bash
./hmumu --help
campaigns/run3_skim_v3.sh --help
campaigns/run3_region_routed_backgrounds.sh --help
```
