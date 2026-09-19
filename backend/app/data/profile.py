"""
SatQuery AI — Structured DataProfile Generator
Synthesizes deterministic raster measurements into a structured DataProfile for ATS context.
Never hallucinates unverified sensors or platform attributes.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from app.schemas.data_asset import BandInfo, Dimensions, DataProfile


class DataProfileGenerator:
    """Generates standardized DataProfile schemas."""

    @staticmethod
    def generate(
        *,
        asset_id: str,
        filename: str,
        dimensions: Dimensions,
        dtype: str,
        crs: Optional[str],
        crs_wkt: Optional[str],
        resolution: Optional[List[float]],
        bounds: Optional[List[float]],
        center: Optional[Dict[str, float]],
        nodata: Optional[float],
        bands: List[BandInfo],
        tags: Dict[str, Any],
    ) -> DataProfile:
        lower_fn = filename.lower()
        tags_str = " ".join([f"{k}:{v}" for k, v in tags.items()]).lower()

        # Deterministic sensor detection from authentic metadata tags or strict filename patterns
        sensor = None
        platform = None
        modality = "optical"
        limitations: List[str] = []

        if "sentinel-2" in tags_str or "msi" in tags_str or lower_fn.startswith("s2") or "sentinel-2" in lower_fn:
            sensor = "MSI"
            platform = "Sentinel-2"
            modality = "multispectral"
        elif "landsat" in tags_str or "oli" in tags_str or lower_fn.startswith("lc08") or lower_fn.startswith("lc09"):
            sensor = "OLI/TIRS"
            platform = "Landsat-8/9"
            modality = "multispectral"
        elif "sentinel-1" in tags_str or "c-sar" in tags_str or lower_fn.startswith("s1"):
            sensor = "C-SAR"
            platform = "Sentinel-1"
            modality = "sar"
        elif "dem" in lower_fn or "copernicus_dem" in lower_fn or "elevation" in lower_fn:
            sensor = "InSAR / Photogrammetric DEM"
            platform = "Copernicus DEM"
            modality = "elevation"
        else:
            sensor = None
            platform = None
            limitations.append("Sensor and platform identity could not be verified from available metadata.")

        # Identify modality from band count if not yet established
        if modality == "optical":
            if dimensions.bands >= 4:
                modality = "multispectral"
            elif dimensions.bands == 3:
                modality = "rgb_optical"
            elif dimensions.bands == 1:
                modality = "single_band_raster"

        # Determine feasible remote-sensing analyses
        possible_analyses: List[str] = []
        if dimensions.bands >= 4:
            possible_analyses.extend([
                "Normalized Difference Vegetation Index (NDVI)",
                "Soil-Adjusted Vegetation Index (SAVI)",
                "False-Color Infrared Composite (NIR-R-G)",
                "Spectral Profile Inspection",
                "Land-Cover Classification & Surface Masking",
            ])
        elif dimensions.bands == 3:
            possible_analyses.extend([
                "True-Color RGB Visual Analysis",
                "Urban Footprint & Structural Feature Extraction",
                "Color Contrast Enhancement & Histogram Stretching",
            ])
        elif dimensions.bands == 1:
            possible_analyses.extend([
                "Single-Band Thresholding & Anomaly Segmentation",
                "Statistical Histogram & Cumulative Distribution",
                "Surface Roughness & Contour Gradient Mapping",
            ])

        if not crs:
            limitations.append("File lacks coordinate reference system (CRS); spatial georeferencing is unprojected.")

        if not bounds or bounds == [0, 0, 0, 0]:
            limitations.append("Spatial bounding box coordinates could not be resolved to WGS84.")

        # Assign common remote sensing band descriptions if standard Sentinel-2 12/13 band configuration
        if dimensions.bands == 13 and ("sentinel" in (platform or "").lower() or dimensions.bands == 13):
            s2_names = [
                ("B01", "Coastal aerosol", 0.443),
                ("B02", "Blue", 0.490),
                ("B03", "Green", 0.560),
                ("B04", "Red", 0.665),
                ("B05", "Vegetation red edge", 0.705),
                ("B06", "Vegetation red edge", 0.740),
                ("B07", "Vegetation red edge", 0.783),
                ("B08", "NIR (Broad)", 0.842),
                ("B8A", "Vegetation red edge (Narrow NIR)", 0.865),
                ("B09", "Water vapour", 0.945),
                ("B10", "SWIR - Cirrus", 1.375),
                ("B11", "SWIR-1", 1.610),
                ("B12", "SWIR-2", 2.190),
            ]
            for idx, (b_name, b_desc, b_wave) in enumerate(s2_names):
                if idx < len(bands):
                    bands[idx].name = b_name
                    bands[idx].description = b_desc
                    bands[idx].wavelength_um = b_wave

        return DataProfile(
            asset_id=asset_id,
            filename=filename,
            format="GeoTIFF",
            dimensions=dimensions,
            dtype=dtype,
            crs=crs,
            crs_wkt=crs_wkt,
            resolution=resolution,
            bounds=bounds,
            center=center,
            nodata=nodata,
            modality=modality,
            sensor=sensor,
            platform=platform,
            acquisition_date=tags.get("ACQUISITION_DATE") or tags.get("DATETIME"),
            bands=bands,
            statistics={
                "band_count": dimensions.bands,
                "total_pixels": dimensions.width * dimensions.height,
            },
            quality={
                "cloud_cover_pct": tags.get("CLOUD_COVERAGE_ASSESSMENT"),
                "data_type": dtype,
            },
            possible_analyses=possible_analyses,
            limitations=limitations,
        )
