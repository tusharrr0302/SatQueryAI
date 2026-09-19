from pathlib import Path

import numpy as np
import pytest

from app.analysis.change_metrics import compute_change_metrics
from app.imagery.planetary_computer import SceneData
from app.models.manager import ModelNotImplementedError, model_manager


def _scene(ndvi: float, name: str) -> SceneData:
    red = np.full((2, 2), 100.0)
    nir = np.full((2, 2), 100.0 * (1 + ndvi) / (1 - ndvi))
    return SceneData(name, "2025-01-01", red, red, red, nir, {}, 0.0, Path("/tmp/test.png"))


def test_change_metrics_are_pixel_derived():
    result = compute_change_metrics(_scene(0.2, "before"), _scene(0.4, "after"), [_scene(0.2, "series")])
    assert result["changed_area_km2"] == 0.0004
    assert result["vegetation_gain_pct"] == 100.0
    assert result["mean_ndvi_change"] == pytest.approx(0.2)


def test_unhosted_models_are_explicitly_gated():
    try:
        model_manager.execute(model_id="geochat-7b", query="Delhi", request={})
    except ModelNotImplementedError:
        return
    raise AssertionError("unhosted model returned a fabricated result")