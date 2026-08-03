# Script layout

The histogram workflow is split by responsibility:

- `analysis/validate_dataset.py` validates skim outputs and writes a versioned
  manifest through `common/manifest_utilities.py`, which also resolves or
  creates validation manifests for downstream jobs.
- `common/add_var_to_skim.py` owns histogram regions, object selections, and
  categories.
- `common/add_vars_to_skim_tuples.py` owns reusable physics observables added
  to skim dataframes.
- `common/jet_component_splitting.py` owns reco/gen jet matching and the
  special DY jet-component categories.
- `histograms/dnn_histogram_production.py` owns sideband dimuon-mass remapping and
  shifted DNN evaluation.
- `histograms/histogram_pipeline.py` applies selections and final event weights
  exactly once.
- `histograms/hist_maker.py` orchestrates input chunks and books/writes the
  histograms.
- `dnn_performance/` exposes model-input checks, performance comparisons, and
  DNN histogram binning tools.
- `plotting_tools/` contains the active histogram plotter, reusable plotting
  functions, bin-edge generator, and plotting shell helpers.
- `tools/derive_dy_ptll_njets_reweight.py` and
  `tools/derive_dy_njets_reweight.py` derive correction payloads from already
  produced histograms; they are analysis tools, not histogram producers.
- `tools/variable_catalog.py` powers `hmumu vars` and `hmumu where` by scanning
  framework source code for RDataFrame `Define`/`Redefine` calls and matching
  them to configured variables.

This keeps the main booking loop focused on the readable sequence:
selection dataframe, output directory, variable specification, histogram
booking, and writing.
