from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class BandInfo(BaseModel):
    index: int
    name: str = "Band"
    description: Optional[str] = None
    wavelength_um: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    std: Optional[float] = None


class Dimensions(BaseModel):
    width: int
    height: int
    bands: int


class DataProfile(BaseModel):
    asset_id: str
    filename: str
    format: str = "GeoTIFF"
    dimensions: Dimensions
    dtype: str
    crs: Optional[str] = None
    crs_wkt: Optional[str] = None
    resolution: Optional[List[float]] = None
    bounds: Optional[List[float]] = None  # [minx, miny, maxx, maxy] in WGS84
    center: Optional[Dict[str, float]] = None  # {"latitude": lat, "longitude": lon}
    nodata: Optional[float] = None
    modality: str = "optical"  # optical, multispectral, hyperspectral, sar, dem, etc.
    sensor: Optional[str] = None
    platform: Optional[str] = None
    acquisition_date: Optional[str] = None
    bands: List[BandInfo] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    quality: Dict[str, Any] = Field(default_factory=dict)
    possible_analyses: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class DataAsset(BaseModel):
    asset_id: str
    filename: Optional[str] = None
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = 0
    preview_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: Optional[str] = None
    profile: Optional[DataProfile] = None

    # Satellite provider discovery properties (Section 14)
    id: Optional[str] = None  # alias for asset_id
    dataset_id: Optional[str] = None  # e.g. "sentinel-2" or "sentinel-1"
    provider: Optional[str] = None  # e.g. "planetary_computer", "copernicus", "mock"
    sensor: Optional[str] = None  # e.g. "Sentinel-2 MSI", "Sentinel-1 C-SAR"
    acquisition_time: Optional[str] = None  # ISO timestamp
    geometry: Optional[Dict[str, Any]] = None
    bbox: Optional[List[float]] = None  # [min_lon, min_lat, max_lon, max_lat]
    cloud_cover: Optional[float] = None  # percentage
    bands: List[str] = Field(default_factory=list)
    spatial_resolution: Optional[float] = None  # meters
    crs: Optional[str] = "EPSG:4326"
    source_url: Optional[str] = None
    download_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class UploadAssetResponse(BaseModel):
    asset_id: str
    profile: DataProfile
    preview_url: str
    thumbnail_url: Optional[str] = None
    message: str = "Data asset successfully inspected and registered."


class AssetRelationship(BaseModel):
    relationship_type: str  # "temporal_pair", "multimodal_pair", "spatial_overlap", "incompatible"
    asset_a_id: str
    asset_b_id: str
    compatible: bool
    summary: str
    possible_analyses: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
