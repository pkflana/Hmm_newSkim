import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = Path(__file__).resolve().parents[1] / "compare_dnn_performance.py"
SPEC = importlib.util.spec_from_file_location("compare_dnn_performance", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_metrics_and_direct_comparison():
    edges = np.array([0.0, 0.5, 1.0])
    old = MODULE.metrics(
        np.array([5.0, 5.0]), np.array([8.0, 2.0]), edges, (0.5,)
    )
    new = MODULE.metrics(
        np.array([2.0, 8.0]), np.array([9.0, 1.0]), edges, (0.5,)
    )
    comparison = MODULE.compare_results(old, new)

    assert new["auc"] > old["auc"]
    assert comparison["auc_delta"] > 0
    point = comparison["background_efficiency_at_signal_efficiency"]["0.50"]
    assert point["updated"] < point["legacy"]
    assert point["absolute_reduction"] > 0
