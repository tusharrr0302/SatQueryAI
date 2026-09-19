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
    source: str = "mock"  # "mock" | "worker"
    worker_url: Optional[str] = None
    fallback: bool = False
    model_id: str
    model_name: str
    dataset_ids: List[str]
    acquisition_dates: Optional[str] = None
    pipeline: str = "ATS / LangGraph"


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
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    before_image_url: Optional[str] = None
    after_image_url: Optional[str] = None
    aoi_bbox: List[float] = Field(default_factory=list)
    confidence: Optional[float] = None
    confidence_level: Optional[str] = None
    audit_trace: List[AuditTraceStage] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

