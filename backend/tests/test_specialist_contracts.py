"""
Unit Test Suite for Specialist Model Contracts (A through M)
Tests:
A. EarthDial worker success
B. EarthDial startup failure
C. Prithvi date extraction
D. Prithvi temporal filenames
E. Prithvi four-frame request
F. CLOSP VV/VH validation
G. CLOSP successful dual-pol execution
H. real worker timeout
I. mock fallback
J. honest provenance
K. NormalizedResult conversion
L. visualization creation from real outputs
M. no visualization when no spatial artifact exists
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
import re

from app.config import settings
from app.services.worker_client import (
    EOWorkerClient,
    EarthDialAdapter,
    PrithviAdapter,
    CLOSPAdapter,
    RemoteWorkerUnavailableError,
    WorkerExecutionError,
)
from app.schemas.normalized_result import NormalizedResult, Provenance, MetricItem
from app.services.visualization_registry import plan_visualizations


# -----------------------------------------------------------------------------
# A. EarthDial worker success
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_a_earthdial_worker_success(monkeypatch):
    monkeypatch.setattr(settings, "EARTHDIAL_WORKER_URL", "http://worker:9000")
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", False)
    client = EOWorkerClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "success",
        "model": "akshaydudhane/EarthDial_4B_MS",
        "mode": "real",
        "result": {
            "answer": "This multispectral scene depicts dense agricultural cropland bordered by a river.",
            "confidence": 0.94,
            "inference_seconds": 1.42,
        },
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        norm = await client.execute(
            model_id="earthdial-4b-ms",
            inputs={"image_url": "https://example.com/scene.tif"},
            query="What is visible in this satellite image?",
        )

        assert norm.provenance.source == "remote_worker"
        assert norm.provenance.fallback is False
        assert "cropland" in norm.key_finding.lower()
        assert norm.provenance.model_id == "earthdial-4b-ms"


# -----------------------------------------------------------------------------
# B. EarthDial startup failure
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_b_earthdial_startup_failure(monkeypatch):
    monkeypatch.setattr(settings, "EARTHDIAL_WORKER_URL", "http://worker:9000")
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", False)
    client = EOWorkerClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "EarthDial subprocess failed: ModuleNotFoundError: No module named 'earthdial'"
    mock_resp.json.return_value = {
        "detail": {
            "error": "MODEL_LOAD_FAILED",
            "model": "earthdial",
            "message": "ModuleNotFoundError: No module named 'earthdial'",
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(RemoteWorkerUnavailableError) as exc_info:
            await client.execute(
                model_id="earthdial-4b-ms",
                inputs={"image_url": "https://example.com/scene.tif"},
                query="Describe the scene",
            )
        assert "earthdial" in str(exc_info.value).lower()


# -----------------------------------------------------------------------------
# C. Prithvi date extraction
# -----------------------------------------------------------------------------
def test_c_prithvi_date_extraction():
    # Verify HLS standard Julian date regex
    fname1 = "Mexico_HLS.S30.T13REM.2018026T173609.v2.0_cropped.tif"
    m1 = re.search(r"(\d{4})(\d{3})T\d{6}", fname1)
    assert m1 is not None
    year1, julian1 = int(m1.group(1)), int(m1.group(2))
    assert year1 == 2018
    assert julian1 == 26

    # Verify standard calendar date
    fname2 = "satquery_prithvi_t1_20240115_a1b2c3d4.tif"
    m2 = re.search(r"(?:_|\b|\.)(\d{4})[-_]?(\d{2})[-_]?(\d{2})(?:_|\b|\.)", fname2)
    assert m2 is not None
    assert int(m2.group(1)) == 2024
    assert int(m2.group(2)) == 1
    assert int(m2.group(3)) == 15


# -----------------------------------------------------------------------------
# D. Prithvi temporal filenames
# -----------------------------------------------------------------------------
def test_d_prithvi_temporal_filenames():
    adapter = PrithviAdapter()
    inputs = {
        "image_t1": "https://example.com/HLS.S30.2018026T173609.tif",
        "image_t2": "https://example.com/HLS.S30.2018106T172859.tif",
        "image_t3": "https://example.com/HLS.S30.2018201T172901.tif",
        "image_t4": "https://example.com/HLS.S30.2018266T173029.tif",
    }
    payload = adapter.build_request_payload({}, "Compare periods", inputs=inputs)
    assert "2018026" in payload["image_t1"]
    assert "2018106" in payload["image_t2"]
    assert "2018201" in payload["image_t3"]
    assert "2018266" in payload["image_t4"]


# -----------------------------------------------------------------------------
# E. Prithvi four-frame request
# -----------------------------------------------------------------------------
def test_e_prithvi_four_frame_request():
    adapter = PrithviAdapter()
    inputs = {
        "image_t1": "https://example.com/t1.tif",
        "image_t2": "https://example.com/t2.tif",
        "image_t3": "https://example.com/t3.tif",
        "image_t4": "https://example.com/t4.tif",
    }
    payload = adapter.build_request_payload({}, "Change query", inputs=inputs)
    for k in ("image_t1", "image_t2", "image_t3", "image_t4"):
        assert k in payload
        assert payload[k] is not None


# -----------------------------------------------------------------------------
# F. CLOSP VV/VH validation
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_f_closp_single_band_rejected(monkeypatch):
    monkeypatch.setattr(settings, "CLOSP_WORKER_URL", "http://worker:9000")
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", False)
    client = EOWorkerClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "ValueError: Expected Sentinel-1 VV/VH (2 bands) for this CLOSP checkpoint, got 1 bands."
    mock_resp.json.return_value = {
        "detail": {
            "error": "INFERENCE_FAILED",
            "model": "closp",
            "message": "ValueError: Expected Sentinel-1 VV/VH (2 bands) for this CLOSP checkpoint, got 1 bands.",
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(RemoteWorkerUnavailableError) as exc_info:
            await client.execute(
                model_id="closp",
                inputs={"sar_image": "https://example.com/single_band.tif"},
                query="Analyze SAR",
            )
        assert "2 bands" in str(exc_info.value)


# -----------------------------------------------------------------------------
# G. CLOSP successful dual-pol execution
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_g_closp_dual_pol_success(monkeypatch):
    monkeypatch.setattr(settings, "CLOSP_WORKER_URL", "http://worker:9000")
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", False)
    client = EOWorkerClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "tool": "analyze_sar_optical",
        "status": "success",
        "model": "CLOSP",
        "sar": {"embedding_dimension": 384, "embedding": [0.1] * 384},
        "optical": {"embedding_dimension": 384, "embedding": [0.2] * 384},
        "cross_modal_similarity": 0.815,
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        norm = await client.execute(
            model_id="closp",
            inputs={
                "sar_image_url": "https://example.com/s1_vvvh.tif",
                "optical_image_url": "https://example.com/s2_12band.tif",
            },
            query="Analyze flood extent using SAR and optical imagery",
        )

        assert norm.provenance.source == "remote_worker"
        assert norm.provenance.fallback is False
        assert any("0.815" in m.value for m in norm.metrics)


# -----------------------------------------------------------------------------
# H. Real worker timeout
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_h_real_worker_timeout(monkeypatch):
    monkeypatch.setattr(settings, "PRITHVI_WORKER_URL", "http://worker:9000")
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", False)
    client = EOWorkerClient()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Remote worker timed out")
        with pytest.raises(RemoteWorkerUnavailableError) as exc:
            await client.execute(
                model_id="prithvi-eo-2.0",
                inputs={"image_t1": "https://example.com/t1.tif"},
                query="Temporal analysis",
            )
        assert "timeout" in str(exc.value).lower()


# -----------------------------------------------------------------------------
# I. Mock fallback governance
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_i_mock_fallback_when_explicitly_allowed(monkeypatch):
    monkeypatch.setattr(settings, "PRITHVI_WORKER_URL", "http://unreachable:9000")
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", True)
    client = EOWorkerClient()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        norm = await client.execute(
            model_id="prithvi-eo-2.0",
            inputs={"image_t1": "https://example.com/t1.tif"},
            query="Temporal analysis",
        )
        assert norm.provenance.source == "mock"
        assert norm.provenance.fallback is True
        assert norm.provenance.fallback_reason is not None


# -----------------------------------------------------------------------------
# J. Honest provenance
# -----------------------------------------------------------------------------
def test_j_honest_provenance():
    real_prov = Provenance(
        source="remote_worker",
        worker_url="https://remote.worker/api",
        fallback=False,
        model_id="prithvi-eo-2.0",
        model_name="Prithvi-EO-2.0",
        dataset_ids=["Sentinel-2"],
    )
    assert real_prov.source == "remote_worker"
    assert real_prov.fallback is False

    fallback_prov = Provenance(
        source="mock_fallback",
        worker_url="https://remote.worker/api",
        fallback=True,
        fallback_reason="Remote worker unreachable",
        model_id="prithvi-eo-2.0",
        model_name="Prithvi-EO-2.0",
        dataset_ids=["Sentinel-2"],
    )
    assert fallback_prov.source == "mock_fallback"
    assert fallback_prov.fallback is True


# -----------------------------------------------------------------------------
# K. NormalizedResult conversion
# -----------------------------------------------------------------------------
def test_k_normalized_result_contract():
    adapter = PrithviAdapter()
    raw = {
        "status": "success",
        "result": {
            "answer": "Detected significant change across 12.5% of analyzed area.",
            "change_percentage": 12.5,
            "change_detected": True,
            "confidence": 0.92,
        },
    }
    norm = adapter.parse_response(
        raw_json=raw,
        request={},
        query="Detect vegetation change",
        duration=2.1,
        worker_url="http://worker:9000",
    )
    assert isinstance(norm, NormalizedResult)
    assert norm.provenance.source == "remote_worker"
    assert any("12.5" in m.value for m in norm.metrics)


# -----------------------------------------------------------------------------
# L. Visualization creation from real outputs
# -----------------------------------------------------------------------------
def test_l_visualization_creation_from_real_output():
    adapter = PrithviAdapter()
    raw = {
        "status": "success",
        "result": {
            "answer": "Temporal analysis detected significant spectral differences across 8.4% of the area.",
            "change_percentage": 8.4,
            "change_detected": True,
            "confidence": 0.88,
        },
    }
    norm = adapter.parse_response(
        raw_json=raw,
        request={},
        query="Show how this area changed between the two periods",
        duration=1.8,
        worker_url="http://worker:9000",
    )
    plan = plan_visualizations(norm)
    assert plan is not None
    assert plan.primary_visualization is not None


# -----------------------------------------------------------------------------
# M. No visualization when no spatial artifact exists
# -----------------------------------------------------------------------------
def test_m_no_fake_spatial_visualization():
    adapter = EarthDialAdapter()
    raw = {
        "status": "success",
        "result": {
            "answer": "The image shows a high-altitude desert with no built structures.",
            "confidence": 0.95,
        },
    }
    norm = adapter.parse_response(
        raw_json=raw,
        request={},
        query="What is visible in this satellite image?",
        duration=0.9,
        worker_url="http://worker:9000",
    )
    assert norm.visualization_required is False
    assert len(norm.raster_outputs) == 0
    assert len(norm.layers) == 0
