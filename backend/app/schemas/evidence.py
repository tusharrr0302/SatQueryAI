from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class EvidenceType(str, Enum):
    OPTICAL_SCENE = "optical_scene"
    OPTICAL_BASELINE = "optical_baseline"
    OPTICAL_FALSE_COLOR = "optical_false_color"
    SAR_VV = "sar_vv"
    SAR_VH = "sar_vh"
    SAR_RATIO = "sar_ratio"
    NDVI = "ndvi"
    NDWI = "ndwi"
    CHANGE_MAP = "change_map"
    FLOOD_EXTENT = "flood_extent"
    TIME_SERIES = "time_series"
    COMPARISON = "comparison"
    SAR_CHANGE = "sar_change"
    DIFFERENCE = "difference"
    TERRAIN_DEM = "terrain_dem"


class EvidenceItem(BaseModel):
    id: str = Field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:8]}")
    type: EvidenceType
    title: str
    description: Optional[str] = None
    sensor: str = "Sentinel-2 MSI"
    dataset_id: str = "sentinel-2-l2a"
    processing_level: str = "L2A"
    acquisition_date: str
    aoi_name: Optional[str] = None
    aoi: Optional[Dict[str, Any]] = None
    bbox: List[float] = Field(default_factory=list)  # [west, south, east, north]
    rendering: str = "true_color"  # "true_color", "false_color", "sar_vv", "sar_vh", "sar_ratio", "sar_change", "ndvi", "ndwi", "elevation", etc.
    image_url: Optional[str] = None  # None when rendering failed, timed out, or quota exceeded
    resolution_m: float = 10.0
    cloud_cover: Optional[float] = None
    coverage_type: str = "single_scene"  # "single_scene" | "AOI mosaic"
    asset_ids: List[str] = Field(default_factory=list)
    layer_type: Optional[str] = None  # "optical" | "sar_vv" | "sar_vh" | "ndwi" | "sar_change" | "flood_extent" | "terrain"
    source: str = "copernicus"  # "copernicus", "planetary_computer", "remote_worker"
    cesium_layer_id: Optional[str] = None
    role: Optional[str] = None  # "current", "baseline", "sar_vv", "sar_vh", "feature", "terrain"
    baseline_role: Optional[str] = None  # "pre_event_baseline" | "temporal_baseline" | "unavailable"
    available: bool = True  # Set to False if provider fails or cannot render authentic imagery
    status: str = "available"  # "available" | "unavailable"
    surface_grid: Optional[List[List[float]]] = None  # Sampled authentic raster grid
    reason: Optional[str] = None  # e.g. "COPERNICUS_RENDER_FAILED"
    message: Optional[str] = None  # Human-readable status/failure description
    error_message: Optional[str] = None  # Preserved provider error or limitation reason
    generated_by: Optional[str] = None  # e.g. "copernicus_evalscript_ndvi", "prithvi_remote_worker"
    input_assets: List[str] = Field(default_factory=list)
    artifact: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MethodInfo(BaseModel):
    data: List[str] = Field(default_factory=lambda: ["Sentinel-1 GRD", "Sentinel-2 L2A"])
    model: str = "CLOSP"
    primary_model: Optional[str] = None
    supporting_model: Optional[str] = None
    discovery_provider: str = "Planetary Computer"
    imagery_rendering: str = "Copernicus Data Space"
    processing_provider: str = "Remote GPU Worker"
    source: str = "remote_worker"


class PresentationPlan(BaseModel):
    id: str = Field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    title: str = "Satellite Earth Observation Assessment"
    summary: Optional[str] = None
    evidence_items: List[EvidenceItem] = Field(default_factory=list)
    primary_evidence_id: Optional[str] = None
    baseline_evidence_id: Optional[str] = None
    has_baseline: bool = False
    baseline_missing_reason: Optional[str] = None
    baseline_role: Optional[str] = None  # "pre_event_baseline" | "temporal_baseline" | "unavailable"
    baseline_title: Optional[str] = None  # "Earlier temporal baseline" vs "Pre-event baseline"
    baseline_note: Optional[str] = None
    coverage_type: Optional[str] = None  # "AOI mosaic" | "single_scene"
    change_analysis: Optional[str] = None
    method: MethodInfo = Field(default_factory=MethodInfo)
    limitations: List[str] = Field(default_factory=list)
    key_measurements: List[Dict[str, Any]] = Field(default_factory=list)

