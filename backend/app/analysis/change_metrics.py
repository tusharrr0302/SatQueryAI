"""Pixel-derived Sentinel-2 vegetation change metrics."""
from __future__ import annotations

from typing import Any

import numpy as np

from app.imagery.planetary_computer import SceneData


def _ndvi(scene: SceneData) -> np.ndarray:
    denominator = scene.nir + scene.red
    return np.divide(scene.nir - scene.red, denominator, out=np.full_like(denominator, np.nan), where=denominator != 0)


def _mean(values: np.ndarray) -> float | None:
    return float(np.nanmean(values)) if np.isfinite(values).any() else None


def compute_change_metrics(before: SceneData, after: SceneData, series: list[SceneData], threshold: float = 0.15) -> dict[str, Any]:
    before_ndvi = _ndvi(before)
    after_ndvi = _ndvi(after)
    shape = (min(before_ndvi.shape[0], after_ndvi.shape[0]), min(before_ndvi.shape[1], after_ndvi.shape[1]))
    before_ndvi = before_ndvi[: shape[0], : shape[1]]
    after_ndvi = after_ndvi[: shape[0], : shape[1]]
    difference = after_ndvi - before_ndvi
    valid = np.isfinite(difference)
    changed = valid & (np.abs(difference) >= threshold)
    pixel_area_km2 = (before.pixel_area_km2 + after.pixel_area_km2) / 2
    changed_area = float(changed.sum() * pixel_area_km2)
    loss = valid & (difference <= -threshold)
    gain = valid & (difference >= threshold)
    valid_count = int(valid.sum())
    return {
        "mean_ndvi_before": _mean(before_ndvi),
        "mean_ndvi_after": _mean(after_ndvi),
        "mean_ndvi_change": _mean(difference),
        "changed_area_km2": changed_area,
        "vegetation_loss_pct": float(loss.sum() / valid_count * 100) if valid_count else None,
        "vegetation_gain_pct": float(gain.sum() / valid_count * 100) if valid_count else None,
        "change_threshold": threshold,
        "pixel_resolution_m": 10,
        "time_series": [
            {"date": scene.date, "metric_name": "mean_ndvi", "value": _mean(_ndvi(scene))}
            for scene in series
        ],
    }
