"""
app/tools/fetch_viirs_modis.py
─────────────────────────────────────────────────────────────────────────────
The fetch_viirs_modis tool: acquire VIIRS and MODIS data from NASA CMR.

ROLE IN THE ARCHITECTURE:
  Called by GPT-OSS when coarse-resolution, wide-area, or near-real-time
  data is needed. VIIRS/MODIS complement Sentinel and Landsat for:
    - Active fire / hotspot detection (near-real-time)
    - Aerosol optical depth / air quality
    - Sea surface temperature
    - Ocean colour / chlorophyll
    - Snow and ice cover
    - Vegetation phenology at continental scale

NASA CMR API:
  https://cmr.earthdata.nasa.gov/search
  Public API — no authentication required for most collections.
  Docs: https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html

COMMON COLLECTIONS:
  VIIRS (Suomi NPP / JPSS):
    VNP09GA.001   — VIIRS/NPP Surface Reflectance Daily 500m
    VNP14IMGTDL_NRT — VIIRS Near Real-Time Active Fire
    VJ109GA.002   — VIIRS/J1 Surface Reflectance 375m

  MODIS:
    MOD09GA.061   — MODIS Terra Daily 500m Surface Reflectance
    MYD09GA.061   — MODIS Aqua Daily 500m Surface Reflectance
    MOD11A1.061   — MODIS Land Surface Temperature / Emissivity
    MOD44W.006    — MODIS Water Mask
"""

from typing import Any
from loguru import logger

from app.tools.base import BaseTool
from app.services.satellite_data import satellite_service
from app.schemas.requests import FetchViirsModisInput
from app.schemas.responses import ToolResult


class FetchViirsModisTool(BaseTool):
    """
    Tool: fetch_viirs_modis
    Provider: NASA Common Metadata Repository (CMR)
    Task: Acquire VIIRS or MODIS data for wide-area or high-frequency analysis.
    """

    @property
    def name(self) -> str:
        return "fetch_viirs_modis"

    @property
    def description(self) -> str:
        return (
            "Fetch VIIRS or MODIS satellite data from NASA's Common Metadata Repository (CMR). "
            "Use this tool for wide-area, coarse-resolution observations or near-real-time data. "
            "Best for: active fire / hotspot detection, aerosol and air quality, "
            "sea surface temperature, ocean chlorophyll, snow/ice cover, large-scale "
            "vegetation monitoring, and continental-scale time series. "
            "VIIRS provides 375m and 750m resolution with daily global coverage. "
            "MODIS provides 250m–1000m resolution. "
            "For high-resolution analysis (10–30m), use fetch_sentinel2 or fetch_landsat instead. "
            "Provide bbox, start_date, end_date, and the collection short_name. "
            "Common collections: 'VNP09GA.001' (VIIRS surface reflectance), "
            "'MOD09GA.061' (MODIS Terra), 'VNP14IMGTDL_NRT' (VIIRS active fire near-real-time)."
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
                        "VIIRS/MODIS cover wide areas — larger bounding boxes are fine."
                    ),
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date YYYY-MM-DD",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date YYYY-MM-DD",
                },
                "collection": {
                    "type": "string",
                    "description": (
                        "NASA CMR collection short name. Examples: "
                        "'VNP09GA.001' (VIIRS NPP 500m surface reflectance), "
                        "'VNP14IMGTDL_NRT' (VIIRS near-real-time active fire), "
                        "'MOD09GA.061' (MODIS Terra daily), "
                        "'MYD09GA.061' (MODIS Aqua daily), "
                        "'MOD11A1.061' (MODIS land surface temperature), "
                        "'VJ109GA.002' (VIIRS/JPSS-1 surface reflectance)."
                    ),
                },
                "sensor": {
                    "type": "string",
                    "enum": ["VIIRS", "MODIS"],
                    "description": "Sensor name for metadata labelling.",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum number of granules to return (default 10).",
                },
            },
            "required": ["bbox", "start_date", "end_date"],
        }

    def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute the fetch_viirs_modis tool via NASA CMR search."""
        logger.info(f"[fetch_viirs_modis] Executing | args: {args}")

        try:
            validated = FetchViirsModisInput(**args)
        except Exception as e:
            logger.error(f"[fetch_viirs_modis] Invalid arguments: {e}")
            return ToolResult(
                tool=self.name,
                model="NASA-CMR",
                mode="error",
                answer="Invalid arguments for fetch_viirs_modis.",
                error=str(e),
            )

        try:
            datasets = satellite_service.fetch_viirs_modis(validated)
        except RuntimeError as e:
            logger.error(f"[fetch_viirs_modis] Provider error: {e}")
            return ToolResult(
                tool=self.name,
                model="NASA-CMR",
                mode="error",
                answer=f"VIIRS/MODIS data fetch failed: {e}",
                error=str(e),
            )
        except Exception as e:
            logger.exception("[fetch_viirs_modis] Unexpected error")
            return ToolResult(
                tool=self.name,
                model="NASA-CMR",
                mode="error",
                answer="VIIRS/MODIS data acquisition encountered an unexpected error.",
                error=str(e),
            )

        if not datasets:
            return ToolResult(
                tool=self.name,
                model="NASA-CMR",
                mode="mock",
                answer=(
                    f"No {validated.collection} granules found for bbox={validated.bbox} "
                    f"between {validated.start_date} and {validated.end_date}. "
                    f"Try a different collection name or expanding the date range."
                ),
                artifacts=[],
            )

        mode = datasets[0].mode
        summary_lines = []
        for ds in datasets:
            summary_lines.append(
                f"  • {ds.product_id} | acquired: {ds.acquisition_time} | "
                f"bbox: {[round(c, 2) for c in ds.bbox]}"
            )

        answer = (
            f"Retrieved {len(datasets)} {validated.collection} granule(s) "
            f"({validated.sensor}) for bbox={validated.bbox} "
            f"({validated.start_date} → {validated.end_date}):\n"
            + "\n".join(summary_lines)
        )

        return ToolResult(
            tool=self.name,
            model="NASA-CMR",
            mode=mode,
            answer=answer,
            artifacts=[ds.model_dump() for ds in datasets],
        )
