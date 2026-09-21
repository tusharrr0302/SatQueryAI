"""
app/tools/fetch_multitemporal_sentinel2.py
-----------------------------------------------------------------------------
The fetch_multitemporal_sentinel2 tool: acquire exactly four Sentinel-2
observations spread across a date range for the Prithvi-EO-2.0-300M pipeline.

ROLE IN THE ARCHITECTURE:
  Called by GPT-OSS when the user needs a 4-frame multitemporal EO stack,
  i.e. when analysis_mode='multitemporal_analysis' will be passed to
  detect_change.  Examples:
    "Analyze vegetation loss in Uttarakhand from 2020 to 2024"
    "Show multitemporal land cover change over four years"

  Contrast with fetch_sentinel2, which returns a variable-length list of
  products from a single narrow time window for single-image tasks.
  This tool always returns exactly 4 frames with the 6-band HLS subset.

OUTPUT CONTRACT:
  artifacts[0] = MultiTemporalInput.model_dump()
  The artifact is Pydantic-validated before being placed in the result.
  GPT-OSS can forward this directly to detect_change as the time-series input.

BAND MAPPING:
  Field names are Sentinel-2 native identifiers; the HLS pre-processing step
  that feeds Prithvi maps them to internal band positions:
    S2 B02  -> HLS slot B01  (Blue,        490 nm, 10 m)
    S2 B03  -> HLS slot B02  (Green,       560 nm, 10 m)
    S2 B04  -> HLS slot B03  (Red,         665 nm, 10 m)
    S2 B08A -> HLS slot B04  (Narrow NIR,  865 nm, 20 m)
    S2 B11  -> HLS slot B05  (SWIR-1,     1610 nm, 20 m)
    S2 B12  -> HLS slot B06  (SWIR-2,     2190 nm, 20 m)
"""

from typing import Any
from loguru import logger

from app.tools.base import BaseTool
from app.services.satellite_data import satellite_service
from app.schemas.requests import (
    FetchMultitemporalSentinel2Input,
    MultiTemporalInput,
    TemporalFrame,
    SpectralBands,
)
from app.schemas.responses import ToolResult
from app.schemas.satellite import SatelliteDataset


# ---------------------------------------------------------------------------
# Band -> SpectralBands field mapping
# Used to convert SatelliteAsset lists into SpectralBands instances.
# Keys are the Sentinel-2 native band identifiers stored in SatelliteAsset.band.
# ---------------------------------------------------------------------------
_BAND_FIELD_MAP = {
    "B02":  "B02",
    "B03":  "B03",
    "B04":  "B04",
    "B08A": "B08A",
    "B11":  "B11",
    "B12":  "B12",
}


def _dataset_to_temporal_frame(ds: SatelliteDataset) -> TemporalFrame:
    """
    Convert one SatelliteDataset into a TemporalFrame for MultiTemporalInput.

    Only the six HLS-required bands (B02, B03, B04, B08A, B11, B12) are
    extracted.  Any other bands present in the dataset are ignored because
    MultiTemporalInput / SpectralBands carries only these six.
    """
    band_urls: dict[str, str] = {}
    for asset in ds.assets:
        field = _BAND_FIELD_MAP.get(asset.band)
        if field is not None:
            band_urls[field] = asset.url

    return TemporalFrame(
        acquisition_date=ds.acquisition_time,
        bands=SpectralBands(**band_urls),
    )


class FetchMultitemporalSentinel2Tool(BaseTool):
    """
    Tool: fetch_multitemporal_sentinel2
    Provider: Copernicus Data Space Ecosystem (OData API) -- mock or real
    Task: Acquire exactly 4 Sentinel-2 observations for the Prithvi pipeline.

    Output: MultiTemporalInput -- ready to pass directly to detect_change with
            analysis_mode='multitemporal_analysis'.
    """

    @property
    def name(self) -> str:
        return "fetch_multitemporal_sentinel2"

    @property
    def description(self) -> str:
        return (
            "Acquire exactly four Sentinel-2 Level-2A observations spread across a "
            "date range, specifically for multitemporal EO analysis via the Prithvi "
            "pipeline. "
            "Use this tool -- NOT fetch_sentinel2 -- when analysis_mode='multitemporal_analysis' "
            "will be used with detect_change (i.e. the user wants a multi-year temporal "
            "EO stack such as vegetation loss tracking, land cover change over 3-5 years, "
            "or crop cycle monitoring). "
            "Provide bbox, start_date, end_date (spanning the full period of interest). "
            "The tool always returns exactly 4 observations with 6 bands each "
            "(B02, B03, B04, B08A, B11, B12), ordered oldest to newest, validated as "
            "MultiTemporalInput. The result can be forwarded directly to detect_change."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "bbox": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": (
                        "Bounding box [min_lon, min_lat, max_lon, max_lat] in WGS84. "
                        "Example: [77.0, 29.5, 81.0, 31.5] for Uttarakhand."
                    ),
                },
                "start_date": {
                    "type": "string",
                    "description": (
                        "Start of the temporal window YYYY-MM-DD. "
                        "The four frames will be distributed across "
                        "[start_date, end_date]. Use the earliest year the user mentions."
                    ),
                },
                "end_date": {
                    "type": "string",
                    "description": (
                        "End of the temporal window YYYY-MM-DD. "
                        "Use the latest year the user mentions."
                    ),
                },
                "max_cloud_cover": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "description": (
                        "Maximum cloud cover percentage (0-100). Default 20%. "
                        "Increase to 50% for monsoon-affected regions."
                    ),
                },
                "product_type": {
                    "type": "string",
                    "enum": ["S2MSI2A", "S2MSI1C"],
                    "description": (
                        "'S2MSI2A' (Level-2A, surface reflectance -- required for Prithvi) "
                        "or 'S2MSI1C' (Level-1C, TOA). Default S2MSI2A."
                    ),
                },
            },
            "required": ["bbox", "start_date", "end_date"],
        }

    def execute(self, args: dict[str, Any]) -> ToolResult:
        """
        Fetch 4 Sentinel-2 frames, convert them to MultiTemporalInput, and
        return the validated result as an artifact.
        """
        logger.info(f"[fetch_multitemporal_sentinel2] Executing | args: {args}")

        # -- Validate input arguments ------------------------------------------
        try:
            validated = FetchMultitemporalSentinel2Input(**args)
        except Exception as e:
            logger.error(f"[fetch_multitemporal_sentinel2] Invalid arguments: {e}")
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData/Prithvi-acquisition",
                mode="error",
                answer="Invalid arguments for fetch_multitemporal_sentinel2.",
                error=str(e),
            )

        # -- Fetch 4 datasets from the provider --------------------------------
        try:
            datasets = satellite_service.fetch_multitemporal_sentinel2(validated)
        except RuntimeError as e:
            logger.error(f"[fetch_multitemporal_sentinel2] Provider error: {e}")
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData/Prithvi-acquisition",
                mode="error",
                answer=f"Multitemporal Sentinel-2 acquisition failed: {e}",
                error=str(e),
            )
        except Exception as e:
            logger.exception("[fetch_multitemporal_sentinel2] Unexpected error")
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData/Prithvi-acquisition",
                mode="error",
                answer="Multitemporal acquisition encountered an unexpected error.",
                error=str(e),
            )

        if not datasets:
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData/Prithvi-acquisition",
                mode="mock",
                answer=(
                    f"No Sentinel-2 products found for bbox={validated.bbox} "
                    f"between {validated.start_date} and {validated.end_date}."
                ),
                artifacts=[],
            )

        # -- Convert SatelliteDataset list -> MultiTemporalInput ---------------
        try:
            frames = [_dataset_to_temporal_frame(ds) for ds in datasets]
            mti = MultiTemporalInput(
                frames=frames,
                bbox=validated.bbox,
                query=(
                    f"Multitemporal Sentinel-2 acquisition: "
                    f"{validated.start_date} to {validated.end_date}, "
                    f"bbox={validated.bbox}"
                ),
                # analysis_mode defaults to "multitemporal_analysis"
            )
        except Exception as e:
            logger.error(
                f"[fetch_multitemporal_sentinel2] MultiTemporalInput validation failed: {e}"
            )
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData/Prithvi-acquisition",
                mode="error",
                answer="Acquisition succeeded but the result failed MultiTemporalInput validation.",
                error=str(e),
            )

        # -- Build human-readable summary --------------------------------------
        mode = datasets[0].mode
        frame_lines = [
            f"  frame {i+1}: {ds.acquisition_time} | cloud: "
            f"{ds.cloud_cover_pct:.1f}% | bands: {', '.join(ds.bands)}"
            for i, ds in enumerate(datasets)
        ]
        answer = (
            f"Acquired {len(datasets)} Sentinel-2 frames "
            f"({validated.start_date} to {validated.end_date}, "
            f"bbox={validated.bbox}):\n"
            + "\n".join(frame_lines)
            + "\nResult is a validated MultiTemporalInput ready for the Prithvi pipeline."
        )

        return ToolResult(
            tool=self.name,
            model="Copernicus-OData/Prithvi-acquisition",
            mode=mode,
            answer=answer,
            artifacts=[mti.model_dump()],
        )
