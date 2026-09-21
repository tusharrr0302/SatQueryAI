"""
backend/app/services/mock_specialists.py
─────────────────────────────────────────────────────────────────────────────
Mock execution adapters for EarthDial and Prithvi foundation models.
Used strictly when remote GPU worker is unreachable during Kaggle setup,
always maintaining honest provenance:
  source="mock", fallback=True, fallback_reason="..."
"""
from typing import Dict, Any, List, Optional
import uuid

from app.schemas.normalized_result import (
    NormalizedResult,
    AOIInfo,
    Coordinates,
    Provenance,
    MetricItem,
    TimeSeriesPoint,
)
from app.models.registry import MODEL_REGISTRY


def execute_mock_specialist(
    model_id: str,
    query: str,
    aoi_dict: Optional[Dict[str, Any]] = None,
) -> NormalizedResult:
    mid = model_id.lower().strip()
    model_meta = MODEL_REGISTRY.get(mid, {})
    model_name = model_meta.get("name", model_id)

    name = (aoi_dict or {}).get("name") or "Target AOI"
    center_dict = (aoi_dict or {}).get("center") or {}
    lat = center_dict.get("latitude", 28.6139)
    lon = center_dict.get("longitude", 77.2090)

    aoi_obj = AOIInfo(
        id=str(uuid.uuid4()),
        name=name,
        type="Polygon",
        center=Coordinates(latitude=lat, longitude=lon),
        area_km2=(aoi_dict or {}).get("area_km2", 25.0),
        bbox=(aoi_dict or {}).get("bbox") or [lon - 0.05, lat - 0.05, lon + 0.05, lat + 0.05],
        polygon=(aoi_dict or {}).get("polygon") or [],
    )

    if mid in ("earthdial", "earthdial-4b-ms", "geochat-7b"):
        key_finding = f"EarthDial-4B-MS scene interpretation for {name}: dense urban core with commercial infrastructure, arterial transport corridors, and interspersed open vegetation canopy."
        prov = Provenance(
            source="mock",
            worker_url="https://saxophone-fondly-bullish.ngrok-free.dev/",
            fallback=True,
            fallback_reason="EarthDial remote worker unavailable (Kaggle venv update pending)",
            model_id="earthdial-4b-ms",
            model_name="EarthDial-4B-MS",
            model_version="4B-MS",
            sensor="Multispectral Satellite",
            dataset_ids=["Sentinel-2 L2A"],
            pipeline="Mock Specialist Adapter / EarthDial-4B-MS",
            notes="Mock execution adapter used while GPU worker environment is updated.",
        )
        metrics = [
            MetricItem(label="VLM Visual Confidence", value="89.2", unit="%"),
            MetricItem(label="Vision Language Model", value="EarthDial-4B-MS", unit="VLM"),
            MetricItem(label="Identified Classes", value="Built-up, Vegetation, Water", unit="classes"),
        ]
        return NormalizedResult(
            query=query,
            analysis_type="image_understanding",
            aoi=aoi_obj,
            location={"name": aoi_obj.name, "latitude": lat, "longitude": lon},
            provenance=prov,
            key_finding=key_finding,
            scientific_explanation=key_finding,
            metrics=metrics,
            observations=[
                f"Major land-cover in {name} is characterized by dense built-up zones (62%), canopy vegetation (24%), and road networks.",
                "Multispectral bands highlight distinct spectral reflectance separating impervious surfaces from vegetative buffer zones.",
            ],
            visualization_required=False,
            visualization_type="none",
            conversational_mode="answer",
            confidence=0.892,
            audit_trace=[
                {
                    "stage": "model_execution",
                    "name": "EarthDial-4B-MS (Mock Adapter)",
                    "status": "completed",
                    "duration_ms": 150,
                    "details": "Mock execution adapter evaluated while remote worker is offline.",
                }
            ],
        )

    # Prithvi EO 2.0 / temporal change default
    key_finding = f"Prithvi-EO-2.0 temporal change detection over {name} indicates 14.82% surface modification across the monitored observation period."
    prov = Provenance(
        source="mock",
        worker_url="https://saxophone-fondly-bullish.ngrok-free.dev/",
        fallback=True,
        fallback_reason="Prithvi-EO-2.0 remote worker unavailable (Kaggle filename date update pending)",
        model_id="prithvi-eo-2.0",
        model_name="Prithvi-EO-2.0",
        model_version="2.0-300M",
        sensor="Sentinel-2 MSI",
        dataset_ids=["Sentinel-2 L2A"],
        pipeline="Mock Specialist Adapter / Prithvi-EO-2.0 ViT",
        notes="Mock execution adapter used while remote worker tempfile dates are updated.",
    )
    metrics = [
        MetricItem(label="Detected Surface Change", value="14.82", unit="%"),
        MetricItem(label="Changed Pixels", value="38,420 / 259,200", unit="px"),
        MetricItem(label="Model Confidence", value="92.4", unit="%"),
    ]
    time_series = [
        TimeSeriesPoint(date="2018-01-26", value=0.48, metric_name="mean_ndvi", label="Baseline NDVI"),
        TimeSeriesPoint(date="2020-04-16", value=0.44, metric_name="mean_ndvi", label="Intermediate"),
        TimeSeriesPoint(date="2022-07-20", value=0.41, metric_name="mean_ndvi", label="Intervention"),
        TimeSeriesPoint(date="2024-09-23", value=0.38, metric_name="mean_ndvi", label="Current Period"),
    ]
    return NormalizedResult(
        query=query,
        analysis_type="temporal_change",
        aoi=aoi_obj,
        location={"name": aoi_obj.name, "latitude": lat, "longitude": lon},
        provenance=prov,
        key_finding=key_finding,
        scientific_explanation=key_finding,
        metrics=metrics,
        time_series=time_series,
        visualization_required=True,
        visualization_type="spatial",
        conversational_mode="earth_analysis",
        confidence=0.924,
        audit_trace=[
            {
                "stage": "model_execution",
                "name": "Prithvi-EO-2.0 (Mock Adapter)",
                "status": "completed",
                "duration_ms": 210,
                "details": "Mock execution adapter evaluated while remote worker is offline.",
            }
        ],
    )
