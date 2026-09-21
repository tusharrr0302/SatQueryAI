"""
tests/test_remote_worker.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for the RemoteWorkerClient hierarchy.

These tests verify:
  1. Mock mode returns correct result structure (no HTTP calls made)
  2. Health check returns expected dict in mock mode
  3. Model hint routing works correctly in mock mode
  4. Real mode raises RuntimeError when worker URL is not configured
  5. HTTP error handling (connection failure, timeout, non-success status)

Run with:
  cd ai-service
  pytest tests/test_remote_worker.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from app.services.remote_worker import (
    GeoChatWorkerClient,
    ChangeDetectionWorkerClient,
    VisTAWorkerClient,
    PrithviWorkerClient,
    SAROpticalWorkerClient,
)


# ─────────────────────────────────────────────────────────────────────────────
# GeoChatWorkerClient tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGeoChatWorkerClient:

    def setup_method(self):
        self.client = GeoChatWorkerClient()

    def test_mock_mode_no_http_call(self):
        """In mock mode, call() should return a result without any HTTP request."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(image=None, query="What do you see?")

        assert isinstance(result, dict)
        assert "answer" in result
        assert result["mode"] == "mock"
        assert result["model"] == GeoChatWorkerClient.MODEL_ID
        assert result["confidence"] is None

    def test_mock_result_contains_mock_label(self):
        """Mock result must be clearly labeled as [MOCK]."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(image="/path/to/image.tif", query="Describe this image")

        assert "[MOCK" in result["answer"]
        assert "GeoChat" in result["answer"]

    def test_mock_result_includes_query(self):
        """Query should appear in the mock answer for transparency."""
        query = "What land cover types are visible?"
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(image=None, query=query)

        assert query in result["answer"]

    def test_health_check_mock_mode(self):
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.health_check()

        assert result["status"] == "mock"

    def test_real_mode_raises_when_url_not_configured(self):
        """If real mode is set but URL is empty, call() should raise RuntimeError."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "real"
            mock_settings.geochat_worker_url = ""
            mock_settings.worker_timeout_seconds = 30

            with pytest.raises(RuntimeError, match="URL not configured"):
                self.client.call(image=None, query="Test query")

    def test_real_mode_http_post_called(self):
        """In real mode with URL configured, httpx.Client.post should be called."""
        mock_response_data = {
            "status": "success",
            "model": "GeoChat-7B",
            "mode": "real",
            "result": {"answer": "This is a real GeoChat result.", "confidence": 0.91},
        }

        with (
            patch("app.services.remote_worker.settings") as mock_settings,
            patch("app.services.remote_worker.httpx.Client") as mock_httpx_client,
        ):
            mock_settings.model_mode = "real"
            mock_settings.geochat_worker_url = "https://mock-ngrok.example.com"
            mock_settings.worker_timeout_seconds = 30

            # Mock the httpx context manager
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client_instance.post.return_value = mock_response
            mock_httpx_client.return_value = mock_client_instance

            result = self.client.call(image="https://example.com/image.tif", query="Describe")

        assert result["mode"] == "real"
        assert result["answer"] == "This is a real GeoChat result."
        mock_client_instance.post.assert_called_once()

    def test_real_mode_connection_error_raises_runtime_error(self):
        """Connection failure should raise RuntimeError with an informative message."""
        import httpx

        with (
            patch("app.services.remote_worker.settings") as mock_settings,
            patch("app.services.remote_worker.httpx.Client") as mock_httpx_client,
        ):
            mock_settings.model_mode = "real"
            mock_settings.geochat_worker_url = "https://dead-ngrok.example.com"
            mock_settings.worker_timeout_seconds = 30

            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client_instance.post.side_effect = httpx.ConnectError("Connection refused")
            mock_httpx_client.return_value = mock_client_instance

            with pytest.raises(RuntimeError, match="unreachable"):
                self.client.call(image=None, query="Test")


# ─────────────────────────────────────────────────────────────────────────────
# ChangeDetectionWorkerClient tests
# ─────────────────────────────────────────────────────────────────────────────

class TestChangeDetectionWorkerClient:

    def setup_method(self):
        self.client = ChangeDetectionWorkerClient()

    def test_mock_mode_default_returns_vista(self):
        """Without analysis_mode the mock worker must default to VisTA."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(
                image_t1=None, image_t2=None,
                query="What changed between these two images?"
            )

        assert result["mode"] == "mock"
        assert "vista" in result["model"].lower()
        assert result["confidence"] is None

    def test_mock_mode_question_change_selects_vista(self):
        """analysis_mode='question_change' must select VisTA in mock mode."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(
                image_t1=None, image_t2=None,
                query="What changed?",
                analysis_mode="question_change",
            )

        assert "vista" in result["model"].lower()

    def test_mock_mode_multitemporal_analysis_selects_prithvi(self):
        """analysis_mode='multitemporal_analysis' must select Prithvi in mock mode."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(
                image_t1=None, image_t2=None,
                query="Perform multitemporal EO analysis.",
                analysis_mode="multitemporal_analysis",
            )

        assert "Prithvi" in result["model"] or "prithvi" in result["model"].lower()

    def test_mock_result_has_required_keys(self):
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(
                image_t1="/t1.tif", image_t2="/t2.tif",
                query="Detect changes"
            )

        assert "answer" in result
        assert "confidence" in result
        assert "change_mask" in result
        assert "mode" in result
        assert "model" in result

    def test_mock_result_is_labeled_mock(self):
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(image_t1=None, image_t2=None, query="Test")

        assert "[MOCK" in result["answer"]

    def test_real_mode_raises_when_url_not_configured(self):
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "real"
            mock_settings.change_detection_worker_url = ""
            mock_settings.worker_timeout_seconds = 30

            with pytest.raises(RuntimeError, match="URL not configured"):
                self.client.call(image_t1=None, image_t2=None, query="Test")

    def test_real_mode_sends_analysis_mode_in_body(self):
        """In real mode, the HTTP body must contain 'analysis_mode' (not 'model_hint')."""
        mock_response_data = {
            "status": "success",
            "model": "like413/vista",
            "mode": "real",
            "result": {"answer": "No significant change detected.", "confidence": 0.85,
                       "change_mask": None},
        }

        with (
            patch("app.services.remote_worker.settings") as mock_settings,
            patch("app.services.remote_worker.httpx.Client") as mock_httpx_client,
        ):
            mock_settings.model_mode = "real"
            mock_settings.change_detection_worker_url = "https://mock-ngrok.example.com"
            mock_settings.worker_timeout_seconds = 30

            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client_instance.post.return_value = mock_response
            mock_httpx_client.return_value = mock_client_instance

            self.client.call(
                image_t1="https://example.com/t1.tif",
                image_t2="https://example.com/t2.tif",
                query="Compare the two images",
                analysis_mode="question_change",
            )

        # Verify analysis_mode was included in the HTTP body
        _, call_kwargs = mock_client_instance.post.call_args
        sent_body = call_kwargs.get("json", {})
        assert "analysis_mode" in sent_body
        assert "model_hint" not in sent_body
        assert sent_body["analysis_mode"] == "question_change"


# ─────────────────────────────────────────────────────────────────────────────
# SAROpticalWorkerClient tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSAROpticalWorkerClient:

    def setup_method(self):
        self.client = SAROpticalWorkerClient()

    def test_mock_mode_default_returns_clasp(self):
        """Default mock result should use CLASP for non-classification queries."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(
                sar_image=None, optical_image=None,
                query="Analyze SAR and optical for flood detection"
            )

        assert result["mode"] == "mock"
        assert "closp" in result["model"].lower() or "clasp" in result["model"].lower()

    def test_mock_mode_terrafm_hint(self):
        """model_hint='terrafm' should select TerraFM in mock mode."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(
                sar_image=None, optical_image=None,
                query="Analyze terrain",
                model_hint="terrafm",
            )

        assert "TerraFM" in result["model"] or "terrafm" in result["model"].lower()

    def test_mock_mode_terrafm_for_classification(self):
        """Queries mentioning 'classify' or 'land cover' should use TerraFM in mock."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(
                sar_image=None, optical_image=None,
                query="Classify land cover using SAR and optical imagery"
            )

        assert "TerraFM" in result["model"]

    def test_mock_result_labeled_mock(self):
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(sar_image=None, optical_image=None, query="Test")

        assert "[MOCK" in result["answer"]

    def test_real_mode_raises_when_url_not_configured(self):
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "real"
            mock_settings.sar_optical_worker_url = ""
            mock_settings.worker_timeout_seconds = 30

            with pytest.raises(RuntimeError, match="URL not configured"):
                self.client.call(sar_image=None, optical_image=None, query="Test")

    def test_health_check_mock_mode(self):
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.health_check()

        assert result["status"] == "mock"


# ─────────────────────────────────────────────────────────────────────────────
# VisTAWorkerClient tests
# ─────────────────────────────────────────────────────────────────────────────

class TestVisTAWorkerClient:

    def setup_method(self):
        self.client = VisTAWorkerClient()

    def test_properties(self):
        assert self.client.endpoint == "/tools/detect_change"
        assert self.client.worker_name == "VisTAWorker"
        assert self.client.VISTA_MODEL_ID == "like413/vista"

        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.vista_worker_url = "https://vista.ngrok.example.com"
            assert self.client.worker_url == "https://vista.ngrok.example.com"

    def test_mock_mode_no_http_call(self):
        """In mock mode, call() returns a local mock without making HTTP requests."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(
                image_t1="mock://before.tif",
                image_t2="mock://after.tif",
                query="Identify new buildings",
            )

        assert result["mode"] == "mock"
        assert result["model"] == "like413/vista"
        assert "[MOCK — VisTA]" in result["answer"]
        assert "Identify new buildings" in result["answer"]
        assert result["confidence"] is None
        assert result["change_mask"] is None
        assert result["change_detected"] is True

    def test_health_check_mock_mode(self):
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.health_check()

        assert result["status"] == "mock"
        assert result["worker"] == "VisTAWorker"

    def test_real_mode_raises_when_url_not_configured(self):
        """If real mode is set but vista_worker_url is empty, call() raises RuntimeError."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "real"
            mock_settings.vista_worker_url = ""
            mock_settings.worker_timeout_seconds = 30

            with pytest.raises(RuntimeError, match="VisTAWorker URL not configured"):
                self.client.call(image_t1=None, image_t2=None, query="Test query")

    def test_real_mode_exact_request_body(self):
        """
        Verify the POST request URL and body match the VisTA Kaggle worker contract:
        {
            "image_t1": ...,
            "image_t2": ...,
            "query": ...,
            "metadata_t1": ...,
            "metadata_t2": ...
        }
        Must NOT send image_t1_url or image_t2_url.
        """
        mock_response_data = {
            "tool": "detect_change",
            "status": "success",
            "model": "VisTA",
            "mode": "mock",
            "result": {
                "answer": "Mock VisTA change detection completed successfully.",
                "confidence": 0.95,
                "change_detected": True,
                "change_mask": {"type": "FeatureCollection"},
            },
        }

        with (
            patch("app.services.remote_worker.settings") as mock_settings,
            patch("app.services.remote_worker.httpx.Client") as mock_httpx_client,
        ):
            mock_settings.model_mode = "real"
            mock_settings.vista_worker_url = "https://vista.ngrok.example.com"
            mock_settings.worker_timeout_seconds = 30

            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response_data
            mock_resp.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client_instance.post.return_value = mock_resp
            mock_httpx_client.return_value = mock_client_instance

            metadata_t1 = {"satellite": "Sentinel-2", "date": "2022-01-01"}
            metadata_t2 = {"satellite": "Sentinel-2", "date": "2023-01-01"}

            result = self.client.call(
                image_t1="https://example.com/t1.tif",
                image_t2="https://example.com/t2.tif",
                query="Detect deforestation",
                metadata_t1=metadata_t1,
                metadata_t2=metadata_t2,
            )

            # Check POST URL
            mock_client_instance.post.assert_called_once()
            called_url = mock_client_instance.post.call_args[0][0]
            assert called_url == "https://vista.ngrok.example.com/tools/detect_change"

            # Check POST json body
            posted_body = mock_client_instance.post.call_args[1]["json"]
            assert posted_body == {
                "image_t1": "https://example.com/t1.tif",
                "image_t2": "https://example.com/t2.tif",
                "query": "Detect deforestation",
                "metadata_t1": metadata_t1,
                "metadata_t2": metadata_t2,
            }
            assert "image_t1_url" not in posted_body
            assert "image_t2_url" not in posted_body

            # Check parsed response
            assert result["answer"] == "Mock VisTA change detection completed successfully."
            assert result["confidence"] == 0.95
            assert result["change_detected"] is True
            assert result["change_mask"] == {"type": "FeatureCollection"}
            assert result["mode"] == "mock"
            assert result["model"] == "VisTA"

    def test_real_mode_raises_on_non_success_status(self):
        """A worker response with status != 'success' must raise RuntimeError."""
        mock_response_data = {
            "status": "error",
            "error": "Failed to load model weights on worker",
        }

        with (
            patch("app.services.remote_worker.settings") as mock_settings,
            patch("app.services.remote_worker.httpx.Client") as mock_httpx_client,
        ):
            mock_settings.model_mode = "real"
            mock_settings.vista_worker_url = "https://vista.ngrok.example.com"
            mock_settings.worker_timeout_seconds = 30

            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response_data
            mock_resp.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client_instance.post.return_value = mock_resp
            mock_httpx_client.return_value = mock_client_instance

            with pytest.raises(RuntimeError, match="VisTA worker returned non-success status"):
                self.client.call(
                    image_t1="https://example.com/t1.tif",
                    image_t2="https://example.com/t2.tif",
                    query="Find changes",
                )


# ─────────────────────────────────────────────────────────────────────────────
# PrithviWorkerClient tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPrithviWorkerClient:

    def setup_method(self):
        self.client = PrithviWorkerClient()

    def test_properties(self):
        assert self.client.endpoint == "/tools/analyze_multitemporal"
        assert self.client.worker_name == "PrithviWorker"
        assert self.client.MODEL_ID == "ibm-nasa-geospatial/Prithvi-EO-2.0-300M"

        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.prithvi_worker_url = "https://prithvi.ngrok.example.com"
            assert self.client.worker_url == "https://prithvi.ngrok.example.com"

    def test_mock_mode_no_http_call(self):
        """In mock mode, call() returns a local mock without making HTTP requests."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.call(
                image_t1="mock://t1.tif",
                image_t2="mock://t2.tif",
                image_t3="mock://t3.tif",
                image_t4="mock://t4.tif",
                query="Analyze multitemporal changes",
            )

        assert result["mode"] == "mock"
        assert result["model"] == "ibm-nasa-geospatial/Prithvi-EO-2.0-300M"
        assert "[MOCK — Prithvi-EO-2.0-300M]" in result["answer"]
        assert "Analyze multitemporal changes" in result["answer"]
        assert result["change_detected"] is True
        assert result["confidence"] is None
        assert result["change_percentage"] == 10.0
        assert result["temporal_frames"] == 4
        assert isinstance(result["change_analysis"], dict)
        assert result["change_analysis"]["changed_pixels"] == 25088
        assert result["change_analysis"]["total_pixels"] == 250880
        assert isinstance(result["model_output"], dict)
        assert result["model_output"]["original_shape"] == [1, 6, 4, 448, 560]

    def test_health_check_mock_mode(self):
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "mock"
            result = self.client.health_check()

        assert result["status"] == "mock"
        assert result["worker"] == "PrithviWorker"

    def test_real_mode_raises_when_url_not_configured(self):
        """If real mode is set but prithvi_worker_url is empty, call() raises RuntimeError."""
        with patch("app.services.remote_worker.settings") as mock_settings:
            mock_settings.model_mode = "real"
            mock_settings.prithvi_worker_url = ""
            mock_settings.worker_timeout_seconds = 30

            with pytest.raises(RuntimeError, match="PrithviWorker URL not configured"):
                self.client.call(
                    image_t1=None,
                    image_t2=None,
                    image_t3=None,
                    image_t4=None,
                    query="Test query",
                )

    def test_real_mode_exact_request_body_and_response_parsing(self):
        """
        Verify the POST request URL and body match the Prithvi Kaggle worker contract:
        {
            "image_t1": ...,
            "image_t2": ...,
            "image_t3": ...,
            "image_t4": ...,
            "query": ...,
            "metadata_t1": ...,
            "metadata_t2": ...,
            "metadata_t3": ...,
            "metadata_t4": ...
        }
        and verify all response fields are parsed and preserved.
        """
        mock_response_data = {
            "tool": "analyze_multitemporal",
            "status": "success",
            "model": "Prithvi-EO-2.0-300M",
            "mode": "real",
            "result": {
                "answer": (
                    "Temporal analysis detected significant spectral differences across "
                    "approximately 10.00% of the analyzed area between the first and latest observations."
                ),
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
                    "temporal_coordinates": [
                        [
                            [2018.0, 26.0],
                            [2018.0, 106.0],
                            [2018.0, 201.0],
                            [2018.0, 266.0],
                        ]
                    ],
                    "location_coordinates": [
                        [-104.70301818847656, 28.715795516967773],
                    ],
                },
            },
        }

        with (
            patch("app.services.remote_worker.settings") as mock_settings,
            patch("app.services.remote_worker.httpx.Client") as mock_httpx_client,
        ):
            mock_settings.model_mode = "real"
            mock_settings.prithvi_worker_url = "https://prithvi.ngrok.example.com"
            mock_settings.worker_timeout_seconds = 30

            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response_data
            mock_resp.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client_instance.post.return_value = mock_resp
            mock_httpx_client.return_value = mock_client_instance

            metadata_t1 = {"satellite": "Sentinel-2", "date": "2018-01-26"}
            metadata_t2 = {"satellite": "Sentinel-2", "date": "2018-04-16"}
            metadata_t3 = {"satellite": "Sentinel-2", "date": "2018-07-20"}
            metadata_t4 = {"satellite": "Sentinel-2", "date": "2018-09-23"}

            result = self.client.call(
                image_t1="https://example.com/t1.tif",
                image_t2="https://example.com/t2.tif",
                image_t3="https://example.com/t3.tif",
                image_t4="https://example.com/t4.tif",
                query="Detect vegetation loss over 4 frames",
                metadata_t1=metadata_t1,
                metadata_t2=metadata_t2,
                metadata_t3=metadata_t3,
                metadata_t4=metadata_t4,
            )

            # Check POST URL
            mock_client_instance.post.assert_called_once()
            called_url = mock_client_instance.post.call_args[0][0]
            assert called_url == "https://prithvi.ngrok.example.com/tools/analyze_multitemporal"

            # Check POST json body
            posted_body = mock_client_instance.post.call_args[1]["json"]
            assert posted_body == {
                "image_t1": "https://example.com/t1.tif",
                "image_t2": "https://example.com/t2.tif",
                "image_t3": "https://example.com/t3.tif",
                "image_t4": "https://example.com/t4.tif",
                "query": "Detect vegetation loss over 4 frames",
                "metadata_t1": metadata_t1,
                "metadata_t2": metadata_t2,
                "metadata_t3": metadata_t3,
                "metadata_t4": metadata_t4,
            }

            # Check parsed response fields preserved
            assert result["mode"] == "real"
            assert result["model"] == "Prithvi-EO-2.0-300M"
            assert "Temporal analysis detected" in result["answer"]
            assert result["change_detected"] is True
            assert result["confidence"] is None
            assert result["change_percentage"] == 10.0
            assert result["temporal_frames"] == 4
            assert result["change_analysis"] == {
                "threshold": 0.5859819054603577,
                "changed_pixels": 25088,
                "total_pixels": 250880,
            }
            assert result["model_output"]["original_shape"] == [1, 6, 4, 448, 560]
            assert result["model_output"]["reconstruction_shape"] == [1, 6, 4, 448, 560]
            assert result["model_output"]["mask_shape"] == [1, 6, 4, 448, 560]
            assert len(result["model_output"]["temporal_coordinates"][0]) == 4
            assert result["model_output"]["location_coordinates"] == [
                [-104.70301818847656, 28.715795516967773]
            ]

    def test_real_mode_raises_on_non_success_status(self):
        """A worker response with status != 'success' must raise RuntimeError."""
        mock_response_data = {
            "status": "error",
            "error": "GPU memory allocation failed on worker",
        }

        with (
            patch("app.services.remote_worker.settings") as mock_settings,
            patch("app.services.remote_worker.httpx.Client") as mock_httpx_client,
        ):
            mock_settings.model_mode = "real"
            mock_settings.prithvi_worker_url = "https://prithvi.ngrok.example.com"
            mock_settings.worker_timeout_seconds = 30

            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response_data
            mock_resp.raise_for_status = MagicMock()

            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client_instance.post.return_value = mock_resp
            mock_httpx_client.return_value = mock_client_instance

            with pytest.raises(RuntimeError, match="Prithvi worker returned non-success status"):
                self.client.call(
                    image_t1="https://example.com/t1.tif",
                    image_t2="https://example.com/t2.tif",
                    image_t3="https://example.com/t3.tif",
                    image_t4="https://example.com/t4.tif",
                    query="Find changes",
                )


