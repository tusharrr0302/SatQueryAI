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
    filename: str
    file_path: str
    file_size_bytes: int
    preview_url: str
    thumbnail_url: Optional[str] = None
    created_at: str
    profile: DataProfile


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
