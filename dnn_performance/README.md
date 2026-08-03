# DNN performance tools

This directory is the public entry point for DNN validation and performance
studies.  Histogram production itself (including sideband dimuon-mass shifts)
lives in `common/dnn_histogram_production.py` and is called by
`histograms/hist_maker.py`.

Available commands:

```bash
python3 dnn_performance/check_model_inputs.py --help
python3 dnn_performance/compare_performance.py --help
python3 dnn_performance/optimize_binning.py --help
python3 dnn_performance/rebin_histograms.py --help
```

The corresponding `tools/*.py` files remain compatibility entry points for
existing campaigns and tests.
