"""
tests/test_specialist_workers.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive automated test suite for remote specialist EO AI workers:
  - Prithvi-EO-2.0
  - EarthDial-4B-MS
  - GeoChat-7B (legacy)
  - VisTA
  - CLOSP
  - TerraFM

Tests:
  1. Registry configuration & metadata
  2. Adapter request payload building & response parsing
  3. EOWorkerClient real HTTP dispatch & timeout / error handling
  4. Provenance honesty (remote_worker vs mock fallback)
  5. /api/v1/health/models endpoint
  6. /api/v1/debug/model/{model_id} endpoint
"""
from __future__ import annotations

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.models.registry import MODEL_REGISTRY
from app.services.worker_client import (
    EOWorkerClient,
    PrithviAdapter,
    EarthDialAdapter,
    GeoChatAdapter,
    VisTAAdapter,
    CLOSPAdapter,
    TerraFMAdapter,
    RemoteWorkerUnavailableError,
    check_all_model_workers,
)
from app.schemas.normalized_result import NormalizedResult, AOIInfo, Coordinates

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test_token_analyst"}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Model Registry Checks
# ─────────────────────────────────────────────────────────────────────────────

def test_registry_contains_all_specialist_models():
    """Verify authoritative model registry defines all required specialist models."""
    required_models = [
        "prithvi-eo-2.0",
        "earthdial-4b-ms",
        "geochat-7b",
        "vista",
        "closp",
        "terrafm",
    ]
    for m in required_models:
        assert m in MODEL_REGISTRY, f"Model {m} missing from MODEL_REGISTRY"
        meta = MODEL_REGISTRY[m]
        assert "worker_env" in meta, f"Model {m} missing worker_env"
        assert "capabilities" in meta, f"Model {m} missing capabilities"
        assert "modalities" in meta, f"Model {m} missing modalities"

    # Verify EarthDial is primary and GeoChat is marked legacy in version
    assert MODEL_REGISTRY["earthdial-4b-ms"]["worker_env"] == "EARTHDIAL_WORKER_URL"
    assert "Legacy" in MODEL_REGISTRY["geochat-7b"]["version"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Adapter Request Payload Building & Response Parsing
# ─────────────────────────────────────────────────────────────────────────────

def test_prithvi_adapter_payload_and_parsing():
    adapter = PrithviAdapter()
    aoi = AOIInfo(
        id="aoi_delhi",
        name="Delhi NCR",
        type="Polygon",
        center=Coordinates(latitude=28.6139, longitude=77.2090),
        area_km2=1484.0,
        bbox=[76.84, 28.40, 77.34, 28.88],
        polygon=[],
    )

    payload = adapter.build_request_payload(
        request={},
        query="Detect urban growth between 2020 and 2024",
        inputs={"image_t1": "https://example.com/t1.tif", "image_t2": "https://example.com/t2.tif"},
        aoi=aoi,
    )
    assert payload["image_t1"] == "https://example.com/t1.tif"
    assert payload["image_t2"] == "https://example.com/t2.tif"
    assert payload["analysis_mode"] == "multitemporal_analysis"
    assert payload["metadata_t1"]["bands"] == ["B02", "B03", "B04", "B08A", "B11", "B12"]

    # Test parsing response with change mask and pixel stats
    mock_worker_json = {
        "result": {
            "answer": "Surface change detected across 14.8% of Delhi AOI.",
            "confidence": 0.94,
            "change_percentage": 14.8,
            "change_analysis": {
                "changed_pixels": 45000,
                "total_pixels": 304054,
            },
            "change_mask": "https://example.com/masks/delhi_change.tif",
            "model_output": {
                "temporal_coordinates": [[[2020, 150], [2024, 150]]],
            },
        }
    }
    norm = adapter.parse_response(
        raw_json=mock_worker_json,
        request={},
        query="Detect urban growth",
        duration=1.45,
        worker_url="http://mock-prithvi-worker:8000",
        aoi=aoi,
    )
    assert isinstance(norm, NormalizedResult)
    assert norm.provenance.source == "remote_worker"
    assert norm.provenance.fallback is False
    assert norm.provenance.model_id == "prithvi-eo-2.0"
    assert norm.confidence == 0.94
    assert any("Surface Change" in m.label for m in norm.metrics)
    assert any("Changed Pixels" in m.label for m in norm.metrics)
    assert len(norm.raster_outputs) == 1
    assert len(norm.layers) == 1
    assert norm.layers[0].type == "change_detection"


def test_earthdial_adapter_payload_and_parsing():
    adapter = EarthDialAdapter()
    payload = adapter.build_request_payload(
        request={},
        query="What type of agricultural patterns are visible?",
        inputs={"image": "https://example.com/punjab_sentinel2.png"},
    )
    assert payload["image_url"] == "https://example.com/punjab_sentinel2.png"
    assert payload["question"] == "What type of agricultural patterns are visible?"

    mock_worker_json = {
        "result": {
            "answer": "Center-pivot irrigation fields and mature wheat crops are observed.",
            "confidence": 0.96,
        }
    }
    norm = adapter.parse_response(
        raw_json=mock_worker_json,
        request={},
        query="What type of agricultural patterns are visible?",
        duration=0.85,
        worker_url="http://mock-earthdial-worker:8000",
    )
    assert isinstance(norm, NormalizedResult)
    assert norm.provenance.source == "remote_worker"
    assert norm.provenance.model_id == "earthdial-4b-ms"
    assert "Center-pivot irrigation" in norm.scientific_explanation
    assert norm.observations == ["Center-pivot irrigation fields and mature wheat crops are observed."]


def test_geochat_adapter_payload_and_parsing():
    adapter = GeoChatAdapter()
    payload = adapter.build_request_payload(
        request={},
        query="Identify runway structures",
        inputs={"image_url": "https://example.com/airport.png"},
    )
    assert payload["image_url"] == "https://example.com/airport.png"
    assert payload["query"] == "Identify runway structures"

    mock_worker_json = {
        "result": {
            "answer": "Identified two intersecting asphalt runways and commercial taxiways.",
            "confidence": 0.89,
        }
    }
    norm = adapter.parse_response(
        raw_json=mock_worker_json,
        request={},
        query="Identify runway structures",
        duration=0.72,
        worker_url="http://mock-geochat-worker:8000",
    )
    assert norm.provenance.source == "remote_worker"
    assert norm.provenance.model_id == "geochat-7b"


def test_vista_adapter_payload_and_parsing():
    adapter = VisTAAdapter()
    payload = adapter.build_request_payload(
        request={},
        query="Where did construction occur?",
        inputs={"before_url": "https://example.com/t1.png", "after_url": "https://example.com/t2.png"},
    )
    assert payload["image_t1"] == "https://example.com/t1.png"
    assert payload["image_t2"] == "https://example.com/t2.png"
    assert payload["analysis_mode"] == "question_change"

    mock_worker_json = {
        "result": {
            "answer": "Extensive ground clearing and structural concrete foundations detected in the northeast sector.",
            "confidence": 0.91,
        }
    }
    norm = adapter.parse_response(
        raw_json=mock_worker_json,
        request={},
        query="Where did construction occur?",
        duration=1.12,
        worker_url="http://mock-vista-worker:8000",
    )
    assert norm.provenance.source == "remote_worker"
    assert norm.provenance.model_id == "vista"


def test_closp_adapter_payload_and_parsing():
    adapter = CLOSPAdapter()
    payload = adapter.build_request_payload(
        request={},
        query="Assess flooded areas through cloud cover",
        inputs={"sar_image": "https://example.com/s1.tif", "optical_image": "https://example.com/s2.tif"},
    )
    assert payload["sar_image_url"] == "https://example.com/s1.tif"
    assert payload["optical_image_url"] == "https://example.com/s2.tif"

    mock_worker_json = {
        "result": {
            "answer": "SAR C-band radar specular reflection reveals 8.4 km² of flooded lowlands underneath cloud cover.",
            "similarity_score": 0.887,
            "confidence": 0.93,
        }
    }
    norm = adapter.parse_response(
        raw_json=mock_worker_json,
        request={},
        query="Assess flooded areas through cloud cover",
        duration=1.35,
        worker_url="http://mock-closp-worker:8000",
    )
    assert norm.provenance.source == "remote_worker"
    assert norm.provenance.model_id == "closp"
    assert any("Alignment Score" in m.label and "0.887" in m.value for m in norm.metrics)


def test_terrafm_adapter_payload_and_parsing():
    adapter = TerraFMAdapter()
    payload = adapter.build_request_payload(
        request={},
        query="Classify land cover using combined radar and optical bands",
        inputs={"sar_image": "https://example.com/s1.tif", "optical_image": "https://example.com/s2.tif"},
    )
    assert payload["sar_image_url"] == "https://example.com/s1.tif"
    assert payload["optical_image_url"] == "https://example.com/s2.tif"

    mock_worker_json = {
        "result": {
            "answer": "Multi-sensor fusion classified the region into 48% forest, 32% agricultural, and 20% water.",
            "classifications": {
                "forest": 0.48,
                "agriculture": 0.32,
                "water": 0.20,
            },
            "confidence": 0.95,
        }
    }
    norm = adapter.parse_response(
        raw_json=mock_worker_json,
        request={},
        query="Classify land cover",
        duration=1.65,
        worker_url="http://mock-terrafm-worker:8000",
    )
    assert norm.provenance.source == "remote_worker"
    assert norm.provenance.model_id == "terrafm"
    assert len(norm.classifications) == 3
    assert len(norm.visualizations) == 1
    assert norm.visualizations[0]["type"] == "donut"


import asyncio


# ─────────────────────────────────────────────────────────────────────────────
# 3. EOWorkerClient Execution Flow & Error Handling
# ─────────────────────────────────────────────────────────────────────────────

def test_worker_client_successful_execution(monkeypatch):
    """Verify EOWorkerClient dispatches to configured worker URL and logs ATS."""
    async def _test():
        monkeypatch.setattr(settings, "EARTHDIAL_WORKER_URL", "http://mock-earthdial:8000")
        client_instance = EOWorkerClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "answer": "Multispectral analysis indicates healthy vegetation canopy with high NIR reflectance.",
                "confidence": 0.95,
            }
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            norm = await client_instance.execute(
                model_id="earthdial-4b-ms",
                request={"aoi": {"name": "Test Farm"}},
                inputs={"image_url": "https://example.com/farm.tif"},
                query="Analyze crop health",
            )

            assert norm.provenance.source == "remote_worker"
            assert norm.provenance.worker_url == "http://mock-earthdial:8000"
            assert norm.provenance.fallback is False
            assert "Multispectral analysis" in norm.scientific_explanation
            mock_post.assert_called_once()
            called_url = mock_post.call_args[0][0]
            assert called_url == "http://mock-earthdial:8000/tools/analyze_image"

    asyncio.run(_test())


def test_worker_client_timeout_raises_when_mock_forbidden(monkeypatch):
    """When ALLOW_MOCK_FALLBACK is False, timeout must raise RemoteWorkerUnavailableError."""
    async def _test():
        monkeypatch.setattr(settings, "EARTHDIAL_WORKER_URL", "http://mock-earthdial:8000")
        monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", False)
        client_instance = EOWorkerClient()

        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Connection timed out")):
            with pytest.raises(RemoteWorkerUnavailableError) as exc_info:
                await client_instance.execute(
                    model_id="earthdial-4b-ms",
                    request={},
                    query="Analyze scene",
                )
            assert "worker_timeout" in str(exc_info.value)

    asyncio.run(_test())


def test_worker_client_timeout_falls_back_honestly_when_allowed(monkeypatch):
    """When ALLOW_MOCK_FALLBACK is True, timeout must return mock with honest provenance."""
    async def _test():
        monkeypatch.setattr(settings, "EARTHDIAL_WORKER_URL", "http://mock-earthdial:8000")
        monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", True)
        client_instance = EOWorkerClient()

        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Connection timed out")):
            norm = await client_instance.execute(
                model_id="earthdial-4b-ms",
                request={},
                query="How much vegetation has been lost in Uttarakhand between 2020 and 2024?",
            )
            assert norm.provenance.source == "mock"
            assert norm.provenance.fallback is True
            assert norm.provenance.fallback_reason == "worker_timeout"
            assert "Worker unavailable" in norm.provenance.notes

    asyncio.run(_test())


def test_worker_client_unconfigured_worker(monkeypatch):
    """If worker URL is None, unconfigured status is handled appropriately."""
    async def _test():
        monkeypatch.setattr(settings, "EARTHDIAL_WORKER_URL", None)
        monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", False)
        client_instance = EOWorkerClient()

        with pytest.raises(RemoteWorkerUnavailableError) as exc_info:
            await client_instance.execute(
                model_id="earthdial-4b-ms",
                request={},
                query="Test query",
            )
        assert "not configured" in str(exc_info.value)

    asyncio.run(_test())


# ─────────────────────────────────────────────────────────────────────────────
# 4. Health & Diagnostic Endpoints
# ─────────────────────────────────────────────────────────────────────────────

def test_health_models_endpoint(monkeypatch):
    """Test GET /api/v1/health/models reports status for all 6 specialist models."""
    monkeypatch.setattr(settings, "PRITHVI_WORKER_URL", "http://mock-prithvi:8000")
    monkeypatch.setattr(settings, "EARTHDIAL_WORKER_URL", None)

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        response = client.get("/api/v1/health/models")
        assert response.status_code == 200
        data = response.json()

        assert "prithvi" in data
        assert data["prithvi"]["configured"] is True
        assert data["prithvi"]["reachable"] is True
        assert data["prithvi"]["status"] == "ready"

        assert "earthdial" in data
        assert data["earthdial"]["configured"] is False
        assert data["earthdial"]["status"] == "unconfigured"


def test_debug_model_endpoint_success(monkeypatch):
    """Test POST /api/v1/debug/model/{model_id} returns diagnostic report."""
    monkeypatch.setattr(settings, "PRITHVI_WORKER_URL", "http://mock-prithvi:8000")

    mock_worker_json = {
        "result": {
            "answer": "Prithvi-EO-2.0 diagnostic run completed.",
            "confidence": 0.98,
            "change_percentage": 5.2,
        }
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_worker_json

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        response = client.post(
            "/api/v1/debug/model/prithvi-eo-2.0",
            json={"query": "Diagnostic test of Prithvi-EO-2.0"},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["model"] == "prithvi-eo-2.0"
        assert data["status"] == "success"
        assert data["source"] == "remote_worker"
        assert data["worker"] == "http://mock-prithvi:8000"
        assert "execution_time" in data
        assert "provenance" in data
        assert data["provenance"]["source"] == "remote_worker"
