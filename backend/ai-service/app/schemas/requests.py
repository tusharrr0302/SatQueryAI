"""
app/schemas/requests.py
─────────────────────────────────────────────────────────────────────────────
Pydantic models for:
  - The FastAPI chat endpoint request body
  - Tool input schemas (the data each tool receives when called)

These schemas serve two purposes:
  1. FastAPI uses them to validate and document incoming HTTP requests.
  2. The orchestrator validates tool arguments from GPT-OSS against them.
"""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# API Request
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """
    The body of a POST /api/v1/chat request.
    This is what the frontend (or curl/Postman) sends to us.
    """

    message: str = Field(
        ...,
        description="Natural-language query from the user",
        examples=["What is visible in this satellite image?"],
    )

    # ── Image inputs ──────────────────────────────────────────────────────────
    # Image can be provided as a local path (dev) or a remote URL (production).
    # When image_url is set, it takes precedence over image_path.
    image_path: Optional[str] = Field(
        default=None,
        description="Path to a local image file (absolute or relative to ai-service/)",
    )
    image_url: Optional[str] = Field(
        default=None,
        description="Public or signed URL to the primary image (for remote workers)",
    )

    # Optional second image for change-detection queries
    image_path_t2: Optional[str] = Field(
        default=None,
        description="Path to a second (time-2) image for change detection",
    )
    image_url_t2: Optional[str] = Field(
        default=None,
        description="Public or signed URL to the second image",
    )

    # Optional SAR image for cross-modal queries
    sar_image_path: Optional[str] = Field(
        default=None,
        description="Path to a SAR image for SAR+optical analysis",
    )
    sar_image_url: Optional[str] = Field(
        default=None,
        description="Public or signed URL to the SAR image",
    )

    # ── Geospatial context ────────────────────────────────────────────────────
    # AOI bounding box — when provided, GPT-OSS can use satellite fetch tools.
    aoi: Optional[list[float]] = Field(
        default=None,
        description=(
            "Area of interest bounding box [min_lon, min_lat, max_lon, max_lat] "
            "in WGS84. Enables satellite data fetching for text-only queries."
        ),
        examples=[[77.5, 29.0, 80.5, 31.5]],
    )

    # Date range for temporal queries (e.g. deforestation over 4 years)
    date_range: Optional[list[str]] = Field(
        default=None,
        description=(
            "Date range for satellite data fetching [start_date, end_date] "
            "in ISO 8601 format (YYYY-MM-DD)."
        ),
        examples=[["2020-01-01", "2024-12-31"]],
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional satellite metadata (sensor, bands, CRS, timestamps, etc.)",
    )

    # ── Conversation context ──────────────────────────────────────────────────
    # Allows GPT-OSS to remember previous messages within the same session.
    # The frontend can pass back the conversation history for multi-turn chat.
    conversation_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Previous messages in the conversation for multi-turn context",
    )

    # ── Request tracking ──────────────────────────────────────────────────────
    request_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional client-provided request ID for log correlation. "
            "If not provided, the service generates one automatically."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tool Input Schemas
# Each tool's input is a separate Pydantic model.
# The orchestrator validates GPT-OSS's tool arguments against these.
# ─────────────────────────────────────────────────────────────────────────────

class ImageMetadata(BaseModel):
    """
    Optional geospatial metadata attached to a single image.
    All fields are optional because the user may not always know them.
    """
    satellite: Optional[str] = Field(default=None, examples=["Sentinel-2"])
    sensor: Optional[str] = Field(default=None, examples=["MSI"])
    acquisition_time: Optional[str] = Field(default=None, examples=["2024-06-01T10:30:00Z"])
    bands: list[str] = Field(default_factory=list, examples=[["B02", "B03", "B04"]])
    crs: Optional[str] = Field(default=None, examples=["EPSG:4326"])


class AnalyzeImageInput(BaseModel):
    """
    Input for the analyze_image tool.
    Handles single-image visual question answering.
    """
    image: str = Field(
    ...,
    description="Image path or URL to the image that EarthDial-4B-MS must analyze",
)
    query: str = Field(
        ...,
        description="The question to ask about the image",
        examples=["What land cover types are visible?"],
    )
    metadata: Optional[ImageMetadata] = Field(default=None)


class DetectChangeInput(BaseModel):
    """
    Input for the detect_change tool.
    Requires two temporally separated images.

    analysis_mode selects which specialist pipeline runs:
      - "question_change"       → VisTA (Change Detection QA & visual grounding)
      - "multitemporal_analysis" → Prithvi-EO-2.0-300M (multitemporal/multispectral EO)

    When omitted, GPT-OSS is the orchestrator and may infer the appropriate mode
    from context; the worker defaults to VisTA.
    """
    image_t1: Optional[str] = Field(
        default=None,
        description="Path or URL to the earlier (time-1) image",
    )
    image_t2: Optional[str] = Field(
        default=None,
        description="Path or URL to the later (time-2) image",
    )
    image_t3: Optional[str] = Field(
        default=None,
        description="Path or URL to the time-3 image (for multitemporal analysis)",
    )
    image_t4: Optional[str] = Field(
        default=None,
        description="Path or URL to the time-4 image (for multitemporal analysis)",
    )
    metadata_t1: Optional[ImageMetadata] = Field(default=None)
    metadata_t2: Optional[ImageMetadata] = Field(default=None)
    metadata_t3: Optional[ImageMetadata] = Field(default=None)
    metadata_t4: Optional[ImageMetadata] = Field(default=None)
    query: str = Field(
        ...,
        description="What change to look for, or a general description request",
        examples=["What changed between these two images?"],
    )
    # GPT-OSS sets this when the user intent clearly maps to one specialist pipeline.
    # Omitting it is valid; the remote worker defaults to VisTA.
    analysis_mode: Optional[Literal[
        "question_change",
        "multitemporal_analysis",
    ]] = Field(
        default=None,
        description=(
            "Analysis mode that determines which specialist pipeline runs. "
            "'question_change' routes to VisTA for natural-language change-detection "
            "answers and visual grounding. "
            "'multitemporal_analysis' routes to Prithvi-EO-2.0-300M for "
            "multitemporal/multispectral EO analysis."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Multitemporal Acquisition Contract (Prithvi pipeline)
# Used when analysis_mode="multitemporal_analysis" is selected.
# The Prithvi-EO-2.0-300M pipeline ingests data via the HLS (Harmonized
# Landsat-Sentinel-2) specification.  The field names here are the
# *Sentinel-2 native* band identifiers; the HLS pre-processing step maps
# them to the band-order Prithvi expects internally.
#
#   Sentinel-2 native → HLS band position
#   ─────────────────────────────────────
#   B02  (Blue,        490 nm, 10 m)  → HLS B01
#   B03  (Green,       560 nm, 10 m)  → HLS B02
#   B04  (Red,         665 nm, 10 m)  → HLS B03
#   B08A (Narrow NIR,  865 nm, 20 m)  → HLS B04 (≈ Landsat Band 5)
#   B11  (SWIR-1,     1610 nm, 20 m)  → HLS B05 (≈ Landsat Band 6)
#   B12  (SWIR-2,     2190 nm, 20 m)  → HLS B06 (≈ Landsat Band 7)
# ─────────────────────────────────────────────────────────────────────────────

class SpectralBands(BaseModel):
    """
    Six Sentinel-2 band assets for one temporal frame.

    Field names are Sentinel-2 native identifiers.  The HLS harmonisation
    step re-orders them into the six-channel stack that the Prithvi pipeline
    expects.  All fields are Optional because partial acquisitions are valid
    (e.g. a band tile may be unavailable due to cloud mask or download failure).
    """
    B02: Optional[str] = Field(
        default=None,
        description=(
            "Blue (490 nm, 10 m resolution) — Sentinel-2 Band 2. "
            "Maps to HLS band position 1."
        ),
    )
    B03: Optional[str] = Field(
        default=None,
        description=(
            "Green (560 nm, 10 m resolution) — Sentinel-2 Band 3. "
            "Maps to HLS band position 2."
        ),
    )
    B04: Optional[str] = Field(
        default=None,
        description=(
            "Red (665 nm, 10 m resolution) — Sentinel-2 Band 4. "
            "Maps to HLS band position 3."
        ),
    )
    B08A: Optional[str] = Field(
        default=None,
        description=(
            "Narrow NIR (865 nm, 20 m resolution) — Sentinel-2 Band 8A. "
            "Maps to HLS band position 4 (analogous to Landsat Band 5)."
        ),
    )
    B11: Optional[str] = Field(
        default=None,
        description=(
            "SWIR-1 (1610 nm, 20 m resolution) — Sentinel-2 Band 11. "
            "Maps to HLS band position 5 (analogous to Landsat Band 6)."
        ),
    )
    B12: Optional[str] = Field(
        default=None,
        description=(
            "SWIR-2 (2190 nm, 20 m resolution) — Sentinel-2 Band 12. "
            "Maps to HLS band position 6 (analogous to Landsat Band 7)."
        ),
    )


class TemporalFrame(BaseModel):
    """
    One temporal observation: an acquisition timestamp paired with the
    six Sentinel-2 band assets for that date.

    Frames must be ordered oldest → newest when assembled into
    MultiTemporalInput.frames.
    """
    acquisition_date: str = Field(
        ...,
        description=(
            "ISO 8601 acquisition timestamp for this frame "
            "(e.g. '2023-06-15T10:30:00Z')"
        ),
        examples=["2023-06-15T10:30:00Z"],
    )
    bands: SpectralBands = Field(
        default_factory=SpectralBands,
        description="Six Sentinel-2 band assets for this acquisition.",
    )


class MultiTemporalInput(BaseModel):
    """
    Input contract for the Prithvi-EO-2.0-300M multitemporal analysis branch.

    The Prithvi pipeline ingests a fixed-length 4-frame × 6-band time series
    harmonised to the HLS (Harmonized Landsat-Sentinel-2) specification.
    This schema captures those four observations in acquisition order before
    the HLS normalisation step runs.

    Routing:
        This schema is only valid when analysis_mode='multitemporal_analysis'.
        The field is fixed as a Literal to prevent accidental misrouting.

    Band naming:
        Field names (B02, B03, B04, B08A, B11, B12) are Sentinel-2 native
        identifiers.  The HLS pre-processing step translates them to the
        band ordering expected by the Prithvi pipeline internally.
    """
    frames: list[TemporalFrame] = Field(
        ...,
        min_length=4,
        max_length=4,
        description=(
            "Exactly 4 temporal frames ordered oldest → newest. "
            "Each frame holds an acquisition date and six Sentinel-2 band assets."
        ),
    )
    bbox: Optional[list[float]] = Field(
        default=None,
        description=(
            "Area of interest bounding box [min_lon, min_lat, max_lon, max_lat] "
            "in WGS84.  Used for spatial context; the pipeline does not crop "
            "assets based on this field."
        ),
        examples=[[77.5, 29.0, 80.5, 31.5]],
    )
    query: str = Field(
        ...,
        description="Natural-language description of the multitemporal analysis to perform.",
        examples=["Detect vegetation loss across four growing seasons."],
    )
    analysis_mode: Literal["multitemporal_analysis"] = Field(
        default="multitemporal_analysis",
        description=(
            "Fixed routing token. Always 'multitemporal_analysis' — "
            "directs the orchestrator to the Prithvi pipeline. "
            "Cannot be overridden to another mode via this schema."
        ),
    )


class AnalyzeSarOpticalInput(BaseModel):
    """
    Input for the analyze_sar_optical tool.
    Takes one SAR image and one optical image for cross-modal analysis.
    """
    sar_image: Optional[str] = Field(
        default=None,
        description="Path or URL to the SAR image",
    )
    optical_image: Optional[str] = Field(
        default=None,
        description="Path or URL to the optical image",
    )
    metadata: Optional[ImageMetadata] = Field(default=None)
    query: str = Field(
        ...,
        description="Analysis question combining SAR and optical data",
        examples=["Identify flood extent using SAR and optical fusion"],
    )
    # LLM-driven model selection field.
    # The orchestrator LLM sets this based on semantic understanding of the task.
    # Do NOT use keyword matching to populate this — the LLM decides.
    selected_models: Optional[Literal["closp", "terrafm", "both"]] = Field(
        default=None,
        description=(
            "Which SAR+optical specialist model(s) to invoke. "
            "'closp': cross-modal embedding specialist (flood, damage assessment). "
            "'terrafm': multisensor foundation model (terrain classification). "
            "'both': invoke both and synthesise results. "
            "If omitted, defaults to 'closp'."
        ),
    )
    # Legacy: model_hint sent to the combined SAR_OPTICAL worker (kept for backward compat)
    model_hint: Optional[str] = Field(
        default=None,
        description="Legacy model hint for the combined SAR+optical worker: 'clasp' or 'terrafm'",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Satellite Acquisition Tool Input Schemas
# ─────────────────────────────────────────────────────────────────────────────

class FetchSentinel1Input(BaseModel):
    """Input for the fetch_sentinel1 tool (Copernicus Data Space OData API)."""
    bbox: list[float] = Field(
        ...,
        description="Bounding box [min_lon, min_lat, max_lon, max_lat] in WGS84",
        examples=[[77.5, 29.0, 80.5, 31.5]],
    )
    start_date: str = Field(
        ...,
        description="Start date in ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)",
        examples=["2024-06-01"],
    )
    end_date: str = Field(
        ...,
        description="End date in ISO 8601 format",
        examples=["2024-06-15"],
    )
    polarization: Optional[str] = Field(
        default="VV",
        description="SAR polarization: 'VV', 'VH', 'VV+VH', 'HH', 'HH+HV'",
    )
    orbit_direction: Optional[str] = Field(
        default=None,
        description="Orbit direction: 'ASCENDING' or 'DESCENDING'",
    )
    product_type: str = Field(
        default="GRD",
        description="Sentinel-1 product type: 'GRD' (detected) or 'SLC' (complex)",
    )
    max_results: int = Field(default=5, description="Maximum number of products to return", ge=1, le=20)


class FetchSentinel2Input(BaseModel):
    """Input for the fetch_sentinel2 tool (Copernicus Data Space OData API)."""
    bbox: list[float] = Field(
        ...,
        description="Bounding box [min_lon, min_lat, max_lon, max_lat] in WGS84",
    )
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field(..., description="End date YYYY-MM-DD")
    max_cloud_cover: float = Field(
        default=20.0,
        description="Maximum cloud cover percentage (0–100). Lower = clearer imagery.",
        ge=0.0,
        le=100.0,
    )
    product_type: str = Field(
        default="S2MSI2A",
        description="Product type: 'S2MSI2A' (Level-2A, surface reflectance) or 'S2MSI1C' (Level-1C, TOA)",
    )
    bands: list[str] = Field(
        default_factory=list,
        description="Specific bands to include (empty = all available). E.g. ['B02', 'B03', 'B04', 'B08']",
    )
    max_results: int = Field(default=5, description="Maximum number of products to return", ge=1, le=20)


class FetchLandsatInput(BaseModel):
    """Input for the fetch_landsat tool (USGS M2M API)."""
    bbox: list[float] = Field(
        ...,
        description="Bounding box [min_lon, min_lat, max_lon, max_lat] in WGS84",
    )
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field(..., description="End date YYYY-MM-DD")
    platform: str = Field(
        default="landsat_ot_c2_l2",
        description=(
            "Landsat dataset ID for USGS M2M: "
            "'landsat_ot_c2_l2' (Landsat 8/9 Collection 2 Level-2), "
            "'landsat_etm_c2_l2' (Landsat 7)"
        ),
    )
    max_cloud_cover: float = Field(
        default=20.0,
        description="Maximum cloud cover percentage (0–100)",
        ge=0.0,
        le=100.0,
    )
    max_results: int = Field(default=5, description="Maximum number of scenes to return", ge=1, le=20)


class FetchViirsModisInput(BaseModel):
    """Input for the fetch_viirs_modis tool (NASA CMR API)."""
    bbox: list[float] = Field(
        ...,
        description="Bounding box [min_lon, min_lat, max_lon, max_lat] in WGS84",
    )
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field(..., description="End date YYYY-MM-DD")
    collection: str = Field(
        default="VIIRS_I1_NRT",
        description=(
            "NASA CMR collection short name. Examples: "
            "'VIIRS_I1_NRT' (VIIRS 375m, near-real-time), "
            "'MOD09GA.061' (MODIS Terra daily surface reflectance), "
            "'MYD09GA.061' (MODIS Aqua), "
            "'VNP09GA.001' (VIIRS daily surface reflectance)"
        ),
    )
    sensor: str = Field(
        default="VIIRS",
        description="Sensor name for metadata: 'VIIRS' or 'MODIS'",
    )
    max_results: int = Field(default=10, description="Maximum number of granules to return", ge=1, le=50)


class FetchMultitemporalSentinel2Input(BaseModel):
    """
    Input for the fetch_multitemporal_sentinel2 tool.

    Acquires exactly four Sentinel-2 Level-2A observations spread across the
    requested date range, each with the six Sentinel-2 native bands required
    by the HLS harmonisation step that feeds the Prithvi pipeline:

        B02  (Blue,        490 nm, 10 m)
        B03  (Green,       560 nm, 10 m)
        B04  (Red,         665 nm, 10 m)
        B08A (Narrow NIR,  865 nm, 20 m)  → HLS band position 4
        B11  (SWIR-1,     1610 nm, 20 m)  → HLS band position 5
        B12  (SWIR-2,     2190 nm, 20 m)  → HLS band position 6

    The returned observations are ordered oldest → newest and are validated
    to produce a ready MultiTemporalInput before being returned to GPT-OSS.

    Use this tool (not fetch_sentinel2) when analysis_mode='multitemporal_analysis'
    is set on a detect_change call — i.e. when the Prithvi pipeline will run.
    """
    bbox: list[float] = Field(
        ...,
        description="Bounding box [min_lon, min_lat, max_lon, max_lat] in WGS84",
        examples=[[77.5, 29.0, 80.5, 31.5]],
    )
    start_date: str = Field(
        ...,
        description=(
            "Start of the temporal window YYYY-MM-DD. "
            "The four frames will be distributed across [start_date, end_date]."
        ),
        examples=["2020-01-01"],
    )
    end_date: str = Field(
        ...,
        description="End of the temporal window YYYY-MM-DD.",
        examples=["2024-12-31"],
    )
    max_cloud_cover: float = Field(
        default=20.0,
        description=(
            "Maximum acceptable cloud cover percentage (0–100). "
            "Applied when querying the real Copernicus API. "
            "For monsoon regions consider 50% or higher."
        ),
        ge=0.0,
        le=100.0,
    )
    product_type: str = Field(
        default="S2MSI2A",
        description=(
            "Sentinel-2 product type: 'S2MSI2A' (Level-2A, atmospherically corrected "
            "surface reflectance — strongly preferred for Prithvi) or "
            "'S2MSI1C' (Level-1C, top-of-atmosphere)."
        ),
    )
