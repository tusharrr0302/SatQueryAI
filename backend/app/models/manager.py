"""Model dispatch for live Earth-observation analysis."""
from __future__ import annotations

from pathlib import Path
import gc
from threading import Lock
from typing import Any

from app.analysis.change_metrics import compute_change_metrics
from app.config import settings
from app.geo.resolver import resolve_aoi
from app.imagery.planetary_computer import ImageryError, fetch_before_after_and_series
from app.models.registry import MODEL_REGISTRY
from app.schemas.normalized_result import (
    AOIInfo, MetricItem, NormalizedResult, Provenance, SatelliteImagePair,
    TimeSeriesPoint, VisualizationSpec,
)
from app.services.scenario_adapter import _build_audit_trace


class ModelNotImplementedError(RuntimeError):
    """Raised when a registered model has no hosted inference implementation."""


def _as_number(value: Any) -> float:
    return float(value) if value is not None else float("nan")


class ModelManager:
    _live_analysis_lock = Lock()

    def execute(self, *, model_id: str, query: str, request: dict[str, Any]) -> NormalizedResult:
        if not self._live_analysis_lock.acquire(blocking=False):
            raise ImageryError("Another live satellite analysis is already running; please retry shortly")
        try:
            return self._execute(model_id=model_id, query=query, request=request)
        finally:
            gc.collect()
            self._live_analysis_lock.release()

    def _execute(self, *, model_id: str, query: str, request: dict[str, Any]) -> NormalizedResult:
        model_key = (model_id or "").lower().replace("_", "-")
        if model_key not in MODEL_REGISTRY:
            model_key = "prithvi-eo-2.0"

        aoi_name = (request.get("aoi") or {}).get("name") or query
        aoi = resolve_aoi(aoi_name)
        intent = request.get("intent") or {}
        temporal = intent.get("temporal_scope") or {}
        output_dir = Path(__file__).resolve().parents[2] / settings.IMAGE_OUTPUT_DIR
        before, after, series = fetch_before_after_and_series(
            aoi.bbox,
            temporal.get("start"),
            temporal.get("end"),
            str(output_dir),
        )
        metrics = compute_change_metrics(before, after, series)
        time_series = [
            TimeSeriesPoint(date=point["date"], metric_name=point["metric_name"], value=_as_number(point["value"]))
            for point in metrics["time_series"] if point["value"] is not None
        ]
        ndvi_change = metrics["mean_ndvi_change"]
        loss = metrics["vegetation_loss_pct"]
        gain = metrics["vegetation_gain_pct"]
        change_text = "unavailable" if ndvi_change is None else f"{ndvi_change:.4f}"
        metrics_items = [
            MetricItem(label="Mean NDVI before", value=f"{metrics['mean_ndvi_before']:.4f}", unit="NDVI"),
            MetricItem(label="Mean NDVI after", value=f"{metrics['mean_ndvi_after']:.4f}", unit="NDVI"),
            MetricItem(label="Mean NDVI change", value=change_text, unit="NDVI"),
            MetricItem(label="Changed area", value=f"{metrics['changed_area_km2']:.4f}", unit="km²"),
            MetricItem(label="Vegetation loss", value=f"{loss:.4f}" if loss is not None else "unavailable", unit="%"),
            MetricItem(label="Vegetation gain", value=f"{gain:.4f}" if gain is not None else "unavailable", unit="%"),
        ]
        output_root = output_dir
        before_url = f"/generated-images/{before.true_color_path.relative_to(output_root).as_posix()}"
        after_url = f"/generated-images/{after.true_color_path.relative_to(output_root).as_posix()}"
        dataset_ids = (request.get("data_requirements") or {}).get("datasets") or ["sentinel-2"]
        model_meta = MODEL_REGISTRY.get(model_key, {})
        model_display_name = model_meta.get("name", model_id)
        return NormalizedResult(
            query=query,
            analysis_type=(request.get("analysis") or {}).get("operation", "temporal_change"),
            aoi=aoi,
            aoi_bbox=aoi.bbox,
            location={"name": aoi.name, "latitude": aoi.center.latitude, "longitude": aoi.center.longitude},
            provenance=Provenance(
                source="planetary_computer", fallback=False, model_id=model_key,
                model_name=model_display_name, dataset_ids=dataset_ids,
                acquisition_dates=f"{before.date} to {after.date}", pipeline="Nominatim / Planetary Computer / rasterio",
            ),
            key_finding=f"Sentinel-2 NDVI changed by {change_text} across {metrics['changed_area_km2']:.4f} km² between {before.date} and {after.date}.",
            scientific_explanation=(
                f"Pixel-level NDVI was computed from Sentinel-2 B08 and B04 reflectance for {aoi.name}. "
                f"Pixels with absolute NDVI change at least {metrics['change_threshold']:.2f} were counted at 10 m resolution."
            ),
            metrics=metrics_items,
            image_comparison=SatelliteImagePair(
                t1_date=before.date, t1_url=before_url, t1_label="Before",
                t2_date=after.date, t2_url=after_url, t2_label="After",
                description="Sentinel-2 B04/B03/B02 true-color composites clipped to the resolved AOI.",
            ),
            before_image_url=before_url,
            after_image_url=after_url,
            time_series=time_series,
            visualization=VisualizationSpec(
                type="Time Series", title=f"Observed mean NDVI for {aoi.name}",
                date_range=f"{before.date} to {after.date}",
                timeseries=time_series,
            ),
            visualizations=[{
                "id": "ndvi_time_series", "type": "line", "renderer": "echarts",
                "title": f"Observed mean NDVI for {aoi.name}",
                "data": [point.model_dump() for point in time_series],
            }],
            confidence=None, confidence_level=None,
            audit_trace=_build_audit_trace(model_display_name, dataset_ids),
        )


model_manager = ModelManager()
