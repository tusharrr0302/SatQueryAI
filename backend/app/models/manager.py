"""Model dispatch for live Earth-observation analysis."""
from __future__ import annotations

from pathlib import Path
import gc
from threading import Lock
from typing import Any

from app.analysis.change_metrics import compute_change_metrics
from app.config import settings
from app.geo.resolver import AOIResolutionError, resolve_aoi
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

    def execute(self, *, model_id: str, query: str, request: dict[str, Any], aoi: Optional[AOIInfo] = None) -> NormalizedResult:
        if not self._live_analysis_lock.acquire(blocking=False):
            raise ImageryError("Another live satellite analysis is already running; please retry shortly")
        try:
            return self._execute(model_id=model_id, query=query, request=request, aoi=aoi)
        finally:
            gc.collect()
            self._live_analysis_lock.release()

    def _execute(self, *, model_id: str, query: str, request: dict[str, Any], aoi: Optional[AOIInfo] = None) -> NormalizedResult:
        model_key = (model_id or "").lower().replace("_", "-")
        if model_key not in ["deterministic-spectral-analysis", "prithvi-eo-2.0", "sentinel-2-ndvi", "ndvi"]:
            raise ModelNotImplementedError(
                f"{model_id} is registered but has no hosted local inference implementation; "
                "only deterministic Sentinel-2 spectral analysis is currently available locally"
            )

        if aoi is None:
            resolved_aoi_dict = request.get("resolved_aoi")
            if resolved_aoi_dict:
                aoi = AOIInfo.model_validate(resolved_aoi_dict) if isinstance(resolved_aoi_dict, dict) else resolved_aoi_dict
            else:
                req_aoi = request.get("aoi") or {}
                aoi_name = req_aoi.get("name")
                if not aoi_name or aoi_name.strip().casefold() == query.strip().casefold():
                    raise AOIResolutionError("Geographic location is required for satellite analysis. Please specify a recognized place or administrative boundary.")
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
        try:
            rel_before = before.true_color_path.relative_to(output_root).as_posix()
        except ValueError:
            rel_before = before.true_color_path.name
        try:
            rel_after = after.true_color_path.relative_to(output_root).as_posix()
        except ValueError:
            rel_after = after.true_color_path.name
        before_url = f"/generated-images/{rel_before}"
        after_url = f"/generated-images/{rel_after}"
        dataset_ids = ["Sentinel-2 L2A"]
        model_display_name = "Deterministic Spectral Analysis"
        return NormalizedResult(
            query=query,
            analysis_type=(request.get("analysis") or {}).get("operation", "temporal_change"),
            aoi=aoi,
            aoi_bbox=aoi.bbox,
            location={"name": aoi.name, "latitude": aoi.center.latitude, "longitude": aoi.center.longitude},
            provenance=Provenance(
                source="live",
                fallback=False,
                model_id="deterministic-spectral-analysis",
                model_name=model_display_name,
                algorithm="NDVI = (B08 - B04) / (B08 + B04)",
                dataset_ids=dataset_ids,
                acquisition_dates=f"{before.date} to {after.date}",
                pipeline="Nominatim / Planetary Computer / rasterio",
                notes="Deterministic spectral index computed directly from surface reflectance bands without foundation model inference.",
            ),
            key_finding=f"Sentinel-2 NDVI changed by {change_text} across {metrics['changed_area_km2']:.4f} km² between {before.date} and {after.date}.",
            scientific_explanation=(
                f"Observed: Sentinel-2 mean NDVI changed by {change_text} across {metrics['changed_area_km2']:.4f} km² between {before.date} and {after.date} in {aoi.name}.\n\n"
                "Possible explanations: Such reductions or increases may correspond to seasonal phenological cycles, agricultural cultivation patterns, or land cover transitions.\n\n"
                "Not established: Satellite spectral index alone does not establish causation without ground validation or higher-resolution land classification."
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
