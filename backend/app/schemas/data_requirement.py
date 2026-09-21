"""
backend/app/schemas/data_requirement.py
─────────────────────────────────────────────────────────────────────────────
Canonical Pydantic models for SatQuery AI's Data Discovery & Acquisition Layer.
Specifies deterministic requirements derived from AnalysisRequest + ToolPlan.
"""
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field

from app.schemas.data_asset import DataAsset


AcquisitionStrategy = Literal[
    "single",
    "temporal",
    "paired",
    "multitemporal",
    "sar_optical_pair",
]

DataDiscoveryStatus = Literal[
    "success",
    "needs_data",
    "unsupported_data_period",
    "no_assets_found",
    "missing_temporal_slot",
    "cloud_threshold_failed",
    "no_valid_scene",
    "acquisition_failed",
    "preprocessing_failed",
    "provider_unavailable",
    "needs_clarification",
]


class TemporalWindow(BaseModel):
    slot: str  # e.g. "2016", "2017" or "t1", "t2"
    start: str  # YYYY-MM-DD
    end: str  # YYYY-MM-DD
    target_date: Optional[str] = None
    label: Optional[str] = None
    period_type: str = "annual"  # "annual" | "quarterly" | "monthly" | "custom"


class TemporalObservationRecord(BaseModel):
    """
    Structured, authentic observation record for a discrete temporal window.
    Preserves all provenance without fabrication; explicitly records unavailable status with reason.
    """
    slot: str  # e.g. "2016", "2017", "t1"
    period: str  # e.g. "2016", "2017-Q2", "2020-07"
    status: str = "ready"  # "ready" | "unavailable"
    reason: Optional[str] = None  # e.g. "NO_VALID_SCENE", "CLOUD_THRESHOLD_FAILED", "AOI_NOT_COVERED"
    explanation: Optional[str] = None
    date: Optional[str] = None  # ISO acquisition date e.g. "2016-07-24"
    asset_id: Optional[str] = None
    sensor: Optional[str] = "Sentinel-2 MSI"
    dataset_id: Optional[str] = "sentinel-2-l2a"
    cloud_cover: Optional[float] = None
    spatial_resolution: Optional[float] = 10.0
    provider: Optional[str] = None
    source_url: Optional[str] = None
    tile_id: Optional[str] = None
    coverage_type: Optional[str] = "single_scene"  # "single_scene" | "AOI_mosaic"
    tile_count: Optional[int] = 1
    bands: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    selected: bool = False

    class Config:
        extra = "allow"


class DataRequirement(BaseModel):
    """
    Authoritative backend representation of the satellite data constraints
    needed to execute a ToolPlan for an AOI.
    """
    aoi_name: Optional[str] = None
    bbox: Optional[List[float]] = None  # [min_lon, min_lat, max_lon, max_lat]
    geometry: Optional[Any] = None  # GeoJSON dict or coordinate polygon

    temporal: Dict[str, Any] = Field(default_factory=dict)
    # e.g. {"start": "2020-01-01", "end": "2025-01-01", "relative_period": "5_years", "resolution": "annual"}

    modalities: List[str] = Field(default_factory=lambda: ["optical"])
    preferred_datasets: List[str] = Field(default_factory=lambda: ["sentinel-2"])

    spatial_resolution: Optional[str] = "10m"
    cloud_cover_max: float = 20.0  # Percentage 0.0 - 100.0

    required_bands: List[str] = Field(default_factory=list)
    # Optical: ["B02", "B03", "B04", "B08"]
    # SAR: ["VV", "VH"]

    temporal_count: Optional[int] = None  # e.g. 10 for decadal series, 4 for Prithvi stack, 2 for bitemporal
    temporal_windows: List[TemporalWindow] = Field(default_factory=list)
    temporal_frequency: Optional[str] = "annual"  # "annual" | "quarterly" | "monthly" | "event"

    acquisition_strategy: AcquisitionStrategy = "single"
    co_registration_required: bool = False
    max_pair_delta_days: int = 5  # For SAR + optical temporal pairing tolerance

    quality_constraints: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class LocalAsset(BaseModel):
    """
    Acquired or cached local asset on the filesystem, preserving complete provenance,
    original filenames, and acquisition timestamps for specialist models like Prithvi.
    """
    asset_id: str
    dataset_id: str
    provider: str
    acquisition_time: str
    local_path: str
    crs: Optional[str] = None
    bbox: Optional[List[float]] = None
    bands: List[str] = Field(default_factory=list)
    original_filename: str
    sensor: Optional[str] = None
    checksum: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class DataDiscoveryResult(BaseModel):
    """
    Structured outcome of the Data Discovery & Candidate Search phase.
    """
    status: DataDiscoveryStatus = "success"
    requirement: DataRequirement
    datasets: List[Dict[str, Any]] = Field(default_factory=list)
    candidates: List[DataAsset] = Field(default_factory=list)
    selected_assets: List[DataAsset] = Field(default_factory=list)
    temporal_assets: Dict[str, DataAsset] = Field(default_factory=dict)  # {"2016": asset, "2017": asset, ...}
    temporal_observations: List[TemporalObservationRecord] = Field(default_factory=list)
    sar_optical_pair: Optional[Dict[str, DataAsset]] = None  # {"sar": asset, "optical": asset}
    message: Optional[str] = None
    missing_inputs: List[str] = Field(default_factory=list)

    class Config:
        extra = "allow"
