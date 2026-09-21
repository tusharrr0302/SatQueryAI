"""
app/tools/fetch_sentinel2.py
─────────────────────────────────────────────────────────────────────────────
The fetch_sentinel2 tool: acquire Sentinel-2 multispectral data from the
Copernicus Data Space Ecosystem via the OData API.

ROLE IN THE ARCHITECTURE:
  Called by GPT-OSS when a query requires optical satellite imagery.
  Examples:
    "Show me deforestation in Uttarakhand between 2020 and 2024"
    "Analyze vegetation health in the Ganges delta"
    "Compare land cover before and after the flood"

  GPT-OSS provides bbox, date range, and cloud cover threshold.
  This tool returns a normalized SatelliteDataset with asset URLs for
  individual band GeoTIFFs.

COPERNICUS ODATA API:
  https://catalogue.dataspace.copernicus.eu/odata/v1
  Requires COPERNICUS_USER and COPERNICUS_PASSWORD in .env
  (only when MODEL_MODE=real)

SENTINEL-2 BANDS:
  10m: B02 (Blue), B03 (Green), B04 (Red), B08 (NIR)
  20m: B05, B06, B07, B8A, B11, B12 (Red-edge, SWIR)
  60m: B01, B09 (Coastal aerosol, Water vapour)
"""

from typing import Any
from loguru import logger

from app.tools.base import BaseTool
from app.services.satellite_data import satellite_service
from app.schemas.requests import FetchSentinel2Input
from app.schemas.responses import ToolResult


class FetchSentinel2Tool(BaseTool):
    """
    Tool: fetch_sentinel2
    Provider: Copernicus Data Space Ecosystem (OData API)
    Task: Acquire Sentinel-2 multispectral optical imagery.
    """

    @property
    def name(self) -> str:
        return "fetch_sentinel2"

    @property
    def description(self) -> str:
        return (
            "Fetch Sentinel-2 multispectral optical satellite imagery from the "
            "Copernicus Data Space Ecosystem. Use this tool when a query requires "
            "optical earth observation data: land cover mapping, vegetation analysis "
            "(NDVI), water body detection (NDWI), agricultural monitoring, urban "
            "growth analysis, deforestation tracking, or any before/after optical "
            "comparison. Sentinel-2 provides 13 spectral bands at 10m, 20m, and 60m "
            "resolution with a 5-day revisit cycle. "
            "Provide a bounding box (bbox), start_date, end_date, and optionally "
            "a maximum cloud cover percentage (default 20%). "
            "For multi-temporal analysis (e.g. comparing 2020 vs 2024), call this "
            "tool TWICE — once for each time period — then pass both results to "
            "detect_change."
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
                        "Bounding box [min_lon, min_lat, max_lon, max_lat] in WGS84 "
                        "(decimal degrees). Example: [77.0, 29.5, 81.0, 31.5] for Uttarakhand."
                    ),
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date YYYY-MM-DD (e.g. '2020-01-01')",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date YYYY-MM-DD (e.g. '2020-03-31')",
                },
                "max_cloud_cover": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "description": (
                        "Maximum acceptable cloud cover percentage (0–100). "
                        "Default 20%. Use lower values for cleaner imagery. "
                        "For monsoon seasons, you may need to increase to 50%."
                    ),
                },
                "product_type": {
                    "type": "string",
                    "enum": ["S2MSI2A", "S2MSI1C"],
                    "description": (
                        "Product type: 'S2MSI2A' (Level-2A, atmospherically corrected "
                        "surface reflectance — preferred for analysis) or "
                        "'S2MSI1C' (Level-1C, top-of-atmosphere)."
                    ),
                },
                "bands": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Specific bands to include. Leave empty for all bands. "
                        "Examples: ['B04', 'B08'] for NDVI; "
                        "['B03', 'B08', 'B11'] for water/vegetation; "
                        "['B02', 'B03', 'B04'] for true colour RGB."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "description": "Maximum number of products to return (default 5).",
                },
            },
            "required": ["bbox", "start_date", "end_date"],
        }

    def execute(self, args: dict[str, Any]) -> ToolResult:
        """
        Execute the fetch_sentinel2 tool.
        Queries Copernicus OData API and returns normalized SatelliteDatasets.
        """
        logger.info(f"[fetch_sentinel2] Executing | args: {args}")

        # ── Validate arguments ────────────────────────────────────────────────
        try:
            validated = FetchSentinel2Input(**args)
        except Exception as e:
            logger.error(f"[fetch_sentinel2] Invalid arguments: {e}")
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData",
                mode="error",
                answer="Invalid arguments for fetch_sentinel2.",
                error=str(e),
            )

        # ── Fetch from provider ───────────────────────────────────────────────
        try:
            datasets = satellite_service.fetch_sentinel2(validated)
        except RuntimeError as e:
            logger.error(f"[fetch_sentinel2] Provider error: {e}")
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData",
                mode="error",
                answer=f"Sentinel-2 data fetch failed: {e}",
                error=str(e),
            )
        except Exception as e:
            logger.exception("[fetch_sentinel2] Unexpected error")
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData",
                mode="error",
                answer="Sentinel-2 data acquisition encountered an unexpected error.",
                error=str(e),
            )

        # ── Build summary ─────────────────────────────────────────────────────
        if not datasets:
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData",
                mode="mock",
                answer=(
                    f"No Sentinel-2 products found for bbox={validated.bbox} "
                    f"between {validated.start_date} and {validated.end_date} "
                    f"with cloud cover ≤{validated.max_cloud_cover}%. "
                    f"Try increasing max_cloud_cover or expanding the date range."
                ),
                artifacts=[],
            )

        mode = datasets[0].mode
        summary_lines = []
        for ds in datasets:
            cloud_str = f"{ds.cloud_cover_pct:.1f}%" if ds.cloud_cover_pct is not None else "N/A"
            summary_lines.append(
                f"  • {ds.product_id} | acquired: {ds.acquisition_time} | "
                f"cloud: {cloud_str} | bands: {len(ds.bands)}"
            )

        answer = (
            f"Retrieved {len(datasets)} Sentinel-2 {validated.product_type} product(s) "
            f"for bbox={validated.bbox} ({validated.start_date} → {validated.end_date}, "
            f"cloud ≤{validated.max_cloud_cover}%):\n"
            + "\n".join(summary_lines)
        )

        return ToolResult(
            tool=self.name,
            model="Copernicus-OData",
            mode=mode,
            answer=answer,
            artifacts=[ds.model_dump() for ds in datasets],
        )
