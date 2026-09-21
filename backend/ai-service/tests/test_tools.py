"""
tests/test_tools.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for all three specialist tools in mock mode.

These tests verify:
  1. Each tool's execute() returns a valid ToolResult
  2. Mock mode is clearly labelled (mode="mock")
  3. Required fields are never None
  4. Error handling works when given invalid args

Run with:
  cd ai-service
  pytest tests/test_tools.py -v
"""

import pytest
from app.tools.analyze_image import AnalyzeImageTool
from app.tools.detect_change import DetectChangeTool
from app.tools.analyze_sar_optical import AnalyzeSarOpticalTool
from app.schemas.responses import ToolResult
from app.schemas.requests import MultiTemporalInput, SpectralBands, TemporalFrame
from pydantic import ValidationError



# ─────────────────────────────────────────────────────────────────────────────
# analyze_image tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeImageTool:

    def setup_method(self):
        """Instantiate the tool before each test."""
        self.tool = AnalyzeImageTool()

    def test_name(self):
        assert self.tool.name == "analyze_image"

    def test_description_not_empty(self):
        assert len(self.tool.description) > 10

    def test_input_schema_has_required_fields(self):
        schema = self.tool.input_schema
        assert "properties" in schema
        assert "query" in schema["properties"]
        assert "image" in schema["properties"]
        assert "required" in schema
        assert "query" in schema["required"]
        assert "image" in schema["required"]


    def test_execute_with_image_path(self):
        result = self.tool.execute({
            "query": "Describe the land cover.",
            "image": "/path/to/image.tif",
            "metadata": {"satellite": "Sentinel-2"},
        })
        assert isinstance(result, ToolResult)
        assert "[MOCK" in result.answer  # Mock result must be labelled

    def test_execute_invalid_args_returns_error_result(self):
        """Extra garbage args should not crash — ToolResult with error."""
        result = self.tool.execute({})  # Missing required 'query'
        assert isinstance(result, ToolResult)
        assert result.error is not None

    def test_to_openai_function_format(self):
        """Must return the OpenAI function-call spec format."""
        spec = self.tool.to_openai_function()
        assert spec["type"] == "function"
        assert "function" in spec
        assert spec["function"]["name"] == "analyze_image"
        assert "parameters" in spec["function"]


# ─────────────────────────────────────────────────────────────────────────────
# detect_change tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectChangeTool:

    def setup_method(self):
        self.tool = DetectChangeTool()

    def test_name(self):
        assert self.tool.name == "detect_change"

    def test_execute_basic(self):
        result = self.tool.execute({
            "query": "What changed between these two images?",
            "image_t1": "/path/before.tif",
            "image_t2": "/path/after.tif",
        })
        assert isinstance(result, ToolResult)
        assert result.mode == "mock"
        assert result.error is None
        assert result.answer

    def test_execute_question_change_mode_accepted(self):
        """analysis_mode='question_change' must be accepted and routes to VisTA."""
        result = self.tool.execute({
            "query": "What changed between the two images?",
            "image_t1": "/path/before.tif",
            "image_t2": "/path/after.tif",
            "analysis_mode": "question_change",
        })
        assert isinstance(result, ToolResult)
        assert result.error is None
        assert "vista" in result.model.lower()

    def test_execute_multitemporal_analysis_mode_accepted(self):
        """analysis_mode='multitemporal_analysis' must be accepted and routes to Prithvi."""
        result = self.tool.execute({
            "query": "Perform multitemporal EO analysis across HLS bands.",
            "image_t1": "/path/before.tif",
            "image_t2": "/path/after.tif",
            "analysis_mode": "multitemporal_analysis",
        })
        assert isinstance(result, ToolResult)
        assert result.error is None
        assert "Prithvi" in result.model or "prithvi" in result.model.lower()

    def test_execute_invalid_analysis_mode_rejected(self):
        """An unknown analysis_mode value must be rejected by Pydantic validation."""
        result = self.tool.execute({
            "query": "Detect changes.",
            "analysis_mode": "prithvi",  # old-style model hint — no longer valid
        })
        assert result.error is not None

    def test_execute_omitted_mode_defaults_to_vista(self):
        """When analysis_mode is omitted the worker should default to VisTA."""
        result = self.tool.execute({
            "query": "What has changed between the two images?",
        })
        assert isinstance(result, ToolResult)
        assert result.error is None
        assert "vista" in result.model.lower()

    def test_execute_missing_query_returns_error(self):
        result = self.tool.execute({})  # Missing required 'query'
        assert result.error is not None

    def test_input_schema_exposes_analysis_mode_to_gpt_oss(self):
        """GPT-OSS must see 'analysis_mode' in the tool's JSON schema."""
        schema = self.tool.input_schema
        assert "analysis_mode" in schema["properties"]
        mode_schema = schema["properties"]["analysis_mode"]
        enum_values = mode_schema.get("enum", [])
        assert "question_change" in enum_values
        assert "multitemporal_analysis" in enum_values

    def test_input_schema_does_not_expose_model_hint(self):
        """The old 'model_hint' field must NOT appear in the GPT-OSS-facing schema."""
        schema = self.tool.input_schema
        assert "model_hint" not in schema["properties"]

    def test_input_schema_exposes_temporal_image_fields(self):
        """Input schema must expose image_t3, image_t4, metadata_t3, metadata_t4."""
        schema = self.tool.input_schema
        assert "image_t3" in schema["properties"]
        assert "image_t4" in schema["properties"]
        assert "metadata_t3" in schema["properties"]
        assert "metadata_t4" in schema["properties"]

    def test_question_change_routes_to_vista_worker_client(self):
        """When analysis_mode='question_change', VisTAWorkerClient must be called."""
        from unittest.mock import patch

        with (
            patch.object(self.tool._vista_worker, "call", wraps=self.tool._vista_worker.call) as mock_vista,
            patch.object(self.tool._worker, "call", wraps=self.tool._worker.call) as mock_change,
            patch.object(self.tool._prithvi_worker, "call", wraps=self.tool._prithvi_worker.call) as mock_prithvi,
        ):
            result = self.tool.execute({
                "query": "What buildings were constructed?",
                "image_t1": "https://example.com/before.tif",
                "image_t2": "https://example.com/after.tif",
                "analysis_mode": "question_change",
            })

            assert result.error is None
            mock_vista.assert_called_once_with(
                image_t1="https://example.com/before.tif",
                image_t2="https://example.com/after.tif",
                query="What buildings were constructed?",
                metadata_t1=None,
                metadata_t2=None,
            )
            mock_change.assert_not_called()
            mock_prithvi.assert_not_called()

    def test_question_change_routes_with_metadata(self):
        """When metadata is provided, it is validated and forwarded to VisTAWorkerClient."""
        from unittest.mock import patch
        from app.schemas.requests import ImageMetadata

        with patch.object(self.tool._vista_worker, "call", wraps=self.tool._vista_worker.call) as mock_vista:
            result = self.tool.execute({
                "query": "What changed?",
                "image_t1": "https://example.com/before.tif",
                "image_t2": "https://example.com/after.tif",
                "metadata_t1": {"satellite": "Sentinel-2"},
                "metadata_t2": {"satellite": "Sentinel-2"},
                "analysis_mode": "question_change",
            })
            assert result.error is None
            mock_vista.assert_called_once()
            called_kwargs = mock_vista.call_args.kwargs
            assert isinstance(called_kwargs["metadata_t1"], ImageMetadata)
            assert called_kwargs["metadata_t1"].satellite == "Sentinel-2"

    def test_multitemporal_analysis_routes_to_prithvi_worker_client(self):
        """When analysis_mode='multitemporal_analysis', PrithviWorkerClient must be called."""
        from unittest.mock import patch
        from app.schemas.requests import ImageMetadata

        with (
            patch.object(self.tool._prithvi_worker, "call", wraps=self.tool._prithvi_worker.call) as mock_prithvi,
            patch.object(self.tool._vista_worker, "call", wraps=self.tool._vista_worker.call) as mock_vista,
            patch.object(self.tool._worker, "call", wraps=self.tool._worker.call) as mock_change,
        ):
            result = self.tool.execute({
                "query": "Detect multi-year deforestation",
                "image_t1": "https://example.com/t1.tif",
                "image_t2": "https://example.com/t2.tif",
                "image_t3": "https://example.com/t3.tif",
                "image_t4": "https://example.com/t4.tif",
                "metadata_t1": {"satellite": "Sentinel-2"},
                "metadata_t2": {"satellite": "Sentinel-2"},
                "metadata_t3": {"satellite": "Sentinel-2"},
                "metadata_t4": {"satellite": "Sentinel-2"},
                "analysis_mode": "multitemporal_analysis",
            })

            assert result.error is None
            mock_prithvi.assert_called_once()
            called_kwargs = mock_prithvi.call_args.kwargs
            assert called_kwargs["image_t1"] == "https://example.com/t1.tif"
            assert called_kwargs["image_t2"] == "https://example.com/t2.tif"
            assert called_kwargs["image_t3"] == "https://example.com/t3.tif"
            assert called_kwargs["image_t4"] == "https://example.com/t4.tif"
            assert called_kwargs["query"] == "Detect multi-year deforestation"
            assert isinstance(called_kwargs["metadata_t1"], ImageMetadata)
            assert isinstance(called_kwargs["metadata_t4"], ImageMetadata)
            mock_vista.assert_not_called()
            mock_change.assert_not_called()

    def test_multitemporal_analysis_does_not_use_vista_worker(self):
        """When analysis_mode='multitemporal_analysis', VisTAWorkerClient must NOT be called."""
        from unittest.mock import patch

        with (
            patch.object(self.tool._vista_worker, "call", wraps=self.tool._vista_worker.call) as mock_vista,
            patch.object(self.tool._worker, "call", wraps=self.tool._worker.call) as mock_change,
            patch.object(self.tool._prithvi_worker, "call", wraps=self.tool._prithvi_worker.call) as mock_prithvi,
        ):
            result = self.tool.execute({
                "query": "Perform multitemporal analysis",
                "image_t1": "https://example.com/before.tif",
                "image_t2": "https://example.com/after.tif",
                "analysis_mode": "multitemporal_analysis",
            })

            assert result.error is None
            mock_vista.assert_not_called()
            mock_change.assert_not_called()
            mock_prithvi.assert_called_once()

    def test_multitemporal_analysis_preserves_prithvi_artifacts(self):
        """Prithvi response artifacts (change_detected, change_percentage, change_analysis, model_output) must be preserved."""
        from unittest.mock import patch

        prithvi_result = {
            "answer": "Temporal analysis detected significant spectral differences across approximately 10.00% of the analyzed area.",
            "change_detected": True,
            "confidence": None,
            "change_percentage": 10.0,
            "temporal_frames": 4,
            "change_analysis": {
                "threshold": 0.5859819054603577,
                "changed_pixels": 25088,
                "total_pixels": 250880,
            },
            "model_output": {
                "original_shape": [1, 6, 4, 448, 560],
                "reconstruction_shape": [1, 6, 4, 448, 560],
                "mask_shape": [1, 6, 4, 448, 560],
                "temporal_coordinates": [[[2018.0, 26.0], [2018.0, 106.0], [2018.0, 201.0], [2018.0, 266.0]]],
                "location_coordinates": [[-104.70301818847656, 28.715795516967773]],
            },
            "mode": "real",
            "model": "ibm-nasa-geospatial/Prithvi-EO-2.0-300M",
        }

        with patch.object(self.tool._prithvi_worker, "call", return_value=prithvi_result):
            result = self.tool.execute({
                "query": "Analyze multitemporal changes",
                "image_t1": "https://example.com/t1.tif",
                "image_t2": "https://example.com/t2.tif",
                "image_t3": "https://example.com/t3.tif",
                "image_t4": "https://example.com/t4.tif",
                "analysis_mode": "multitemporal_analysis",
            })

            assert result.error is None
            assert result.model == "ibm-nasa-geospatial/Prithvi-EO-2.0-300M"
            assert result.mode == "real"
            assert "Temporal analysis detected" in result.answer

            # Verify change_detection_status artifact
            status_art = next(a for a in result.artifacts if a.get("type") == "change_detection_status")
            assert status_art["data"]["change_detected"] is True
            assert status_art["data"]["change_percentage"] == 10.0
            assert status_art["data"]["temporal_frames"] == 4
            assert status_art["data"]["changed_pixels"] == 25088
            assert status_art["data"]["total_pixels"] == 250880
            assert status_art["data"]["threshold"] == 0.5859819054603577

            # Verify change_analysis artifact
            analysis_art = next(a for a in result.artifacts if a.get("type") == "change_analysis")
            assert analysis_art["data"]["changed_pixels"] == 25088
            assert analysis_art["data"]["total_pixels"] == 250880

            # Verify model_output artifact
            model_art = next(a for a in result.artifacts if a.get("type") == "model_output")
            assert model_art["data"]["original_shape"] == [1, 6, 4, 448, 560]
            assert model_art["data"]["reconstruction_shape"] == [1, 6, 4, 448, 560]

    def test_routing_strictly_mode_based_no_keywords(self):
        """Routing depends ONLY on explicit analysis_mode, NEVER keyword or regex matching."""
        from unittest.mock import patch

        with (
            patch.object(self.tool._prithvi_worker, "call") as mock_prithvi,
            patch.object(self.tool._vista_worker, "call") as mock_vista,
            patch.object(self.tool._worker, "call", wraps=self.tool._worker.call) as mock_change,
        ):
            # Query explicitly contains "multitemporal", "prithvi", "4 frames"
            # BUT analysis_mode is omitted (None)
            result = self.tool.execute({
                "query": "Perform multitemporal analysis using Prithvi across 4 frames",
                "image_t1": "https://example.com/t1.tif",
                "image_t2": "https://example.com/t2.tif",
            })

            assert result.error is None
            # Must NOT route to Prithvi or VisTA via keyword matching
            mock_prithvi.assert_not_called()
            mock_vista.assert_not_called()
            # Must route through the general worker default
            mock_change.assert_called_once()

    def test_execute_includes_change_detected_artifact(self):
        """When change_detected is returned by worker, it must be added to artifacts."""
        result = self.tool.execute({
            "query": "Is there change?",
            "image_t1": "https://example.com/t1.tif",
            "image_t2": "https://example.com/t2.tif",
            "analysis_mode": "question_change",
        })
        assert result.error is None
        artifact_types = [a.get("type") for a in result.artifacts]
        assert "change_detection_status" in artifact_types
        status_art = next(a for a in result.artifacts if a.get("type") == "change_detection_status")
        assert status_art["data"]["change_detected"] is True


# ─────────────────────────────────────────────────────────────────────────────
# analyze_sar_optical tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeSarOpticalTool:

    def setup_method(self):
        self.tool = AnalyzeSarOpticalTool()

    def test_name(self):
        assert self.tool.name == "analyze_sar_optical"

    def test_execute_basic(self):
        result = self.tool.execute({
            "query": "Detect flood extent using SAR and optical fusion",
            "sar_image": "/path/sar.tif",
            "optical_image": "/path/optical.tif",
        })
        assert isinstance(result, ToolResult)
        assert result.mode == "mock"
        assert result.error is None

    def test_execute_selects_terrafm_for_classification(self):
        """
        When selected_models='terrafm' is set (by the LLM), the tool should
        call the TerraFM worker. The old keyword-based routing has been replaced
        by LLM-driven model selection via the selected_models schema field.
        """
        result = self.tool.execute({
            "query": "Classify land cover using SAR and optical imagery",
            "selected_models": "terrafm",  # LLM sets this, not keyword matching
        })
        assert "TerraFM" in result.model

    def test_execute_selects_closp_by_default(self):
        result = self.tool.execute({
            "query": "Analyze this SAR and optical image combination",
        })
        assert "closp" in result.model.lower()

    def test_mock_result_is_labelled(self):
        result = self.tool.execute({"query": "Flood mapping"})
        assert "[MOCK" in result.answer


# ─────────────────────────────────────────────────────────────────────────────
# MultiTemporalInput schema tests (Prithvi pipeline contract)
# These tests verify the Pydantic schema itself — no tool execution required.
# Band names used are Sentinel-2 native identifiers (B02, B03, B04, B08A,
# B11, B12).  They are NOT the Prithvi/HLS internal band indices; the HLS
# harmonisation step handles that mapping separately.
# ─────────────────────────────────────────────────────────────────────────────

def _make_frame(date: str, full: bool = True) -> dict:
    """Helper: build a TemporalFrame dict.  full=False → sparse bands."""
    bands: dict = {}
    if full:
        bands = {
            "B02":  f"s3://bucket/{date}/B02.tif",
            "B03":  f"s3://bucket/{date}/B03.tif",
            "B04":  f"s3://bucket/{date}/B04.tif",
            "B08A": f"s3://bucket/{date}/B08A.tif",
            "B11":  f"s3://bucket/{date}/B11.tif",
            "B12":  f"s3://bucket/{date}/B12.tif",
        }
    else:
        # Only visible bands present — NIR and SWIR tiles missing
        bands = {
            "B02": f"s3://bucket/{date}/B02.tif",
            "B03": f"s3://bucket/{date}/B03.tif",
            "B04": f"s3://bucket/{date}/B04.tif",
        }
    return {"acquisition_date": date, "bands": bands}


_FOUR_DATES = [
    "2022-03-15T09:00:00Z",
    "2022-06-21T09:00:00Z",
    "2022-09-22T09:00:00Z",
    "2022-12-10T09:00:00Z",
]


class TestMultiTemporalInput:
    """
    Schema-level tests for the MultiTemporalInput Pydantic model.

    Validates the 4-frame × 6-band multitemporal acquisition contract
    for the Prithvi pipeline without exercising any tool execution.
    """

    def test_valid_4_frames_accepted(self):
        """Happy path: exactly 4 frames with all 6 S2 bands → no validation error."""
        payload = MultiTemporalInput(
            frames=[TemporalFrame(**_make_frame(d)) for d in _FOUR_DATES],
            query="Detect vegetation change across four growing seasons.",
        )
        assert len(payload.frames) == 4
        # Band fields use Sentinel-2 native names, not Prithvi internal indices
        assert payload.frames[0].bands.B02 is not None
        assert payload.frames[0].bands.B08A is not None
        assert payload.frames[0].bands.B12 is not None

    def test_sparse_bands_accepted(self):
        """Partial acquisitions (missing NIR/SWIR tiles) must still be valid."""
        payload = MultiTemporalInput(
            frames=[TemporalFrame(**_make_frame(d, full=False)) for d in _FOUR_DATES],
            query="Analyse with available visible bands only.",
        )
        assert payload.frames[0].bands.B02 is not None
        # Missing bands default to None — not an error
        assert payload.frames[0].bands.B11 is None
        assert payload.frames[0].bands.B12 is None

    def test_fewer_than_4_frames_rejected(self):
        """Only 3 frames → Pydantic must raise ValidationError (min_length=4)."""
        with pytest.raises(ValidationError):
            MultiTemporalInput(
                frames=[TemporalFrame(**_make_frame(d)) for d in _FOUR_DATES[:3]],
                query="This should fail.",
            )

    def test_more_than_4_frames_rejected(self):
        """5 frames → Pydantic must raise ValidationError (max_length=4)."""
        five_dates = _FOUR_DATES + ["2023-03-01T09:00:00Z"]
        with pytest.raises(ValidationError):
            MultiTemporalInput(
                frames=[TemporalFrame(**_make_frame(d)) for d in five_dates],
                query="This should also fail.",
            )

    def test_wrong_analysis_mode_rejected(self):
        """analysis_mode must be fixed to 'multitemporal_analysis'; anything else fails."""
        with pytest.raises(ValidationError):
            MultiTemporalInput(
                frames=[TemporalFrame(**_make_frame(d)) for d in _FOUR_DATES],
                query="Reroute to VisTA — must not work.",
                analysis_mode="question_change",  # type: ignore[arg-type]
            )

    def test_analysis_mode_defaults_to_multitemporal_analysis(self):
        """When omitted, analysis_mode must default to 'multitemporal_analysis'."""
        payload = MultiTemporalInput(
            frames=[TemporalFrame(**_make_frame(d)) for d in _FOUR_DATES],
            query="Default mode check.",
        )
        assert payload.analysis_mode == "multitemporal_analysis"

