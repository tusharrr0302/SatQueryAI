"""
app/schemas/responses.py
─────────────────────────────────────────────────────────────────────────────
Pydantic models for:
  - Tool output (what each specialist tool returns)
  - API response (what the chat endpoint returns to the caller)
  - Visualization payload (structured geospatial data for the Cesium frontend)

These are strict contracts. If a tool changes what it returns, update
the schema here so the orchestrator and API both stay in sync.

VISUALIZATION CONTRACT:
  The frontend (Svelte + CesiumJS) should be able to read the 'visualization'
  field in AnalysisResponse and render:
    - 2D map layers (GeoJSON polygons, raster overlays, heatmaps)
    - 3D scene data (terrain, volumetric data)
    - Depth profiles (ocean/atmosphere vertical slices)
    - Temporal data (timeline slider, before/after comparisons)

  The backend does NOT render Cesium. It provides the data structures.
  The frontend decides how to render them.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Tool Output Schemas
# Every tool returns one of these structured results.
# The orchestrator serialises this and sends it back to GPT-OSS as the
# tool_result message so GPT-OSS can synthesise the final answer.
# ─────────────────────────────────────────────────────────────────────────────

class ToolResult(BaseModel):
    """
    The standard output envelope for every tool.

    Fields:
      tool        — which tool produced this result
      model       — which specialist model was used
      mode        — "mock" or "real" so the LLM is never misled
      answer      — the plain-text description / analysis from the model
      confidence  — model confidence score (null if not provided by the model)
      artifacts   — any extra outputs (bounding boxes, masks, GeoJSON, etc.)
      error       — filled in only if the tool failed
    """

    tool: str = Field(..., description="Name of the tool that ran")
    model: str = Field(..., description="Name of the specialist model used")
    mode: str = Field(
        ...,
        description="'mock' or 'real' — always honest about what ran",
    )
    answer: str = Field(..., description="Plain-text analysis result")

    # Use None/null — never invent a confidence score
    confidence: Optional[float] = Field(
        default=None,
        description="Model confidence (null if not provided by the model)",
    )

    # Structured geospatial outputs: SatelliteDataset objects, GeoJSON, masks
    artifacts: list[Any] = Field(
        default_factory=list,
        description="Extra structured outputs (SatelliteDatasets, masks, boxes, GeoJSON, etc.)",
    )

    # Only set when something went wrong inside the tool
    error: Optional[str] = Field(
        default=None,
        description="Error description if the tool failed",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Visualization Payload
# Structured geospatial data for the Cesium/map frontend.
# All fields are optional — not every analysis produces every type.
# ─────────────────────────────────────────────────────────────────────────────

class MapLayer(BaseModel):
    """
    A single renderable layer for the 2D/3D map frontend.

    type="geojson"  → data field contains GeoJSON FeatureCollection
    type="raster"   → url field points to a GeoTIFF/tile server
    type="heatmap"  → data contains point observations with values
    type="wms"      → url is a WMS endpoint with optional params
    """
    id: str = Field(..., description="Unique layer identifier")
    type: str = Field(..., description="Layer type: 'geojson', 'raster', 'heatmap', 'wms'")
    label: str = Field(default="", description="Human-readable layer name")
    data: Optional[Any] = Field(default=None, description="GeoJSON FeatureCollection or point array")
    url: Optional[str] = Field(default=None, description="Remote tile/raster URL")
    opacity: float = Field(default=0.8, description="Layer opacity 0–1")
    visible: bool = Field(default=True)
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra rendering hints (colormap, min/max values, etc.)",
    )


class VolumeData(BaseModel):
    """
    3D volumetric scientific data (e.g. ocean temperature cube, atmosphere slice).
    Allows the frontend to construct a volumetric 3D scene in Cesium.
    """
    bbox: list[float] = Field(description="[min_lon, min_lat, max_lon, max_lat]")
    dimensions: list[int] = Field(description="[x_size, y_size, z_size]")
    coordinates: dict[str, Any] = Field(
        default_factory=dict,
        description="Coordinate arrays: {'lon': [...], 'lat': [...], 'depth': [...]}",
    )
    variable: str = Field(..., description="Scientific variable name (e.g. 'temperature')")
    unit: str = Field(default="", description="Physical unit (e.g. '°C', 'PSU', 'mg/m³')")
    values: list[Any] = Field(default_factory=list, description="Flattened value array (z-first)")
    depth_range: list[float] = Field(default_factory=list, description="[min_depth_m, max_depth_m]")
    time: Optional[str] = Field(default=None, description="ISO 8601 timestamp")


class ProfileData(BaseModel):
    """
    Vertical profile data (ocean CTD cast, atmosphere sounding, etc.).
    Allows the frontend to render depth/altitude slices and profile viewers.
    """
    instrument: str = Field(default="", description="Instrument type (e.g. 'CTD', 'Argo float')")
    location: dict[str, float] = Field(
        description="{'lat': 0.0, 'lon': 0.0}",
    )
    depth: list[float] = Field(default_factory=list, description="Depth values in metres")
    variables: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Variable arrays keyed by name: {'temperature': [...], 'salinity': [...]}",
    )
    time: Optional[str] = Field(default=None, description="ISO 8601 observation timestamp")


class PointObservation(BaseModel):
    """A single geolocated observation (buoy, station, detection, etc.)."""
    lat: float
    lon: float
    value: Optional[float] = None
    label: Optional[str] = None
    time: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)


class VisualizationPayload(BaseModel):
    """
    Complete visualization payload returned in AnalysisResponse.

    The frontend reads this and decides what to render.
    All fields are optional — only populate fields relevant to the analysis.

    DO NOT fabricate geospatial data. If an analysis doesn't produce
    specific coordinates or measurements, leave those fields empty.
    """
    layers: list[MapLayer] = Field(
        default_factory=list,
        description="2D/3D map layers (GeoJSON, rasters, heatmaps)",
    )
    rasters: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Raster overlay descriptors with URL and band mapping",
    )
    vectors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="GeoJSON FeatureCollections for polygon/polyline overlays",
    )
    points: list[PointObservation] = Field(
        default_factory=list,
        description="Point observations (stations, detections, samples)",
    )
    profiles: list[ProfileData] = Field(
        default_factory=list,
        description="Vertical profiles (ocean/atmosphere depth slices)",
    )
    volumes: list[VolumeData] = Field(
        default_factory=list,
        description="3D volumetric data (ocean cubes, atmosphere fields)",
    )
    temporal_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Temporal context for timeline rendering: "
            "{'start': '2020-01-01', 'end': '2024-12-31', 'timestamps': [...], "
            "'before': '...', 'after': '...'}"
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Analysis Result Metadata
# ─────────────────────────────────────────────────────────────────────────────

class AnalysisMetadata(BaseModel):
    """Summary of what analysis was performed."""
    type: str = Field(default="", description="Analysis type (e.g. 'change_detection', 'vqa', 'sar_fusion')")
    tool: str = Field(default="", description="Tool that performed the analysis")
    model: str = Field(default="", description="Specialist model used")
    confidence: Optional[float] = Field(default=None)
    mode: str = Field(default="mock", description="'mock' or 'real'")


class SourceMetadata(BaseModel):
    """Geospatial provenance of the input data."""
    sensor: str = Field(default="", description="Sensor type (optical, SAR, thermal)")
    platform: str = Field(default="", description="Satellite platform name")
    acquisition_time: Optional[str] = Field(default=None)
    acquisition_time_t2: Optional[str] = Field(default=None, description="Second acquisition for change detection")
    bbox: list[float] = Field(default_factory=list, description="[min_lon, min_lat, max_lon, max_lat]")
    crs: str = Field(default="EPSG:4326")
    product_id: Optional[str] = Field(default=None)


class DetectionResults(BaseModel):
    """
    Structured analysis outputs for frontend rendering.
    Only populate fields that actually have data.
    """
    detections: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Object detection results [{label, bbox, confidence, geometry}]",
    )
    bounding_boxes: list[list[float]] = Field(
        default_factory=list,
        description="Detection bounding boxes [[x1,y1,x2,y2], ...]",
    )
    polygons: list[dict[str, Any]] = Field(
        default_factory=list,
        description="GeoJSON Polygon or MultiPolygon features",
    )
    statistics: dict[str, Any] = Field(
        default_factory=dict,
        description="Quantitative results: affected_area_km2, change_pct, etc.",
    )
    change_mask: Optional[dict[str, Any]] = Field(
        default=None,
        description="Binary or multi-class change segmentation mask (GeoJSON or URL)",
    )
    classifications: dict[str, float] = Field(
        default_factory=dict,
        description="Class label → area/confidence mapping",
    )


# ─────────────────────────────────────────────────────────────────────────────
# API Response
# ─────────────────────────────────────────────────────────────────────────────

class ToolCallRecord(BaseModel):
    """
    A log of a single tool call made during a chat turn.
    Returned in the API response so callers can see what happened.
    """
    tool_name: str
    arguments: dict[str, Any]
    result: ToolResult


class ChatResponse(BaseModel):
    """
    The full response returned by POST /api/v1/chat.

    Fields:
      answer       — the final natural-language answer from GPT-OSS
      tool_calls   — list of every tool call made (for transparency/debugging)
      artifacts    — aggregated artifacts from all tools
      model        — the orchestrator LLM model name
      request_id   — unique identifier for this request (for log correlation)
      error        — filled in only when the entire request fails
    """

    answer: str = Field(
        ...,
        description="GPT-OSS's final synthesised natural-language answer",
    )
    tool_calls: list[ToolCallRecord] = Field(
        default_factory=list,
        description="All tool calls made during this turn (for transparency)",
    )
    artifacts: list[Any] = Field(
        default_factory=list,
        description="Aggregated artifacts from all tool calls",
    )
    model: str = Field(
        ...,
        description="The orchestrator model that produced the answer",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Unique request identifier for log correlation",
    )
    visualization: Optional[VisualizationPayload] = Field(
        default=None,
        description="Structured geospatial data for frontend rendering",
    )
    analysis: Optional[AnalysisMetadata] = Field(
        default=None,
        description="Metadata about the analysis performed",
    )
    source: Optional[SourceMetadata] = Field(
        default=None,
        description="Geospatial provenance of the input data",
    )
    results: Optional[DetectionResults] = Field(
        default=None,
        description="Structured analysis outputs (detections, polygons, statistics)",
    )
    error: Optional[str] = Field(
        default=None,
        description="High-level error if the request could not be completed",
    )


class ErrorResponse(BaseModel):
    """Used when an HTTP error response needs to be returned."""
    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None
