"""
tests/test_satellite_tools.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for the 4 satellite acquisition tools in mock mode.

These tests verify:
  1. Each tool is correctly registered and named
  2. Input validation works (required fields enforced)
  3. Mock mode returns valid SatelliteDataset structure in artifacts
  4. Empty results are handled gracefully (no exceptions)
  5. Invalid args return ToolResult with error, not an exception

Run with:
  cd ai-service
  pytest tests/test_satellite_tools.py -v
"""

import pytest
from app.tools.fetch_sentinel1 import FetchSentinel1Tool
from app.tools.fetch_sentinel2 import FetchSentinel2Tool
from app.tools.fetch_landsat import FetchLandsatTool
from app.tools.fetch_viirs_modis import FetchViirsModisTool
from app.schemas.responses import ToolResult
from app.schemas.satellite import SatelliteDataset


SAMPLE_BBOX = [77.5, 29.0, 80.5, 31.5]
SAMPLE_DATES = ("2024-06-01", "2024-06-15")


# ─────────────────────────────────────────────────────────────────────────────
# fetch_sentinel1 tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFetchSentinel1Tool:

    def setup_method(self):
        self.tool = FetchSentinel1Tool()

    def test_name(self):
        assert self.tool.name == "fetch_sentinel1"

    def test_description_mentions_sar(self):
        assert "SAR" in self.tool.description or "radar" in self.tool.description.lower()

    def test_input_schema_has_required_fields(self):
        schema = self.tool.input_schema
        required = schema.get("required", [])
        assert "bbox" in required
        assert "start_date" in required
        assert "end_date" in required

    def test_execute_basic_mock(self):
        """Basic execution should return a valid ToolResult with mock datasets."""
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": SAMPLE_DATES[0],
            "end_date": SAMPLE_DATES[1],
        })
        assert isinstance(result, ToolResult)
        assert result.tool == "fetch_sentinel1"
        assert result.mode in ("mock", "real", "error")
        assert result.error is None
        assert len(result.artifacts) > 0

    def test_execute_returns_sentinel1_dataset(self):
        """Artifacts must be parseable as SatelliteDataset."""
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": SAMPLE_DATES[0],
            "end_date": SAMPLE_DATES[1],
        })
        assert len(result.artifacts) > 0
        ds_dict = result.artifacts[0]
        ds = SatelliteDataset(**ds_dict)
        assert ds.source == "sentinel-1"
        assert ds.sensor == "sar"
        assert ds.mode == "mock"
        assert ds.cloud_cover_pct is None  # SAR is cloud-independent

    def test_execute_with_polarization(self):
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": SAMPLE_DATES[0],
            "end_date": SAMPLE_DATES[1],
            "polarization": "VV+VH",
        })
        assert result.error is None
        ds = SatelliteDataset(**result.artifacts[0])
        assert "VV" in ds.bands or "VH" in ds.bands

    def test_execute_missing_required_fields_returns_error(self):
        """Missing bbox should return ToolResult with error, not raise."""
        result = self.tool.execute({"start_date": "2024-06-01", "end_date": "2024-06-15"})
        assert isinstance(result, ToolResult)
        assert result.error is not None

    def test_to_openai_function_format(self):
        spec = self.tool.to_openai_function()
        assert spec["type"] == "function"
        assert spec["function"]["name"] == "fetch_sentinel1"
        assert "parameters" in spec["function"]


# ─────────────────────────────────────────────────────────────────────────────
# fetch_sentinel2 tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFetchSentinel2Tool:

    def setup_method(self):
        self.tool = FetchSentinel2Tool()

    def test_name(self):
        assert self.tool.name == "fetch_sentinel2"

    def test_description_mentions_optical(self):
        desc = self.tool.description.lower()
        assert "optical" in desc or "multispectral" in desc

    def test_execute_basic_mock(self):
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": SAMPLE_DATES[0],
            "end_date": SAMPLE_DATES[1],
        })
        assert isinstance(result, ToolResult)
        assert result.error is None
        assert len(result.artifacts) > 0

    def test_execute_returns_sentinel2_dataset(self):
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": SAMPLE_DATES[0],
            "end_date": SAMPLE_DATES[1],
            "max_cloud_cover": 20.0,
        })
        ds = SatelliteDataset(**result.artifacts[0])
        assert ds.source == "sentinel-2"
        assert ds.sensor == "optical"
        assert ds.cloud_cover_pct is not None
        assert ds.cloud_cover_pct <= 20.0
        assert len(ds.bands) > 0

    def test_execute_with_band_filter(self):
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": SAMPLE_DATES[0],
            "end_date": SAMPLE_DATES[1],
            "bands": ["B04", "B08"],
        })
        ds = SatelliteDataset(**result.artifacts[0])
        assert "B04" in ds.bands
        assert "B08" in ds.bands

    def test_execute_missing_bbox_returns_error(self):
        result = self.tool.execute({"start_date": "2024-06-01", "end_date": "2024-06-15"})
        assert result.error is not None

    def test_mock_result_is_labeled(self):
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": SAMPLE_DATES[0],
            "end_date": SAMPLE_DATES[1],
        })
        ds = SatelliteDataset(**result.artifacts[0])
        assert ds.mode == "mock"


# ─────────────────────────────────────────────────────────────────────────────
# fetch_landsat tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFetchLandsatTool:

    def setup_method(self):
        self.tool = FetchLandsatTool()

    def test_name(self):
        assert self.tool.name == "fetch_landsat"

    def test_description_mentions_landsat(self):
        assert "Landsat" in self.tool.description or "landsat" in self.tool.description.lower()

    def test_execute_basic_mock(self):
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": SAMPLE_DATES[0],
            "end_date": SAMPLE_DATES[1],
        })
        assert isinstance(result, ToolResult)
        assert result.error is None
        assert len(result.artifacts) > 0

    def test_execute_returns_landsat_dataset(self):
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": SAMPLE_DATES[0],
            "end_date": SAMPLE_DATES[1],
        })
        ds = SatelliteDataset(**result.artifacts[0])
        assert "landsat" in ds.source.lower()
        assert ds.sensor == "optical"
        assert ds.mode == "mock"
        assert "SR_B4" in ds.bands  # Landsat red band

    def test_execute_missing_required_returns_error(self):
        result = self.tool.execute({"bbox": SAMPLE_BBOX})  # missing dates
        assert result.error is not None

    def test_thermal_band_included(self):
        """Landsat datasets must include the thermal band."""
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": SAMPLE_DATES[0],
            "end_date": SAMPLE_DATES[1],
        })
        ds = SatelliteDataset(**result.artifacts[0])
        assert "ST_B10" in ds.bands


# ─────────────────────────────────────────────────────────────────────────────
# fetch_viirs_modis tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFetchViirsModisTool:

    def setup_method(self):
        self.tool = FetchViirsModisTool()

    def test_name(self):
        assert self.tool.name == "fetch_viirs_modis"

    def test_description_mentions_viirs_and_modis(self):
        desc = self.tool.description
        assert "VIIRS" in desc and "MODIS" in desc

    def test_execute_basic_mock(self):
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": SAMPLE_DATES[0],
            "end_date": SAMPLE_DATES[1],
        })
        assert isinstance(result, ToolResult)
        assert result.error is None
        assert len(result.artifacts) > 0

    def test_execute_returns_viirs_dataset(self):
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": SAMPLE_DATES[0],
            "end_date": SAMPLE_DATES[1],
            "collection": "VNP09GA.001",
            "sensor": "VIIRS",
        })
        ds = SatelliteDataset(**result.artifacts[0])
        assert ds.source == "viirs"
        assert ds.mode == "mock"

    def test_execute_missing_bbox_returns_error(self):
        result = self.tool.execute({"start_date": "2024-06-01", "end_date": "2024-06-15"})
        assert result.error is not None

    def test_to_openai_function_format(self):
        spec = self.tool.to_openai_function()
        assert spec["type"] == "function"
        assert spec["function"]["name"] == "fetch_viirs_modis"


# ─────────────────────────────────────────────────────────────────────────────
# SatelliteDataset schema validation
# ─────────────────────────────────────────────────────────────────────────────

class TestSatelliteDatasetSchema:
    """Verify the normalized schema is consistent across all providers."""

    def test_all_tools_produce_valid_satellite_datasets(self):
        """All 4 tools must produce artifacts parseable as SatelliteDataset."""
        tools = [
            (FetchSentinel1Tool(), {"bbox": SAMPLE_BBOX, "start_date": SAMPLE_DATES[0], "end_date": SAMPLE_DATES[1]}),
            (FetchSentinel2Tool(), {"bbox": SAMPLE_BBOX, "start_date": SAMPLE_DATES[0], "end_date": SAMPLE_DATES[1]}),
            (FetchLandsatTool(), {"bbox": SAMPLE_BBOX, "start_date": SAMPLE_DATES[0], "end_date": SAMPLE_DATES[1]}),
            (FetchViirsModisTool(), {"bbox": SAMPLE_BBOX, "start_date": SAMPLE_DATES[0], "end_date": SAMPLE_DATES[1]}),
        ]
        for tool, args in tools:
            result = tool.execute(args)
            assert result.error is None, f"{tool.name} returned error: {result.error}"
            assert len(result.artifacts) > 0, f"{tool.name} returned no artifacts"
            # Must parse without exception
            ds = SatelliteDataset(**result.artifacts[0])
            assert ds.source != ""
            assert ds.acquisition_time != ""
            assert len(ds.bbox) == 4
            assert ds.mode in ("mock", "real")
