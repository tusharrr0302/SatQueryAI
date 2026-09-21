"""
app/tools/fetch_sentinel1.py
─────────────────────────────────────────────────────────────────────────────
The fetch_sentinel1 tool: acquire Sentinel-1 SAR data from the Copernicus
Data Space Ecosystem via the OData API.

ROLE IN THE ARCHITECTURE:
  This tool is called by GPT-OSS when a query requires SAR satellite data.
  Example: "Show me flood extent in Nepal using Sentinel-1 SAR"

  GPT-OSS provides the bounding box, date range, and SAR parameters.
  This tool queries the Copernicus OData API and returns a normalized
  SatelliteDataset in the ToolResult.artifacts list.

  The returned SatelliteDataset is then available for the orchestrator
  to pass to specialist analysis tools (analyze_sar_optical, detect_change).

COPERNICUS ODATA API:
  https://catalogue.dataspace.copernicus.eu/odata/v1
  Requires COPERNICUS_USER and COPERNICUS_PASSWORD in .env
  (only when MODEL_MODE=real)
"""

import json
from typing import Any
from loguru import logger

from app.tools.base import BaseTool
from app.services.satellite_data import satellite_service
from app.schemas.requests import FetchSentinel1Input
from app.schemas.responses import ToolResult


class FetchSentinel1Tool(BaseTool):
    """
    Tool: fetch_sentinel1
    Provider: Copernicus Data Space Ecosystem (OData API)
    Task: Acquire Sentinel-1 SAR imagery for a given area and time range.
    """

    @property
    def name(self) -> str:
        return "fetch_sentinel1"

    @property
    def description(self) -> str:
        return (
            "Fetch Sentinel-1 Synthetic Aperture Radar (SAR) satellite data from the "
            "Copernicus Data Space Ecosystem. Use this tool when a query involves SAR "
            "observations such as: flood mapping through clouds, building damage "
            "assessment, ship detection, soil moisture estimation, or any case requiring "
            "cloud-penetrating radar imagery. "
            "Sentinel-1 operates in C-band with VV and VH polarizations at 10m resolution "
            "(IW GRD mode). SAR imagery is NOT affected by cloud cover. "
            "Provide a bounding box (bbox), start_date, and end_date. "
            "The result contains asset URLs for SAR GeoTIFF files. "
            "After fetching, pass the result to analyze_sar_optical for cross-modal analysis, "
            "or to detect_change for multi-temporal SAR comparison."
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
                        "(decimal degrees). Example: [80.0, 27.5, 82.5, 29.0] for Nepal."
                    ),
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in ISO 8601 format: YYYY-MM-DD (e.g. '2024-06-01')",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in ISO 8601 format: YYYY-MM-DD (e.g. '2024-06-15')",
                },
                "polarization": {
                    "type": "string",
                    "enum": ["VV", "VH", "VV+VH", "HH", "HH+HV"],
                    "description": "SAR polarization. Default 'VV' for general use; 'VV+VH' for dual-pol.",
                },
                "orbit_direction": {
                    "type": "string",
                    "enum": ["ASCENDING", "DESCENDING"],
                    "description": "Optional orbit direction. Omit to accept both.",
                },
                "product_type": {
                    "type": "string",
                    "enum": ["GRD", "SLC"],
                    "description": "Product type: 'GRD' for detected (intensity), 'SLC' for complex.",
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
        Execute the fetch_sentinel1 tool.
        Queries Copernicus OData API and returns normalized SatelliteDatasets.
        """
        logger.info(f"[fetch_sentinel1] Executing | args: {args}")

        # ── Validate arguments ────────────────────────────────────────────────
        try:
            validated = FetchSentinel1Input(**args)
        except Exception as e:
            logger.error(f"[fetch_sentinel1] Invalid arguments: {e}")
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData",
                mode="error",
                answer="Invalid arguments for fetch_sentinel1.",
                error=str(e),
            )

        # ── Fetch from provider ───────────────────────────────────────────────
        try:
            datasets = satellite_service.fetch_sentinel1(validated)
        except RuntimeError as e:
            logger.error(f"[fetch_sentinel1] Provider error: {e}")
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData",
                mode="error",
                answer=f"Sentinel-1 data fetch failed: {e}",
                error=str(e),
            )
        except Exception as e:
            logger.exception("[fetch_sentinel1] Unexpected error")
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData",
                mode="error",
                answer="Sentinel-1 data acquisition encountered an unexpected error.",
                error=str(e),
            )

        # ── Build summary ─────────────────────────────────────────────────────
        if not datasets:
            return ToolResult(
                tool=self.name,
                model="Copernicus-OData",
                mode=validated.product_type,
                answer=(
                    f"No Sentinel-1 products found for bbox={validated.bbox} "
                    f"between {validated.start_date} and {validated.end_date}. "
                    f"Try expanding the date range or bounding box."
                ),
                artifacts=[],
            )

        mode = datasets[0].mode
        summary_lines = []
        for ds in datasets:
            summary_lines.append(
                f"  • {ds.product_id} | acquired: {ds.acquisition_time} | "
                f"bands: {', '.join(ds.bands)}"
            )

        answer = (
            f"Retrieved {len(datasets)} Sentinel-1 {validated.product_type} product(s) "
            f"for bbox={validated.bbox} ({validated.start_date} → {validated.end_date}):\n"
            + "\n".join(summary_lines)
        )

        return ToolResult(
            tool=self.name,
            model="Copernicus-OData",
            mode=mode,
            answer=answer,
            artifacts=[ds.model_dump() for ds in datasets],
        )
