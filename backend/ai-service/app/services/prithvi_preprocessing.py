"""
app/services/prithvi_preprocessing.py
─────────────────────────────────────────────────────────────────────────────
Prithvi-EO-2.0-300M preprocessing layer.

PURPOSE
-------
Transform a validated MultiTemporalInput (4 temporal frames x 6 Sentinel-2
bands) into the normalized NumPy array that Prithvi expects:

    shape  : (4, 6, 224, 224)
    dtype  : float32
    layout : [T, C, H, W]  (time x channel x height x width)

This layer is intentionally separated from:
  - satellite acquisition  (FetchMultitemporalSentinel2Tool / satellite_data.py)
  - model loading / inference (future Kaggle worker notebook)

PIPELINE
--------
    MultiTemporalInput
         |
    1. Temporal sort           oldest -> newest (validates exactly 4 frames)
         |
    2. Band validation         all 6 S2 bands present per frame
         |
    3. Asset resolution        each band URL -> RasterData (via BandAssetLoader)
         |
    4. Geospatial 30 m grid alignment:
         For real/georeferenced rasters:
           Reproject/resample each band to common 30 m grid using
           rasterio.warp.reproject (bilinear).
         For synthetic test rasters without spatial metadata:
           Fallback to bilinear zoom.
         |
    5. Model spatial window:
         Crop (deterministic central crop) or pad (deterministic symmetric pad)
         to the model input spatial dimensions (224 x 224 pixels).
         Note: 224 x 224 at 30 m GSD covers ~6.72 km x 6.72 km spatial footprint.
         |
    6. Channel stack           shape (6, 224, 224)
         |
    7. Non-finite rejection    NaN / Inf in any band raises PrithviPreprocessingError
         |
    8. Prithvi normalisation   (pixel - mean) / std  per channel
         |
    PrithviPreprocessingResult  shape (4, 6, 224, 224), dtype float32

BAND ORDERING & CHANNEL SEMANTICS
---------------------------------
Sentinel-2 native names are used throughout the acquisition layer contract:
    B02, B03, B04, B08A, B11, B12

For Prithvi-EO-2.0-300M, the model channels correspond to:
    channel 0  <-  S2 B02   (Blue,        490 nm, 10 m native)  -> Prithvi/HLS B02
    channel 1  <-  S2 B03   (Green,       560 nm, 10 m native)  -> Prithvi/HLS B03
    channel 2  <-  S2 B04   (Red,         665 nm, 10 m native)  -> Prithvi/HLS B04
    channel 3  <-  S2 B08A  (Narrow NIR,  865 nm, 20 m native)  -> Prithvi/HLS B05
    channel 4  <-  S2 B11   (SWIR-1,     1610 nm, 20 m native)  -> Prithvi/HLS B06
    channel 5  <-  S2 B12   (SWIR-2,     2190 nm, 20 m native)  -> Prithvi/HLS B07

This order is enforced by PRITHVI_BAND_ORDER.

PRITHVI NORMALISATION CONSTANTS
--------------------------------
Source: Prithvi-EO-2.0-300M model card / HLS training statistics.
Applied in PRITHVI_BAND_ORDER channel order (channels 0 to 5):

    mean = [1087, 1342, 1433, 2734, 1958, 1363]
    std  = [2248, 2179, 2178, 1850, 1242, 1049]

SPATIAL RESOLUTION VS MODEL INPUT SIZE
--------------------------------------
- Target ground sampling distance (GSD): target_resolution_m = 30.0 m.
- Model input spatial dimension: 224 x 224 pixels.
These are strictly separate operations:
  1. Reproject/resample native rasters (10 m / 20 m) to a common 30 m grid.
  2. Select/crop/pad a 224 x 224 pixel spatial window from the 30 m grid.
  At 30 m GSD, a 224 x 224 pixel window spans 224 * 30 m = 6,720 m (~6.72 km) per side.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
from loguru import logger

from app.schemas.requests import MultiTemporalInput


# ─────────────────────────────────────────────────────────────────────────────
# Canonical band order & semantic mappings
# ─────────────────────────────────────────────────────────────────────────────

# Sentinel-2 native band names in channel order
PRITHVI_BAND_ORDER: list[str] = [
    "B02",   # channel 0 -> Prithvi/HLS B02 (Blue,        490 nm, 10 m native)
    "B03",   # channel 1 -> Prithvi/HLS B03 (Green,       560 nm, 10 m native)
    "B04",   # channel 2 -> Prithvi/HLS B04 (Red,         665 nm, 10 m native)
    "B08A",  # channel 3 -> Prithvi/HLS B05 (Narrow NIR,  865 nm, 20 m native)
    "B11",   # channel 4 -> Prithvi/HLS B06 (SWIR-1,     1610 nm, 20 m native)
    "B12",   # channel 5 -> Prithvi/HLS B07 (SWIR-2,     2190 nm, 20 m native)
]

# Prithvi-EO-2.0-300M model channel names
PRITHVI_MODEL_BANDS: list[str] = [
    "B02",   # channel 0
    "B03",   # channel 1
    "B04",   # channel 2
    "B05",   # channel 3
    "B06",   # channel 4
    "B07",   # channel 5
]

# Semantic mapping from Sentinel-2 native band names to Prithvi/HLS model bands
S2_TO_PRITHVI_BAND_MAP: dict[str, str] = {
    "B02": "B02",
    "B03": "B03",
    "B04": "B04",
    "B08A": "B05",
    "B11": "B06",
    "B12": "B07",
}

# Number of required temporal frames (fixed for Prithvi-EO-2.0-300M).
PRITHVI_N_FRAMES: int = 4

# Spatial target for crop/pad (matches Prithvi ViT patch grid).
PRITHVI_SPATIAL_SIZE: int = 224

# Target spatial resolution in metres (HLS / Prithvi pretraining GSD).
PRITHVI_TARGET_RESOLUTION_M: float = 30.0

# ── Prithvi-EO-2.0-300M normalisation constants ──────────────────────────────
# Applied per-channel, in PRITHVI_BAND_ORDER order (channels 0..5).
# Source: Prithvi-EO-2.0 model card (HLS surface-reflectance training stats).
_PRITHVI_MEAN = np.array(
    [1087.0, 1342.0, 1433.0, 2734.0, 1958.0, 1363.0],
    dtype=np.float32,
)
_PRITHVI_STD = np.array(
    [2248.0, 2179.0, 2178.0, 1850.0, 1242.0, 1049.0],
    dtype=np.float32,
)


# ─────────────────────────────────────────────────────────────────────────────
# Exception
# ─────────────────────────────────────────────────────────────────────────────

class PrithviPreprocessingError(ValueError):
    """
    Raised when preprocessing cannot produce a valid Prithvi input tensor.

    Reasons include:
      - Wrong number of temporal frames (must be exactly 4)
      - Missing required band asset in any frame
      - Non-finite (NaN / Inf) values in raster data
      - Inconsistent spatial reference between bands
      - Asset load failure
    """


# ─────────────────────────────────────────────────────────────────────────────
# RasterData -- Container for raster array + geospatial metadata
# ─────────────────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class RasterData:
    """
    Internal container for a loaded 2-D raster array along with geospatial metadata.

    Attributes:
        array: 2-D float32 NumPy array (H, W).
        crs: Coordinate reference system string (e.g. 'EPSG:32632') or None.
        transform: Affine transform object or None.
        resolution: (x_res, y_res) native pixel resolution in CRS units, or None.
        width: Raster width in pixels.
        height: Raster height in pixels.
    """
    array: np.ndarray
    crs: Optional[str] = None
    transform: Optional[Any] = None
    resolution: Optional[tuple[float, float]] = None
    width: Optional[int] = None
    height: Optional[int] = None

    @property
    def shape(self) -> tuple[int, ...]:
        return self.array.shape

    @property
    def ndim(self) -> int:
        return self.array.ndim

    @property
    def dtype(self) -> np.dtype:
        return self.array.dtype

    def __array__(self, dtype=None) -> np.ndarray:
        return np.asarray(self.array, dtype=dtype)


# ─────────────────────────────────────────────────────────────────────────────
# BandAssetLoader -- clean abstraction between asset reference and RasterData
# ─────────────────────────────────────────────────────────────────────────────

class BandAssetLoader:
    """
    Resolves a band asset reference (URL / path string) to a RasterData container.

    Design:
    - Production (rasterio) path: opens GeoTIFF via rasterio, reads band 1 and metadata.
    - Test / mock path: synthetic arrays registered via BandAssetLoader.register().
      No HTTP download, no file I/O. Supports optional CRS/transform/resolution.
    """

    def __init__(self) -> None:
        self._registry: dict[str, RasterData] = {}

    def register(
        self,
        url: str,
        array: np.ndarray,
        crs: Optional[str] = None,
        transform: Optional[Any] = None,
        resolution: Optional[tuple[float, float] | float] = None,
    ) -> None:
        """
        Register a synthetic raster array for a given URL.

        Args:
            url: The exact URL string that will appear in SpectralBands fields.
            array: 2-D NumPy array (H, W) or (1, H, W).
            crs: Optional CRS string (e.g. 'EPSG:32632').
            transform: Optional rasterio Affine transform.
            resolution: Optional pixel resolution tuple (x_res, y_res) or float.
        """
        if array.ndim == 3 and array.shape[0] == 1:
            array = array[0]
        if array.ndim != 2:
            raise ValueError(
                f"BandAssetLoader.register: array must be 2-D (H, W), "
                f"got shape {array.shape}"
            )
        arr_f32 = array.astype(np.float32)
        h, w = arr_f32.shape
        res: Optional[tuple[float, float]] = None
        if isinstance(resolution, (int, float)):
            res = (float(resolution), float(resolution))
        elif isinstance(resolution, tuple):
            res = (float(resolution[0]), float(resolution[1]))

        self._registry[url] = RasterData(
            array=arr_f32,
            crs=crs,
            transform=transform,
            resolution=res,
            width=w,
            height=h,
        )

    def load(self, url: str) -> RasterData:
        """
        Load a band asset and return it as a RasterData instance.

        Priority:
          1. In-memory registry (registered synthetic arrays)
          2. rasterio (real GeoTIFF files / remote URLs)

        Raises:
            PrithviPreprocessingError: if the asset cannot be loaded.
        """
        if url in self._registry:
            return self._registry[url]

        # -- Real mode: try rasterio -----------------------------------------
        try:
            import rasterio
        except ImportError:
            raise PrithviPreprocessingError(
                f"Cannot load asset '{url}': rasterio is not installed "
                "(required for real-mode band loading). "
                "Install it with: pip install rasterio. "
                "For tests, use BandAssetLoader.register() to inject synthetic arrays."
            )

        try:
            with rasterio.open(url) as src:
                data = src.read(1).astype(np.float32)
                crs_str = str(src.crs) if src.crs else None
                transform = src.transform
                res = src.res if hasattr(src, "res") else None
                return RasterData(
                    array=data,
                    crs=crs_str,
                    transform=transform,
                    resolution=res,
                    width=src.width,
                    height=src.height,
                )
        except Exception as exc:
            raise PrithviPreprocessingError(
                f"Failed to load band asset '{url}': {exc}"
            ) from exc


# ─────────────────────────────────────────────────────────────────────────────
# PrithviPreprocessingResult -- internal output contract
# ─────────────────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class PrithviPreprocessingResult:
    """
    Output of the Prithvi preprocessing pipeline.

    This is an INTERNAL dataclass -- it is NOT serialized directly into API responses.
    The NumPy array is held in memory until consumed by the Prithvi inference step.

    Attributes
    ----------
    array : np.ndarray
        Preprocessed tensor, shape (4, 6, 224, 224), dtype float32.
        Layout: [T, C, H, W] -- time x channel x height x width.
        Values are Prithvi-normalized: (pixel - mean) / std.

    shape : tuple[int, int, int, int]
        Tuple (4, 6, 224, 224) confirming the expected layout.

    band_order : list[str]
        Sentinel-2 native band names in channel order (PRITHVI_BAND_ORDER).
        channel i <-> band_order[i].

    frame_dates : list[str]
        ISO 8601 acquisition timestamps of the 4 frames, oldest -> newest.

    resolution_m : float
        Target spatial ground sampling distance (30.0 m).

    resampling_occurred : bool
        True if any band was spatially resampled.

    spatial_size : int
        Model height and width after crop/pad (224).

    crs : Optional[str]
        Geospatial Coordinate Reference System (e.g. 'EPSG:32632') if available.

    transform : Optional[Any]
        Affine georeferencing transform of the preprocessed spatial window if available.
    """

    array: np.ndarray
    shape: tuple[int, int, int, int]
    band_order: list[str]
    frame_dates: list[str]
    resolution_m: float
    resampling_occurred: bool
    spatial_size: int
    crs: Optional[str] = None
    transform: Optional[Any] = None

    def summary(self) -> dict:
        """Return a JSON-safe summary (without the NumPy array)."""
        transform_val = None
        if self.transform is not None:
            if hasattr(self.transform, "to_gdal"):
                transform_val = list(self.transform.to_gdal())
            elif hasattr(self.transform, "__iter__"):
                transform_val = list(self.transform)
            else:
                transform_val = str(self.transform)

        return {
            "shape": list(self.shape),
            "dtype": str(self.array.dtype),
            "band_order": self.band_order,
            "frame_dates": self.frame_dates,
            "resolution_m": self.resolution_m,
            "resampling_occurred": self.resampling_occurred,
            "spatial_size": self.spatial_size,
            "crs": self.crs,
            "transform": transform_val,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Internal spatial helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resample_to_target(
    array: np.ndarray,
    target_h: int,
    target_w: int,
) -> np.ndarray:
    """
    Resample a 2-D synthetic array to (target_h, target_w) using bilinear interpolation.

    Used for unit tests with synthetic arrays that lack geospatial metadata.
    Uses scipy.ndimage.zoom with order=1 (bilinear kernel).
    """
    h, w = array.shape
    if h == target_h and w == target_w:
        return array

    from scipy.ndimage import zoom  # pyrefly: ignore [missing-import]

    zoom_h = target_h / h
    zoom_w = target_w / w
    resampled = zoom(array, (zoom_h, zoom_w), order=1, prefilter=False)
    return resampled.astype(np.float32)


def _crop_or_pad(array: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """
    Crop or zero-pad a 2-D array to exactly (target_h, target_w).

    Behaviour:
    - Larger than target: crop a deterministic CENTRAL window.
    - Smaller than target: zero-pad symmetrically (floor padding on leading side).
    """
    h, w = array.shape

    # -- Height axis ----------------------------------------------------------
    if h > target_h:
        start_h = (h - target_h) // 2
        array = array[start_h : start_h + target_h, :]
    elif h < target_h:
        pad_before = (target_h - h) // 2
        pad_after = target_h - h - pad_before
        array = np.pad(array, ((pad_before, pad_after), (0, 0)), mode="constant")

    # -- Width axis -----------------------------------------------------------
    h2, w2 = array.shape
    if w > target_w:
        start_w = (w - target_w) // 2
        array = array[:, start_w : start_w + target_w]
    elif w < target_w:
        pad_before = (target_w - w) // 2
        pad_after = target_w - w - pad_before
        array = np.pad(array, ((0, 0), (pad_before, pad_after)), mode="constant")

    return array.astype(np.float32)


def _reproject_to_30m_grid(
    raster: RasterData,
    target_crs: str,
    target_transform: Any,
    target_h: int,
    target_w: int,
) -> np.ndarray:
    """
    Geospatially reproject/resample a raster to a target 30 m grid using
    rasterio.warp.reproject with Resampling.bilinear.
    """
    try:
        import rasterio.warp
        from rasterio.enums import Resampling
    except ImportError:
        raise PrithviPreprocessingError(
            "rasterio is required for geospatial 30 m grid reprojection."
        )

    destination = np.zeros((target_h, target_w), dtype=np.float32)
    rasterio.warp.reproject(
        source=raster.array,
        destination=destination,
        src_transform=raster.transform,
        src_crs=raster.crs,
        dst_transform=target_transform,
        dst_crs=target_crs,
        resampling=Resampling.bilinear,
    )
    return destination


# ─────────────────────────────────────────────────────────────────────────────
# Core preprocessing function
# ─────────────────────────────────────────────────────────────────────────────

def preprocess_multitemporal(
    mti: MultiTemporalInput,
    loader: Optional[BandAssetLoader] = None,
    target_h: int = PRITHVI_SPATIAL_SIZE,
    target_w: int = PRITHVI_SPATIAL_SIZE,
    target_resolution_m: float = PRITHVI_TARGET_RESOLUTION_M,
) -> PrithviPreprocessingResult:
    """
    Transform a validated MultiTemporalInput into a Prithvi input tensor.

    Steps
    -----
    1. Validate frame count (must be exactly 4).
    2. Sort frames oldest -> newest by acquisition_date.
    3. For each frame, validate all 6 bands are present (not None).
    4. For each frame and band, resolve the asset URL to a RasterData via *loader*.
    5. Place all 6 bands on a common 30 m spatial grid:
       - If geospatial metadata (CRS + transform) is available:
         Compute common 30 m grid and reproject using rasterio.warp.reproject (bilinear).
       - If synthetic data without geospatial metadata:
         Treat as common synthetic grid, with bilinear zoom if size differs.
    6. Crop (central) or zero-pad to exactly the model input size (target_h, target_w).
    7. Stack 6 bands into a (6, target_h, target_w) frame array in PRITHVI_BAND_ORDER.
    8. Validate: no NaN or Inf values allowed anywhere.
    9. Apply Prithvi normalisation: (pixel - mean) / std per channel.
    10. Stack 4 frames into a (4, 6, target_h, target_w) tensor.

    Args
    ----
    mti:
        Validated MultiTemporalInput (4 frames x 6 bands).
    loader:
        BandAssetLoader instance for resolving band URLs.
    target_h:
        Model input height in pixels (default: 224).
    target_w:
        Model input width in pixels (default: 224).
    target_resolution_m:
        Target ground sampling distance in metres (default: 30.0).

    Returns
    -------
    PrithviPreprocessingResult
        Fully preprocessed tensor and associated metadata (including crs and transform).
    """
    if loader is None:
        loader = BandAssetLoader()

    # -- Step 1: Validate frame count -----------------------------------------
    n_frames = len(mti.frames)
    if n_frames != PRITHVI_N_FRAMES:
        raise PrithviPreprocessingError(
            f"Prithvi requires exactly {PRITHVI_N_FRAMES} temporal frames; "
            f"got {n_frames}."
        )

    # -- Step 2: Sort frames oldest -> newest ---------------------------------
    def _parse_date(frame_date: str) -> datetime:
        """Parse ISO 8601 string to datetime (UTC)."""
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(frame_date, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise PrithviPreprocessingError(
            f"Cannot parse acquisition_date '{frame_date}'. "
            "Expected ISO 8601 format (e.g. '2023-06-15' or '2023-06-15T10:30:00Z')."
        )

    frames = sorted(mti.frames, key=lambda f: _parse_date(f.acquisition_date))
    frame_dates = [f.acquisition_date for f in frames]

    logger.debug(
        f"[prithvi_preprocessing] Processing {n_frames} frames: {frame_dates}"
    )

    # -- Steps 3-9: Per-frame processing --------------------------------------
    all_frame_arrays: list[np.ndarray] = []
    resampling_occurred = False
    final_crs: Optional[str] = None
    final_transform: Optional[Any] = None

    for frame_idx, frame in enumerate(frames):
        frame_raster_data: list[RasterData] = []

        for band_name in PRITHVI_BAND_ORDER:
            # Step 3: validate band presence
            url: Optional[str] = getattr(frame.bands, band_name)
            if url is None:
                raise PrithviPreprocessingError(
                    f"Frame {frame_idx} (date={frame.acquisition_date}) "
                    f"is missing required band '{band_name}'. "
                    "All 6 bands (B02, B03, B04, B08A, B11, B12) are mandatory "
                    "for Prithvi preprocessing even though MultiTemporalInput "
                    "allows optional bands."
                )

            # Step 4: load raster asset
            try:
                raster = loader.load(url)
            except PrithviPreprocessingError:
                raise
            except Exception as exc:
                raise PrithviPreprocessingError(
                    f"Frame {frame_idx}, band {band_name}: "
                    f"unexpected error loading '{url}': {exc}"
                ) from exc

            # Ensure 2-D array
            if raster.array.ndim != 2:
                raise PrithviPreprocessingError(
                    f"Frame {frame_idx}, band {band_name}: "
                    f"expected 2-D array, got shape {raster.array.shape}."
                )

            frame_raster_data.append(raster)

        # Check if all bands have geospatial metadata (CRS and transform)
        has_geospatial = all(
            r.crs is not None and r.transform is not None for r in frame_raster_data
        )

        frame_bands: list[np.ndarray] = []

        if has_geospatial:
            import rasterio.transform
            from affine import Affine

            # Reference band for CRS and bounds
            ref_r = frame_raster_data[0]
            ref_crs = ref_r.crs
            ref_bounds = rasterio.transform.array_bounds(
                ref_r.array.shape[0], ref_r.array.shape[1], ref_r.transform
            )
            minx, miny, maxx, maxy = ref_bounds

            # Derive common 30 m grid
            grid_w = max(1, int(round((maxx - minx) / target_resolution_m)))
            grid_h = max(1, int(round((maxy - miny) / target_resolution_m)))
            grid_transform = Affine.translation(minx, maxy) * Affine.scale(
                target_resolution_m, -target_resolution_m
            ) if not hasattr(Affine, "__matmul__") else Affine.translation(minx, maxy) @ Affine.scale(
                target_resolution_m, -target_resolution_m
            )

            for band_idx, r in enumerate(frame_raster_data):
                # Geospatially reproject to common 30 m grid
                aligned_band = _reproject_to_30m_grid(
                    raster=r,
                    target_crs=ref_crs,  # type: ignore[arg-type]
                    target_transform=grid_transform,
                    target_h=grid_h,
                    target_w=grid_w,
                )
                resampling_occurred = True

                # Step 5: Choose spatial window (central crop or zero pad to 224x224)
                windowed_band = _crop_or_pad(aligned_band, target_h, target_w)
                frame_bands.append(windowed_band)

            # Compute final transform after crop/pad
            start_y = (grid_h - target_h) // 2 if grid_h > target_h else -((target_h - grid_h) // 2)
            start_x = (grid_w - target_w) // 2 if grid_w > target_w else -((target_w - grid_w) // 2)
            final_transform = grid_transform @ Affine.translation(start_x, start_y)
            final_crs = ref_crs

        else:
            # Synthetic / mock arrays without geospatial metadata
            for band_idx, r in enumerate(frame_raster_data):
                band_array = r.array
                h, w = band_array.shape

                if h != target_h or w != target_w:
                    resampling_occurred = True
                    band_array = _resample_to_target(band_array, target_h, target_w)

                band_array = _crop_or_pad(band_array, target_h, target_w)
                frame_bands.append(band_array)

        # Step 7: stack 6 bands -> (6, target_h, target_w)
        frame_stack = np.stack(frame_bands, axis=0)

        # Step 8: reject non-finite values
        if not np.isfinite(frame_stack).all():
            n_bad = int(np.sum(~np.isfinite(frame_stack)))
            raise PrithviPreprocessingError(
                f"Frame {frame_idx} (date={frame.acquisition_date}) "
                f"contains {n_bad} non-finite value(s) (NaN or Inf). "
                "Remove or repair the affected pixels before preprocessing."
            )

        # Step 9: Prithvi normalisation -- (pixel - mean) / std per channel
        mean = _PRITHVI_MEAN[:, np.newaxis, np.newaxis]   # (6, 1, 1)
        std = _PRITHVI_STD[:, np.newaxis, np.newaxis]     # (6, 1, 1)
        frame_stack = (frame_stack - mean) / std
        frame_stack = frame_stack.astype(np.float32)

        all_frame_arrays.append(frame_stack)

    # -- Step 10: Stack 4 frames -> (4, 6, target_h, target_w) ---------------
    tensor = np.stack(all_frame_arrays, axis=0)

    result = PrithviPreprocessingResult(
        array=tensor,
        shape=(tensor.shape[0], tensor.shape[1], tensor.shape[2], tensor.shape[3]),
        band_order=list(PRITHVI_BAND_ORDER),
        frame_dates=frame_dates,
        resolution_m=target_resolution_m,
        resampling_occurred=resampling_occurred,
        spatial_size=target_h,
        crs=final_crs,
        transform=final_transform,
    )

    logger.info(
        f"[prithvi_preprocessing] Complete: shape={result.shape}, "
        f"dtype={tensor.dtype}, resampled={resampling_occurred}, "
        f"resolution={target_resolution_m}m, spatial_size={target_h}"
    )
    return result
