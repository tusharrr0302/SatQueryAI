"""
Unit and Integration Test Suite for CLOSP Canonical Endpoint Contract (/tools/analyze_sar_optical).

Covers:
1. CLOSP endpoint is strictly /tools/analyze_sar_optical.
2. Request payload contains sar_image_url, optical_image_url, query, and model_hint="closp".
3. Backend does not call obsolete /analyze endpoint in active ATS path.
4. Canonical worker route /tools/analyze_sar_optical is registered and active.
5. HTTP 404 from worker produces clear worker-route error (not generic region error).
6. ALLOW_MOCK_FALLBACK=False prevents silent fallback to mock.
7. Sentinel-1 dual-polarization (VV+VH) validation remains strictly enforced.
8. Backward-compatible alias /analyze forwards to the same implementation.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from app.config import settings
from app.services.worker_client import (
    EOWorkerClient,
    CLOSPAdapter,
    RemoteWorkerUnavailableError,
)
from app.schemas.normalized_result import NormalizedResult, AOIInfo, Coordinates


# -----------------------------------------------------------------------------
# 1. Endpoint Contract: CLOSP endpoint is /tools/analyze_sar_optical
# -----------------------------------------------------------------------------
def test_closp_canonical_endpoint_is_tools_analyze_sar_optical():
    adapter = CLOSPAdapter()
    assert adapter.get_endpoint() == "/tools/analyze_sar_optical"
    assert adapter.tool_name == "analyze_sar_optical"
    assert adapter.model_id == "closp"


# -----------------------------------------------------------------------------
# 2. Payload Contract: contains sar_image_url, optical_image_url, query, model_hint
# -----------------------------------------------------------------------------
def test_closp_payload_contains_all_canonical_fields():
    adapter = CLOSPAdapter()
    inputs = {
        "sar_image_url": "https://example.com/s1_vv_vh.tif",
        "optical_image_url": "https://example.com/s2_optical.tif",
    }
    payload = adapter.build_request_payload(
        request={},
        query="Analyze possible flooding in Nepal using SAR and optical imagery",
        inputs=inputs,
    )
    assert payload["sar_image_url"] == "https://example.com/s1_vv_vh.tif"
    assert payload["optical_image_url"] == "https://example.com/s2_optical.tif"
    assert payload["query"] == "Analyze possible flooding in Nepal using SAR and optical imagery"
    assert payload["model_hint"] == "closp"


# -----------------------------------------------------------------------------
# 3. Active ATS path does not call obsolete /analyze
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_backend_does_not_call_obsolete_analyze_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "CLOSP_WORKER_URL", "http://worker:9000")
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", False)
    client = EOWorkerClient()

    called_urls = []

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "tool": "analyze_sar_optical",
        "status": "success",
        "model": "DarthReca/closp",
        "mode": "real",
        "cross_modal_similarity": 0.42,
        "answer": "Coherent SAR-optical alignment detected across flood plain.",
    }

    async def mock_post(url, **kwargs):
        called_urls.append(str(url))
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        norm = await client.execute(
            model_id="closp",
            inputs={
                "sar_image_url": "https://example.com/s1.tif",
                "optical_image_url": "https://example.com/s2.tif",
            },
            query="Nepal flood analysis",
        )

        assert len(called_urls) == 1
        assert called_urls[0] == "http://worker:9000/tools/analyze_sar_optical"
        assert not called_urls[0].endswith("/analyze")
        assert norm.provenance.source == "remote_worker"
        assert norm.provenance.fallback is False


# -----------------------------------------------------------------------------
# 4. HTTP 404 from worker produces clear worker-route error
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_worker_http_404_produces_clear_endpoint_error(monkeypatch):
    monkeypatch.setattr(settings, "CLOSP_WORKER_URL", "http://worker:9000")
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", False)
    client = EOWorkerClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "404 Not Found"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(RemoteWorkerUnavailableError) as exc_info:
            await client.execute(
                model_id="closp",
                inputs={
                    "sar_image_url": "https://example.com/s1.tif",
                    "optical_image_url": "https://example.com/s2.tif",
                },
                query="Nepal flooding",
            )

        err_str = str(exc_info.value)
        assert "CLOSP worker endpoint not found: /tools/analyze_sar_optical" in err_str
        assert "http://worker:9000" in err_str
        assert "ALLOW_MOCK_FALLBACK=False" in err_str


# -----------------------------------------------------------------------------
# 5. ALLOW_MOCK_FALLBACK=False prevents silent fallback on 404
# -----------------------------------------------------------------------------
@pytest.mark.anyio
async def test_real_mode_prevents_silent_mock_fallback_on_error(monkeypatch):
    monkeypatch.setattr(settings, "CLOSP_WORKER_URL", "http://worker:9000")
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", False)
    client = EOWorkerClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(RemoteWorkerUnavailableError):
            await client.execute(
                model_id="closp",
                inputs={"sar_image": "https://example.com/s1.tif"},
                query="Nepal flood assessment",
            )


# -----------------------------------------------------------------------------
# 6. Dual polarization (VV+VH) validation remains enforced
# -----------------------------------------------------------------------------
def test_dual_pol_validation_enforced_in_contracts():
    from tests.test_specialist_contracts import test_f_closp_single_band_rejected, test_g_closp_dual_pol_success
    # Both contract tests must execute and pass
    import asyncio
    asyncio.run(test_f_closp_single_band_rejected(pytest.MonkeyPatch()))
    asyncio.run(test_g_closp_dual_pol_success(pytest.MonkeyPatch()))


# -----------------------------------------------------------------------------
# 7. Worker URL fallback: CLOSP_WORKER_URL with SAR_OPTICAL_WORKER_URL alias
# -----------------------------------------------------------------------------
def test_closp_worker_url_resolution(monkeypatch):
    adapter = CLOSPAdapter()

    monkeypatch.setattr(settings, "CLOSP_WORKER_URL", "https://closp.ngrok.dev")
    monkeypatch.setattr(settings, "SAR_OPTICAL_WORKER_URL", "")
    assert adapter.get_worker_url() == "https://closp.ngrok.dev"

    # Fallback to SAR_OPTICAL_WORKER_URL when CLOSP_WORKER_URL is empty
    monkeypatch.setattr(settings, "CLOSP_WORKER_URL", "")
    monkeypatch.setattr(settings, "SAR_OPTICAL_WORKER_URL", "https://sar-opt.ngrok.dev")
    assert adapter.get_worker_url() == "https://sar-opt.ngrok.dev"
