"""
tests/test_multitemporal_acquisition.py
-----------------------------------------------------------------------------
Tests for the multitemporal Sentinel-2 acquisition layer (Step 2).

These tests verify:
  1. The tool returns exactly 4 frames
  2. Frames are ordered oldest -> newest (chronological)
  3. Every frame contains all 6 HLS-required Sentinel-2 bands
  4. Acquisition metadata (bbox, source, mode) is preserved
  5. The result satisfies MultiTemporalInput Pydantic validation
  6. Existing single-image satellite acquisition tools are unaffected

Band naming note:
  Field names in SpectralBands are Sentinel-2 native identifiers
  (B02, B03, B04, B08A, B11, B12).  They are NOT Prithvi internal indices.
  The HLS harmonisation step handles the mapping to internal band positions.

Run with:
  cd ai-service
  pytest tests/test_multitemporal_acquisition.py -v
"""

import pytest
from app.tools.fetch_multitemporal_sentinel2 import FetchMultitemporalSentinel2Tool
from app.tools.fetch_sentinel2 import FetchSentinel2Tool
from app.tools.fetch_sentinel1 import FetchSentinel1Tool
from app.schemas.responses import ToolResult
from app.schemas.satellite import SatelliteDataset
from app.schemas.requests import MultiTemporalInput


SAMPLE_BBOX = [77.5, 29.0, 80.5, 31.5]  # Uttarakhand, India


class TestFetchMultitemporalSentinel2Tool:
    """Tests for the new fetch_multitemporal_sentinel2 tool."""

    def setup_method(self):
        self.tool = FetchMultitemporalSentinel2Tool()

    # -- Test 1: exactly four frames ------------------------------------------

    def test_returns_exactly_four_frames(self):
        """The tool must return a result with exactly 4 frames in the artifact."""
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert isinstance(result, ToolResult)
        assert result.error is None, f"Unexpected error: {result.error}"
        assert len(result.artifacts) == 1

        mti = MultiTemporalInput(**result.artifacts[0])
        assert len(mti.frames) == 4

    def test_tool_name(self):
        assert self.tool.name == "fetch_multitemporal_sentinel2"

    def test_input_schema_requires_bbox_start_end(self):
        schema = self.tool.input_schema
        required = schema.get("required", [])
        assert "bbox" in required
        assert "start_date" in required
        assert "end_date" in required

    def test_missing_required_field_returns_error(self):
        """Missing bbox must return ToolResult with error, not raise."""
        result = self.tool.execute({
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert isinstance(result, ToolResult)
        assert result.error is not None

    # -- Test 2: chronological ordering ---------------------------------------

    def test_frames_are_chronologically_ordered(self):
        """Frames must be ordered oldest -> newest by acquisition_date."""
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert result.error is None

        mti = MultiTemporalInput(**result.artifacts[0])
        dates = [f.acquisition_date for f in mti.frames]
        assert dates == sorted(dates), (
            f"Frames are not chronologically ordered: {dates}"
        )

    def test_frame_dates_span_requested_window(self):
        """All 4 frame dates must fall within [start_date, end_date]."""
        start = "2020-01-01"
        end = "2024-12-31"
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": start,
            "end_date": end,
        })
        assert result.error is None

        mti = MultiTemporalInput(**result.artifacts[0])
        for frame in mti.frames:
            # acquisition_date is ISO 8601; simple string comparison works here
            assert frame.acquisition_date[:10] >= start, (
                f"Frame date {frame.acquisition_date} is before start {start}"
            )
            assert frame.acquisition_date[:10] <= end, (
                f"Frame date {frame.acquisition_date} is after end {end}"
            )

    # -- Test 3: six bands present ---------------------------------------------

    def test_every_frame_has_all_six_hls_bands(self):
        """
        Every frame must carry assets for all 6 HLS-required S2 bands:
        B02, B03, B04, B08A, B11, B12.
        Band names are Sentinel-2 native identifiers, not Prithvi internal indices.
        """
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert result.error is None

        mti = MultiTemporalInput(**result.artifacts[0])
        required_bands = {"B02", "B03", "B04", "B08A", "B11", "B12"}
        for i, frame in enumerate(mti.frames):
            present = {
                b for b in ("B02", "B03", "B04", "B08A", "B11", "B12")
                if getattr(frame.bands, b) is not None
            }
            assert present == required_bands, (
                f"Frame {i} is missing bands: {required_bands - present}"
            )

    def test_band_urls_use_mock_scheme(self):
        """Mock mode band URLs must use mock:// to be unambiguous about data origin."""
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert result.error is None

        mti = MultiTemporalInput(**result.artifacts[0])
        for frame in mti.frames:
            for band_name in ("B02", "B03", "B04", "B08A", "B11", "B12"):
                url = getattr(frame.bands, band_name)
                assert url is not None
                assert url.startswith("mock://"), (
                    f"Band {band_name} URL is not a mock:// URL: {url}"
                )

    # -- Test 4: metadata preservation ----------------------------------------

    def test_bbox_preserved_in_result(self):
        """bbox from input must be preserved in the MultiTemporalInput artifact."""
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert result.error is None

        mti = MultiTemporalInput(**result.artifacts[0])
        assert mti.bbox == SAMPLE_BBOX

    def test_mode_is_mock(self):
        """In mock mode, ToolResult.mode must be 'mock'."""
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert result.mode == "mock"

    def test_source_is_sentinel2(self):
        """Raw SatelliteDataset artifacts before conversion must identify source as sentinel-2."""
        from app.services.satellite_data import satellite_service
        from app.schemas.requests import FetchMultitemporalSentinel2Input

        params = FetchMultitemporalSentinel2Input(
            bbox=SAMPLE_BBOX,
            start_date="2020-01-01",
            end_date="2024-12-31",
        )
        datasets = satellite_service.fetch_multitemporal_sentinel2(params)
        assert len(datasets) == 4
        for ds in datasets:
            assert ds.source == "sentinel-2"
            assert ds.sensor == "optical"
            assert ds.mode == "mock"

    # -- Test 5: MultiTemporalInput compatibility ------------------------------

    def test_artifact_validates_as_multitemporal_input(self):
        """The artifact dict must be directly usable as MultiTemporalInput(**artifact)."""
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        assert result.error is None
        assert len(result.artifacts) == 1

        # This must not raise
        mti = MultiTemporalInput(**result.artifacts[0])
        assert mti.analysis_mode == "multitemporal_analysis"

    def test_analysis_mode_is_fixed(self):
        """analysis_mode in the artifact must always be 'multitemporal_analysis'."""
        result = self.tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        })
        mti = MultiTemporalInput(**result.artifacts[0])
        assert mti.analysis_mode == "multitemporal_analysis"

    def test_to_openai_function_format(self):
        spec = self.tool.to_openai_function()
        assert spec["type"] == "function"
        assert spec["function"]["name"] == "fetch_multitemporal_sentinel2"
        assert "parameters" in spec["function"]

    # -- Test 6: existing acquisition tools unaffected ------------------------


class TestExistingAcquisitionToolsUnaffected:
    """
    Regression: all four existing single-image acquisition tools must continue
    to work correctly after the multitemporal layer was added.
    """

    def test_fetch_sentinel2_still_returns_variable_list(self):
        """
        fetch_sentinel2 must still return a variable-length list artifact,
        NOT a MultiTemporalInput. It must not be tied to the 4-frame contract.
        """
        tool = FetchSentinel2Tool()
        result = tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": "2024-06-01",
            "end_date": "2024-06-15",
        })
        assert result.error is None
        assert len(result.artifacts) > 0
        # artifact must parse as SatelliteDataset, NOT as MultiTemporalInput
        ds = SatelliteDataset(**result.artifacts[0])
        assert ds.source == "sentinel-2"
        assert ds.mode == "mock"

    def test_fetch_sentinel1_unaffected(self):
        tool = FetchSentinel1Tool()
        result = tool.execute({
            "bbox": SAMPLE_BBOX,
            "start_date": "2024-06-01",
            "end_date": "2024-06-15",
        })
        assert result.error is None
        ds = SatelliteDataset(**result.artifacts[0])
        assert ds.source == "sentinel-1"
        assert ds.sensor == "sar"
