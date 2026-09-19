"""
SatQuery AI — Deterministic Raster Data Inspector
Extracts metadata, coordinate reference systems, bounding boxes, band statistics,
and generates downsampled preview thumbnails without blowing up system memory.
"""
from __future__ import annotations

import os
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image
import rasterio
from rasterio.warp import transform_bounds
from rasterio.enums import Resampling

from app.schemas.data_asset import BandInfo, Dimensions, DataProfile


class DataInspector:
    """Inspects geospatial raster files deterministically."""

    @staticmethod
    def inspect(file_path: str, asset_id: str, output_dir: str) -> Tuple[DataProfile, str, str]:
        """
        Inspects raster at file_path and generates preview and thumbnail in output_dir.
        Returns (DataProfile, preview_relative_url, thumbnail_relative_url).
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        preview_filename = "preview.png"
        thumb_filename = "thumbnail.png"
        preview_path = out_path / preview_filename
        thumb_path = out_path / thumb_filename

        with rasterio.open(str(path)) as src:
            width = src.width
            height = src.height
            count = src.count
            dtype_str = str(src.dtypes[0]) if src.dtypes else "uint8"
            nodata_val = src.nodata

            # CRS & EPSG
            crs_str = None
            crs_wkt = None
            if src.crs:
                crs_str = src.crs.to_string()
                try:
                    crs_wkt = src.crs.to_wkt()
                except Exception:
                    crs_wkt = None

            # Spatial resolution
            res_x, res_y = abs(src.res[0]), abs(src.res[1])

            # Transform bounds to WGS84 (EPSG:4326) for global web mapping
            wgs84_bounds = None
            center_coords = None
            try:
                if src.crs:
                    minx, miny, maxx, maxy = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
                    wgs84_bounds = [round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)]
                    center_coords = {
                        "latitude": round((miny + maxy) / 2.0, 6),
                        "longitude": round((minx + maxx) / 2.0, 6),
                    }
                else:
                    # Raw pixel or unprojected bounds
                    wgs84_bounds = [round(src.bounds.left, 4), round(src.bounds.bottom, 4),
                                    round(src.bounds.right, 4), round(src.bounds.top, 4)]
            except Exception:
                wgs84_bounds = None

            # Metadata tags
            tags = src.tags()

            # Downsample factor for statistics and preview generation (keep preview under 1024px)
            max_dim = max(width, height)
            scale = max(1, math.ceil(max_dim / 1024))
            preview_w = max(1, width // scale)
            preview_h = max(1, height // scale)

            # Band inspection & statistics on downsampled window
            bands_info: List[BandInfo] = []
            preview_bands = []

            for b_idx in range(1, count + 1):
                try:
                    # Read downsampled slice
                    band_data = src.read(
                        b_idx,
                        out_shape=(preview_h, preview_w),
                        resampling=Resampling.bilinear,
                    ).astype(np.float32)

                    if nodata_val is not None:
                        valid_mask = band_data != nodata_val
                    else:
                        valid_mask = ~np.isnan(band_data)

                    valid_pixels = band_data[valid_mask]
                    if len(valid_pixels) > 0:
                        b_min = float(np.min(valid_pixels))
                        b_max = float(np.max(valid_pixels))
                        b_mean = float(np.mean(valid_pixels))
                        b_std = float(np.std(valid_pixels))
                    else:
                        b_min, b_max, b_mean, b_std = 0.0, 0.0, 0.0, 0.0

                    b_desc = src.descriptions[b_idx - 1] if src.descriptions and src.descriptions[b_idx - 1] else None
                    b_name = f"B{b_idx:02d}" if count > 1 else "Band 1"

                    bands_info.append(BandInfo(
                        index=b_idx,
                        name=b_name,
                        description=b_desc,
                        min=round(b_min, 3),
                        max=round(b_max, 3),
                        mean=round(b_mean, 3),
                        std=round(b_std, 3),
                    ))

                    if b_idx <= 4:
                        preview_bands.append(band_data)
                except Exception as b_err:
                    bands_info.append(BandInfo(index=b_idx, name=f"B{b_idx}"))

            # Generate true-color or grayscale preview
            DataInspector._generate_preview_image(preview_bands, preview_path, thumb_path)

        # Modality, sensor, platform identification heuristics
        from app.data.profile import DataProfileGenerator
        profile = DataProfileGenerator.generate(
            asset_id=asset_id,
            filename=path.name,
            dimensions=Dimensions(width=width, height=height, bands=count),
            dtype=dtype_str,
            crs=crs_str,
            crs_wkt=crs_wkt,
            resolution=[round(res_x, 2), round(res_y, 2)],
            bounds=wgs84_bounds,
            center=center_coords,
            nodata=nodata_val,
            bands=bands_info,
            tags=tags,
        )

        preview_rel = f"/api/data/assets/{asset_id}/preview"
        thumb_rel = f"/api/data/assets/{asset_id}/thumbnail"

        return profile, preview_rel, thumb_rel

    @staticmethod
    def _generate_preview_image(bands: List[np.ndarray], preview_path: Path, thumb_path: Path) -> None:
        """Normalizes and creates a visual preview image."""
        try:
            if not bands:
                # Blank fallback image
                img = Image.new("RGB", (256, 256), color=(20, 20, 25))
                img.save(preview_path)
                img.save(thumb_path)
                return

            def norm_band(arr: np.ndarray) -> np.ndarray:
                p2, p98 = np.percentile(arr, (2, 98))
                if p98 > p2:
                    clipped = np.clip(arr, p2, p98)
                    return ((clipped - p2) / (p98 - p2) * 255.0).astype(np.uint8)
                return np.zeros_like(arr, dtype=np.uint8)

            if len(bands) >= 3:
                # Use first 3 bands as RGB (or bands 3,2,1 if 4-band optical)
                if len(bands) >= 4:
                    r, g, b = norm_band(bands[3]), norm_band(bands[2]), norm_band(bands[1])
                else:
                    r, g, b = norm_band(bands[0]), norm_band(bands[1]), norm_band(bands[2])
                rgb_arr = np.dstack([r, g, b])
                img = Image.fromarray(rgb_arr, mode="RGB")
            else:
                gray = norm_band(bands[0])
                img = Image.fromarray(gray, mode="L")

            img.save(preview_path, format="PNG", optimize=True)

            # Thumbnail
            thumb = img.copy()
            thumb.thumbnail((256, 256))
            thumb.save(thumb_path, format="PNG", optimize=True)
        except Exception as err:
            img = Image.new("RGB", (256, 256), color=(15, 15, 20))
            img.save(preview_path)
            img.save(thumb_path)
