"""
app/tools/fetch_landsat.py
─────────────────────────────────────────────────────────────────────────────
The fetch_landsat tool: acquire Landsat 8/9 data from the USGS M2M API.

ROLE IN THE ARCHITECTURE:
  Called by GPT-OSS when a query requires Landsat imagery. Landsat is
  particularly useful for:
    - Long-term time series (40+ year archive)
    - Multi-spectral analysis at 30m resolution
    - Surface temperature (thermal band ST_B10)
    - Vegetation indices (NDVI, EVI)
    - Water quality and wetland mapping

USGS M2M API:
  https://m2m.cr.usgs.gov/api/api/json/stable/
  Requires USGS_USERNAME and USGS_TOKEN in .env
  (only when MODEL_MODE=real)

  Authentication flow:
    POST /login-token → session API key
    POST /scene-search → scene list
    POST /logout → release session

LANDSAT BANDS (Collection 2 Level-2):
  SR_B2: Blue (0.452–0.512 μm)
  SR_B3: Green (0.533–0.590 μm)
  SR_B4: Red (0.636–0.673 μm)
  SR_B5: NIR (0.851–0.879 μm)
  SR_B6: SWIR-1 (1.566–1.651 μm)
  SR_B7: SWIR-2 (2.107–2.294 μm)
  ST_B10: Thermal Infrared / Surface Temperature
"""

from typing import Any
from loguru import logger

from app.tools.base import BaseTool
from app.services.satellite_data import satellite_service
from app.schemas.requests import FetchLandsatInput
from app.schemas.responses import ToolResult


class FetchLandsatTool(BaseTool):
    """
    Tool: fetch_landsat
    Provider: USGS M2M JSON API
    Task: Acquire Landsat 8 / Landsat 9 multispectral + thermal imagery.
    """

    @property
    def name(self) -> str:
        return "fetch_landsat"

    @property
    def description(self) -> str:
        return (
            "Fetch Landsat 8 or Landsat 9 satellite imagery from the USGS M2M API. "
            "Use this tool when a query requires Landsat data specifically, or when "
            "long-term historical analysis is needed (Landsat archive extends to 1972). "
            "Landsat 8/9 provides 7 spectral bands at 30m resolution plus a thermal band "
            "(surface temperature) at 30m. "
            "Best for: multi-decadal land cover change, surface temperature mapping, "
            "fire burn scar assessment, agricultural field analysis, water quality, "
            "HLS (Harmonized Landsat-Sentinel) compatible analysis with Prithvi models. "
            "Collection 2 Level-2 (atmospherically corrected surface reflectance) is "
            "the preferred product type. "
            "Provide bbox, start_date, end_date, and optionally max_cloud_cover."
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
                        "Example: [73.0, 18.0, 77.0, 22.0] for central India."
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
                "platform": {
                    "type": "string",
                    "description": (
                        "USGS dataset ID: "
                        "'landsat_ot_c2_l2' for Landsat 8/9 Collection 2 Level-2 (recommended), "
                        "'landsat_etm_c2_l2' for Landsat 7."
                    ),
                },
                "max_cloud_cover": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Maximum cloud cover percentage (0–100, default 20).",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "description": "Maximum number of scenes to return (default 5).",
                },
            },
            "required": ["bbox", "start_date", "end_date"],
        }

    def execute(self, args: dict[str, Any]) -> ToolResult:
        """Execute the fetch_landsat tool via USGS M2M scene-search."""
        logger.info(f"[fetch_landsat] Executing | args: {args}")

        try:
            validated = FetchLandsatInput(**args)
        except Exception as e:
            logger.error(f"[fetch_landsat] Invalid arguments: {e}")
            return ToolResult(
                tool=self.name,
                model="USGS-M2M",
                mode="error",
                answer="Invalid arguments for fetch_landsat.",
                error=str(e),
            )

        try:
            datasets = satellite_service.fetch_landsat(validated)
        except RuntimeError as e:
            logger.error(f"[fetch_landsat] Provider error: {e}")
            return ToolResult(
                tool=self.name,
                model="USGS-M2M",
                mode="error",
                answer=f"Landsat data fetch failed: {e}",
                error=str(e),
            )
        except Exception as e:
            logger.exception("[fetch_landsat] Unexpected error")
            return ToolResult(
                tool=self.name,
                model="USGS-M2M",
                mode="error",
                answer="Landsat data acquisition encountered an unexpected error.",
                error=str(e),
            )

        if not datasets:
            return ToolResult(
                tool=self.name,
                model="USGS-M2M",
                mode="mock",
                answer=(
                    f"No Landsat scenes found for bbox={validated.bbox} "
                    f"between {validated.start_date} and {validated.end_date} "
                    f"with cloud cover ≤{validated.max_cloud_cover}%. "
                    f"Try expanding the date range or bounding box."
                ),
                artifacts=[],
            )

        mode = datasets[0].mode
        summary_lines = []
        for ds in datasets:
            cloud_str = f"{ds.cloud_cover_pct:.1f}%" if ds.cloud_cover_pct is not None else "N/A"
            summary_lines.append(
                f"  • {ds.product_id} | platform: {ds.platform} | "
                f"acquired: {ds.acquisition_time} | cloud: {cloud_str}"
            )

        answer = (
            f"Retrieved {len(datasets)} Landsat scene(s) for bbox={validated.bbox} "
            f"({validated.start_date} → {validated.end_date}):\n"
            + "\n".join(summary_lines)
        )

        return ToolResult(
            tool=self.name,
            model="USGS-M2M",
            mode=mode,
            answer=answer,
            artifacts=[ds.model_dump() for ds in datasets],
        )
