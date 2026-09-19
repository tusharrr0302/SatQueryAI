from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


class Coordinates(BaseModel):
    latitude: float
    longitude: float


class AOIInfo(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    country: Optional[str] = None
    type: str = "Polygon"
    center: Coordinates
    area_km2: float
    bbox: List[float] = Field(default_factory=list)  # [min_lon, min_lat, max_lon, max_lat]
    polygon: List[List[float]] = Field(default_factory=list)  # [[lon, lat], ...]


class MetricItem(BaseModel):
    label: str
    value: str
    change: Optional[str] = None
    trend: Optional[str] = None  # "increase" | "decrease" | "stable"
    unit: Optional[str] = None


class TimeSeriesPoint(BaseModel):
    date: str
    value: float
    metric_name: str = "mean_ndvi"
    unit: Optional[str] = None
    label: Optional[str] = None


class SatelliteImagePair(BaseModel):
    t1_date: str
    t1_url: str
    t1_label: str
    t2_date: str
    t2_url: str
    t2_label: str
    description: Optional[str] = None


class VisualizationSpec(BaseModel):
    type: str  # "3D Surface" | "Change Map" | "Time Series" | "Image Comparison" | "Heatmap" | "Polygon Map"
    title: str
    sub_title: Optional[str] = None
    date_range: Optional[str] = None
    color_map: Optional[str] = "viridis"  # "ndvi" | "thermal" | "diverging" | "viridis"
    legend_min: Optional[float] = -0.2
    legend_max: Optional[float] = 0.8
    legend_unit: Optional[str] = ""
    surface_opacity: float = 0.85
    vertical_exaggeration: float = 2.0
    reverse_depth: bool = False
    surface_grid: Optional[List[List[float]]] = None  # 2D height/index matrix for 3D surface
    timeseries: Optional[List[TimeSeriesPoint]] = None


class AuditTraceStage(BaseModel):
    stage: str
    name: str
    status: str = "completed"  # "pending" | "running" | "completed" | "failed"
    duration_ms: int
    details: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Provenance(BaseModel):
    source: str = "mock"  # "mock" | "worker" | "live" | "user_data"
    worker_url: Optional[str] = None
    fallback: bool = False
    model_id: str
    model_name: str
    dataset_ids: List[str]
    acquisition_dates: Optional[str] = None
    pipeline: str = "ATS / LangGraph"


# ==============================================================================
# CANONICAL GEOSPATIAL DATA-LAYER CONTRACT
# ==============================================================================

class LayerSpatial(BaseModel):
    bounds: List[float] = Field(default_factory=list)  # [west, south, east, north] in WGS84
    center: Optional[Coordinates] = None
    polygon: Optional[List[List[float]]] = None  # [[lon, lat], ...]


class LayerSource(BaseModel):
    type: str  # "geojson" | "image" | "tile" | "user_asset" | "entity_collection"
    url: Optional[str] = None  # Relative URL or endpoint
    format: Optional[str] = None  # "geojson" | "png" | "cog" | "vector"
    data: Optional[Dict[str, Any]] = None  # Inline GeoJSON Feature or FeatureCollection


class LayerStyle(BaseModel):
    opacity: float = 0.85
    color: Optional[str] = None  # CSS fill color (e.g. "rgba(239, 68, 68, 0.35)")
    outline_color: Optional[str] = None  # CSS stroke color (e.g. "#ef4444")
    outline_width: float = 2.0
    color_scale: Optional[str] = None  # "viridis" | "ndvi" | "thermal" | "red" | "amber" | "emerald" | "blue"


class LayerLegendItem(BaseModel):
    label: str
    color: str
    value: Optional[str] = None


class LayerLegend(BaseModel):
    type: str = "continuous"  # "continuous" | "categorical" | "metric_summary"
    title: str
    unit: Optional[str] = ""
    min: Optional[float] = None
    max: Optional[float] = None
    color_scale: Optional[str] = None
    items: Optional[List[LayerLegendItem]] = None


class LayerTemporal(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None
    acquisition_date: Optional[str] = None


class LayerProvenance(BaseModel):
    dataset_id: Optional[str] = None  # e.g., "sentinel-2", "sentinel-1", "user-upload"
    model_id: Optional[str] = None  # e.g., "prithvi-eo-2.0", "terrafm", "deterministic"
    source: str = "mock"  # "mock" | "live" | "user_data"


class LayerAccess(BaseModel):
    is_private: bool = False
    user_id: Optional[str] = None
    asset_id: Optional[str] = None


class DataLayerSpec(BaseModel):
    layer_id: str
    type: str  # "aoi" | "imagery" | "raster" | "polygon" | "change_detection" | "flood_extent" | "heatmap" | "user_asset"
    title: str
    description: str
    source: LayerSource
    spatial: LayerSpatial
    style: LayerStyle = Field(default_factory=LayerStyle)
    legend: Optional[LayerLegend] = None
    temporal: Optional[LayerTemporal] = None
    provenance: LayerProvenance
    access: LayerAccess = Field(default_factory=LayerAccess)


class NormalizedResult(BaseModel):
    result_id: str = Field(default_factory=lambda: f"res_{uuid.uuid4().hex[:10]}")
    query: str
    analysis_type: str
    aoi: AOIInfo
    location: Optional[Dict[str, Any]] = None
    provenance: Provenance
    key_finding: str
    scientific_explanation: str
    metrics: List[MetricItem] = Field(default_factory=list)
    image_comparison: Optional[SatelliteImagePair] = None
    visualization: Optional[VisualizationSpec] = None
    visualizations: List[Dict[str, Any]] = Field(default_factory=list)
    layers: List[DataLayerSpec] = Field(default_factory=list)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    before_image_url: Optional[str] = None
    after_image_url: Optional[str] = None
    aoi_bbox: List[float] = Field(default_factory=list)
    confidence: Optional[float] = None
    confidence_level: Optional[str] = None
    audit_trace: List[AuditTraceStage] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

