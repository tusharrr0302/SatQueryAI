from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, model_validator
import uuid
from datetime import datetime
from app.schemas.evidence import EvidenceItem, PresentationPlan


class ConversationalMode(str, Enum):
    ANSWER = "answer"
    EARTH_ANALYSIS = "earth_analysis"
    TEMPORAL_CHANGE = "temporal_change"
    CROSS_MODAL = "cross_modal"
    IMAGE_UNDERSTANDING = "image_understanding"
    COMPARISON = "comparison"
    INVESTIGATION = "investigation"
    VISUALIZATION = "visualization"


class VisualizationType(str, Enum):
    NONE = "none"
    SPATIAL = "spatial"
    TEMPORAL = "temporal"
    MULTIMODAL = "multimodal"
    IMAGE_EVIDENCE = "image_evidence"
    COMPARISON = "comparison"
    INVESTIGATION = "investigation"


class VisualizationGateSpec(BaseModel):
    visualization_required: bool = False
    visualization_reason: Optional[str] = None
    visualization_type: str = "none"


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


class MetricSemanticType(str, Enum):
    CROSS_MODAL_ALIGNMENT = "cross_modal_alignment"
    MODEL_CONFIDENCE = "model_confidence"
    CLASSIFICATION_CONFIDENCE = "classification_confidence"
    DATA_QUALITY = "data_quality"
    FLOOD_AREA = "flood_area"
    FLOOD_PROBABILITY = "flood_probability"
    AFFECTED_AREA = "affected_area"
    CHANGE_PERCENTAGE = "change_percentage"
    CHANGED_PIXELS = "changed_pixels"
    NDVI = "ndvi"
    NDWI = "ndwi"
    NDMI = "ndmi"
    SAR_BACKSCATTER = "sar_backscatter"
    SAR_RATIO = "sar_ratio"
    ELEVATION = "elevation"
    SLOPE = "slope"
    ASPECT = "aspect"
    VEGETATION_AREA = "vegetation_area"
    LAND_COVER_AREA = "land_cover_area"
    TEMPORAL_OBSERVATION = "temporal_observation"
    OTHER_VERIFIED_MEASUREMENT = "other_verified_measurement"


class DataAvailabilityStatus(str, Enum):
    READY = "ready"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    NOT_REQUESTED = "not_requested"
    NOT_COMPUTED = "not_computed"
    NOT_APPLICABLE = "not_applicable"


class DataProductAvailability(BaseModel):
    product_id: str
    title: str = ""
    label: Optional[str] = None
    status: DataAvailabilityStatus
    reason_code: Optional[str] = None
    human_reason: Optional[str] = None
    retryable: bool = False
    source: Optional[str] = None
    attempted_at: Optional[str] = None
    technical_details: Optional[Dict[str, Any]] = None


class MetricItem(BaseModel):
    id: Optional[str] = None
    label: str
    value: Union[str, float, int]
    unit: Optional[str] = None
    semantic_type: Optional[MetricSemanticType] = None
    source_model: Optional[str] = None
    source_dataset: Optional[str] = None
    acquisition_time: Optional[str] = None
    interpretation: Optional[str] = None
    confidence_type: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None
    change: Optional[str] = None
    trend: Optional[str] = None  # "increase" | "decrease" | "stable"
    metric_id: Optional[str] = None
    source: Optional[str] = None
    source_type: Optional[str] = None
    calculation: Optional[str] = None
    input_assets: Optional[List[str]] = None
    model_id: Optional[str] = None


class TimeSeriesPoint(BaseModel):
    date: str
    value: Optional[float] = None
    metric_name: str = "mean_ndvi"
    unit: Optional[str] = None
    label: Optional[str] = None
    semantic_type: Optional[MetricSemanticType] = None
    is_missing: bool = False
    missing_reason: Optional[str] = None


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
    source: str = "mock"  # "remote_worker" | "local_model" | "deterministic" | "live" | "mock" | "user_data" | "unavailable"
    worker_url: Optional[str] = None
    fallback: bool = False
    fallback_reason: Optional[str] = None
    model_id: str
    model_name: str
    model_version: Optional[str] = None
    sensor: Optional[str] = None
    acquisition_time: Optional[str] = None
    algorithm: Optional[str] = None
    dataset_ids: List[str]
    acquisition_dates: Optional[str] = None
    pipeline: str = "ATS / LangGraph"
    discovery_provider: Optional[str] = "Planetary Computer / Copernicus"
    processing_provider: Optional[str] = "remote_worker"
    notes: Optional[str] = None
    execution_status: str = "success"  # "success" | "unavailable" | "failed" | "fallback"

    @model_validator(mode="before")
    @classmethod
    def validate_provenance_contract_before(cls, data: Any) -> Any:
        if isinstance(data, dict):
            src = data.get("source")
            fb = data.get("fallback")
            # source in ("mock", "mock_fallback") iff fallback == True
            if src in ("mock", "mock_fallback"):
                if fb is False:
                    raise ValueError(f"Provenance integrity violation: source cannot be '{src}' when fallback is False")
                data["fallback"] = True
            elif fb is True and src not in ("mock", "mock_fallback"):
                raise ValueError("Provenance integrity violation: fallback=True is only valid when source is 'mock' or 'mock_fallback'")
        return data

    @model_validator(mode="after")
    def validate_provenance_integrity(self) -> "Provenance":
        # Section 2 & 15 Contract:
        # If source in ("mock", "mock_fallback"), fallback MUST be true
        if self.source in ("mock", "mock_fallback"):
            if not self.fallback:
                raise ValueError(f"Provenance integrity violation: source cannot be '{self.source}' when fallback is False")
        # If source == "remote_worker", fallback MUST be false
        if self.source == "remote_worker":
            if self.fallback:
                raise ValueError("Provenance integrity violation: source cannot be 'remote_worker' when fallback is True")
            if not self.worker_url:
                raise ValueError("Provenance integrity violation: worker_url must exist when source is 'remote_worker'")
        # If execution_status indicates failure or unavailability, source cannot be remote_worker
        if self.execution_status in ("unavailable", "failed") and self.source == "remote_worker":
            raise ValueError(f"Provenance integrity violation: source cannot be 'remote_worker' when execution_status is '{self.execution_status}'")
        return self



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
    dataset_name: Optional[str] = None
    model_name: Optional[str] = None
    date: Optional[str] = None
    resolution: Optional[str] = None


class LayerAccess(BaseModel):
    is_private: bool = False
    user_id: Optional[str] = None
    asset_id: Optional[str] = None


class DataLayerSpec(BaseModel):
    layer_id: str
    type: str  # "aoi" | "imagery" | "raster" | "polygon" | "change_detection" | "flood_extent" | "heatmap" | "3d_surface" | "3d_extruded_polygon" | "point_cloud" | "point" | "user_asset"
    title: str
    description: str
    role: Optional[str] = "primary_analysis"  # "primary_analysis" | "study_area" | "comparison" | "reference" | "boundary" | "context" | "evidence"
    purpose: Optional[str] = None
    dataset: Optional[str] = None
    model: Optional[str] = None
    date: Optional[str] = None
    resolution: Optional[str] = None
    source: LayerSource
    spatial: LayerSpatial
    style: LayerStyle = Field(default_factory=LayerStyle)
    legend: Optional[LayerLegend] = None
    temporal: Optional[LayerTemporal] = None
    provenance: LayerProvenance
    access: LayerAccess = Field(default_factory=LayerAccess)
    visible: Optional[bool] = True


class VisualizationExplanation(BaseModel):
    # Factual structured metadata (Section Part 8)
    title: Optional[str] = None
    what_it_shows: Optional[str] = None
    data_source: Optional[str] = None
    variables: List[str] = Field(default_factory=list)
    how_to_read: Optional[str] = None
    why_it_matters: Optional[str] = None
    limitations: Optional[str] = None

    # Extended facets
    visual_form: Optional[str] = None
    what_this_represents: Optional[str] = None
    primary_metric: Optional[str] = None
    baseline_comparison: Optional[str] = None
    palette_and_scale: Optional[str] = None
    critical_thresholds: Optional[str] = None
    spatial_context: Optional[str] = None
    provenance_and_sensor: Optional[str] = None
    visual_inferences: Optional[str] = None
    plain_language_summary: Optional[str] = None
    technical_summary: Optional[str] = None

    # Backwards compatibility fields
    what_you_see: Optional[str] = None
    why_chosen: Optional[str] = None
    key_observation: Optional[str] = None
    units: Optional[str] = ""
    temporal_range: Optional[str] = None
    dataset: Optional[str] = None
    model: Optional[str] = None


class VisualizationDataContract(BaseModel):
    """Normalized visualization data contract (Section Part 16)."""
    visualization_id: str
    status: str = "ready"  # "ready" | "unavailable"
    source: Optional[str] = None
    reason: Optional[str] = None
    explanation: Optional[VisualizationExplanation] = None
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    coordinates: List[List[float]] = Field(default_factory=list)  # [[lon, lat, val], ...] for 3D point cloud
    surface_grid: Optional[List[List[float]]] = None  # 2D matrix for 3D surface
    echarts_option: Optional[Dict[str, Any]] = None
    layer_spec: Optional[DataLayerSpec] = None
    accepted_semantic_types: List[str] = Field(default_factory=list)

    class Config:
        extra = "allow"


class CameraSpec(BaseModel):
    action: str = "fly_to_aoi"
    destination: List[float] = Field(default_factory=list)
    name: Optional[str] = None
    bbox: Optional[List[float]] = None
    altitude: Optional[float] = 350000.0
    pitch: Optional[float] = -85.0
    heading: Optional[float] = 0.0
    roll: Optional[float] = 0.0


class VisualizationPlan(BaseModel):
    primary_visualization: Dict[str, Any]
    secondary_visualizations: List[Dict[str, Any]] = Field(default_factory=list)
    active_layers: List[DataLayerSpec] = Field(default_factory=list)
    layers: List[DataLayerSpec] = Field(default_factory=list)
    camera: Optional[Union[CameraSpec, Dict[str, Any]]] = None
    legend: Optional[Dict[str, Any]] = None
    explanation: Optional[VisualizationExplanation] = None


class WebEvidenceItem(BaseModel):
    id: Optional[str] = None
    title: str
    snippet: str
    source: str
    source_domain: Optional[str] = None
    attribution: Optional[str] = None
    url: Optional[str] = None
    published_date: Optional[str] = None
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_reference_photo: bool = False


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
    observations: List[str] = Field(default_factory=list)
    raster_outputs: List[Dict[str, Any]] = Field(default_factory=list)
    vector_outputs: List[Dict[str, Any]] = Field(default_factory=list)
    detections: List[Dict[str, Any]] = Field(default_factory=list)
    classifications: List[Dict[str, Any]] = Field(default_factory=list)
    change_regions: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    image_comparison: Optional[SatelliteImagePair] = None
    visualization: Optional[VisualizationSpec] = None
    visualizations: List[Dict[str, Any]] = Field(default_factory=list)
    visualization_plan: Optional[VisualizationPlan] = None
    layers: List[DataLayerSpec] = Field(default_factory=list)
    time_series: List[TimeSeriesPoint] = Field(default_factory=list)
    before_image_url: Optional[str] = None
    after_image_url: Optional[str] = None
    aoi_bbox: List[float] = Field(default_factory=list)
    confidence: Optional[float] = None
    confidence_level: Optional[str] = None
    audit_trace: List[AuditTraceStage] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)
    ai_mode: Optional[str] = "auto"
    conversational_mode: Optional[str] = "answer"
    visualization_required: bool = False
    visualization_reason: Optional[str] = None
    visualization_type: Optional[str] = "none"
    web_evidence: Optional[List[WebEvidenceItem]] = None
    presentation_plan: Optional[PresentationPlan] = None
    evidence_items: List[EvidenceItem] = Field(default_factory=list)
    analysis_summary: Optional[str] = None
    measurements: List[Dict[str, Any]] = Field(default_factory=list)
    data_sources: List[str] = Field(default_factory=list)
    models_used: List[str] = Field(default_factory=list)
    surface_grid: Optional[List[List[float]]] = None  # 2D height/index matrix for 3D surfaces
    temporal_observations: List[Dict[str, Any]] = Field(default_factory=list)
    data_availability: List[DataProductAvailability] = Field(default_factory=list)
    processing_provider: Optional[str] = None
    discovery_provider: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

