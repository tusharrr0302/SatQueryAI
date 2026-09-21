"""
app/schemas/satellite.py
─────────────────────────────────────────────────────────────────────────────
Normalized satellite data schema.

WHY THIS EXISTS:
  Each satellite data provider (Copernicus, USGS, NASA CMR) returns data
  in a different format. The satellite acquisition tools normalize everything
  into this common internal schema before passing results to the orchestrator
  or specialist analysis tools.

  This means the specialist tools (analyze_image, detect_change, etc.) and
  GPT-OSS never need to know whether the image came from Copernicus or USGS.
  They only see the normalized SatelliteDataset.

DATA FLOW:
  Provider API response
       ↓
  Provider-specific parser (in satellite_data.py)
       ↓
  SatelliteDataset (this schema)
       ↓
  Returned in ToolResult.artifacts[]
       ↓
  Passed to specialist analysis tool
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class SatelliteAsset(BaseModel):
    """
    A single band or file asset associated with a satellite product.
    'url' may be a direct download URL, a signed URL, or a local file path.
    """
    band: str = Field(..., description="Band identifier (e.g. 'B04', 'VV', 'B8A')")
    url: str = Field(..., description="Asset URL or local path")
    format: str = Field(default="GeoTIFF", description="File format: GeoTIFF, NetCDF, HDF5, etc.")
    resolution_m: Optional[float] = Field(
        default=None,
        description="Ground sample distance in metres (e.g. 10.0 for Sentinel-2 10m bands)",
    )


class SatelliteDataset(BaseModel):
    """
    Normalized representation of a satellite data product.

    Produced by satellite acquisition tools (fetch_sentinel1, fetch_sentinel2,
    fetch_landsat, fetch_viirs_modis) after normalizing the provider response.

    Consumed by:
      - The orchestrator (injected into tool call arguments)
      - The frontend (via the visualization payload)
      - Preprocessing pipeline
    """

    # ── Provenance ────────────────────────────────────────────────────────────
    source: str = Field(
        ...,
        description="Data source: 'sentinel-1', 'sentinel-2', 'landsat-8', 'landsat-9', 'viirs', 'modis'",
        examples=["sentinel-2"],
    )
    product_id: str = Field(
        ...,
        description="Provider-assigned product identifier",
        examples=["S2A_MSIL2A_20240601T053649_N0510_R005_T44RKR_20240601T092846"],
    )

    # ── Sensor info ───────────────────────────────────────────────────────────
    sensor: str = Field(
        ...,
        description="Sensor type: 'optical', 'sar', 'thermal', 'multispectral'",
        examples=["optical"],
    )
    platform: str = Field(
        default="",
        description="Satellite platform name (e.g. 'Sentinel-2A', 'Landsat-9')",
    )

    # ── Temporal ──────────────────────────────────────────────────────────────
    acquisition_time: str = Field(
        ...,
        description="ISO 8601 acquisition timestamp",
        examples=["2024-06-01T05:36:49Z"],
    )

    # ── Spatial ───────────────────────────────────────────────────────────────
    bbox: list[float] = Field(
        ...,
        description="Bounding box [min_lon, min_lat, max_lon, max_lat] in WGS84",
        examples=[[77.5, 29.0, 80.5, 31.5]],
    )
    crs: str = Field(
        default="EPSG:4326",
        description="Coordinate Reference System (EPSG code)",
        examples=["EPSG:4326"],
    )

    # ── Spectral / data ───────────────────────────────────────────────────────
    bands: list[str] = Field(
        default_factory=list,
        description="List of band identifiers available in this product",
        examples=[["B02", "B03", "B04", "B08"]],
    )
    assets: list[SatelliteAsset] = Field(
        default_factory=list,
        description="Individual band/file assets with download URLs",
    )

    # ── Quality ───────────────────────────────────────────────────────────────
    cloud_cover_pct: Optional[float] = Field(
        default=None,
        description="Cloud cover percentage (0–100), null for SAR products",
    )

    # ── Provider metadata ─────────────────────────────────────────────────────
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw provider-specific metadata preserved for reference",
    )

    # ── Mode transparency ─────────────────────────────────────────────────────
    mode: str = Field(
        default="mock",
        description="'mock' or 'real' — always honest about data origin",
    )
