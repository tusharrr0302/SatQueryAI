"""Tests for Live Execution Integrity and Mock Leak Prevention.

Verifies:
- Cases A-E: Worker responses (200, 404, 500, timeout, malformed)
- Case F: Scenario matcher blocked when ALLOW_MOCK_FALLBACK=False
- Case G: Visualization registry does not fabricate specialist layers/flood
- Case H: Narrative generator reports honest unavailable state and decoupled advisory
- Case I: Strict provenance consistency contract
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from app.config import settings
from app.schemas.normalized_result import (
    NormalizedResult,
    Provenance,
    AOIInfo,
    Coordinates,
    MetricItem,
    DataLayerSpec,
    VisualizationSpec,
)
from app.services.worker_client import (
    EOWorkerClient,
    RemoteWorkerUnavailableError,
    RemoteWorkerExecutionError,
    PrithviAdapter,
    EarthDialAdapter,
    CLOSPAdapter,
)
from app.services.visualization_registry import build_data_layers
from app.services.evidence_service import evidence_service
from app.graph.nodes import _format_presentation_plan_markdown, execute_unknown_analysis


# ---------------------------------------------------------------------------
# Case A: Real remote worker returns 200
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_case_a_worker_200_success():
    mock_response_data = {
        "status": "success",
        "model_id": "prithvi-eo-2.0",
        "change_detected": True,
        "change_percentage": 8.4,
        "change_analysis": {
            "changed_pixels": 12050,
            "total_pixels": 143400,
        },
        "confidence": 0.88,
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data

    client = EOWorkerClient()
    aoi = AOIInfo(
        name="Kashmir",
        center=Coordinates(latitude=34.0837, longitude=74.7973),
        area_km2=222236.0,
        bbox=[73.5, 32.5, 76.5, 35.5],
    )

    with patch.object(settings, "PRITHVI_WORKER_URL", "https://mock-worker.satquery.internal"):
        with patch.object(settings, "ALLOW_MOCK_FALLBACK", False):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                res = await client.execute(model_id="prithvi-eo-2.0", query="vegetation change in Kashmir", aoi=aoi)

                assert res.provenance.source == "remote_worker"
                assert res.provenance.fallback is False
                assert res.provenance.execution_status == "success"
                assert res.provenance.worker_url == "https://mock-worker.satquery.internal"
                assert res.confidence == 0.88
                assert len(res.metrics) == 3
                for m in res.metrics:
                    assert m.source_type == "remote_worker"
                    assert m.source != "mock"
                    assert m.model_id == "prithvi-eo-2.0"


# ---------------------------------------------------------------------------
# Case B: Real remote worker returns 404
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_case_b_worker_404_reports_unavailable_no_mock():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "Not Found"

    client = EOWorkerClient()
    aoi = AOIInfo(
        name="Kashmir",
        center=Coordinates(latitude=34.0837, longitude=74.7973),
        area_km2=222236.0,
        bbox=[73.5, 32.5, 76.5, 35.5],
    )

    with patch.object(settings, "PRITHVI_WORKER_URL", "https://mock-worker.satquery.internal"):
        with patch.object(settings, "ALLOW_MOCK_FALLBACK", False):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                with pytest.raises(RemoteWorkerUnavailableError) as exc_info:
                    await client.execute(model_id="prithvi-eo-2.0", query="vegetation change in Kashmir", aoi=aoi)

                assert "not found" in str(exc_info.value).lower()

    # In live execution mode with ALLOW_MOCK_FALLBACK=False, execute_unknown_analysis
    # must catch this and return an honest unavailable NormalizedResult, NEVER mock
    with patch("app.services.worker_client.EOWorkerClient.execute", new_callable=AsyncMock, side_effect=RemoteWorkerUnavailableError("Worker returned HTTP 404")):
        with patch.object(settings, "ALLOW_MOCK_FALLBACK", False):
            with patch.object(settings, "EO_EXECUTION_MODE", "live"):
                state = {
                    "user_query": "how kashmir has changed in last 10 years in terms of vegetation, i am thinking to start an apple farm there, will it be good option",
                    "aoi": aoi,
                    "target_sensor": "sentinel-2-l2a",
                    "discovered_assets": [],
                    "search_metadata": {},
                }
                out = await execute_unknown_analysis(state)
                norm_dict = out["normalized_result"]
                norm = NormalizedResult.model_validate(norm_dict)

                assert norm.provenance.source == "unavailable"
                assert norm.provenance.fallback is False
                assert norm.provenance.execution_status == "unavailable"
                assert norm.metrics == []
                assert norm.confidence is None
                assert "Apple" in norm.key_finding or "Offline" in norm.key_finding or "Specialist" in norm.key_finding
                # Ensure no flood extent layer
                for l in norm.layers:
                    assert l.layer_id != "flood_extent"
                    assert "flood" not in l.layer_id.lower()


# ---------------------------------------------------------------------------
# Case C: Real remote worker returns 500
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_case_c_worker_500_reports_error_no_mock():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error in model pipeline"

    client = EOWorkerClient()
    aoi = AOIInfo(
        name="Valencia",
        center=Coordinates(latitude=39.4699, longitude=-0.3763),
        area_km2=134.65,
        bbox=[-0.45, 39.40, -0.30, 39.52],
    )

    with patch.object(settings, "CLOSP_WORKER_URL", "https://mock-worker.satquery.internal"):
        with patch.object(settings, "ALLOW_MOCK_FALLBACK", False):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                with pytest.raises(RemoteWorkerUnavailableError) as exc_info:
                    await client.execute(model_id="closp", query="flood extent in Valencia", aoi=aoi)

                assert "500" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Case D: Real remote worker times out
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_case_d_worker_timeout_reports_unavailable():
    client = EOWorkerClient()
    aoi = AOIInfo(
        name="Kashmir",
        center=Coordinates(latitude=34.0837, longitude=74.7973),
        area_km2=222236.0,
        bbox=[73.5, 32.5, 76.5, 35.5],
    )

    with patch.object(settings, "EARTHDIAL_WORKER_URL", "https://mock-worker.satquery.internal"):
        with patch.object(settings, "ALLOW_MOCK_FALLBACK", False):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.TimeoutException("Connection timed out after 30s")):
                with pytest.raises(RemoteWorkerUnavailableError) as exc_info:
                    await client.execute(model_id="earthdial-4b-ms", query="multispectral change in Kashmir", aoi=aoi)

                assert "worker_timeout" in str(exc_info.value) or "timed out" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Case E: Real remote worker returns malformed response
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_case_e_worker_malformed_response_fails_cleanly():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = Exception("JSONDecodeError: Expecting value")

    client = EOWorkerClient()
    aoi = AOIInfo(
        name="Kashmir",
        center=Coordinates(latitude=34.0837, longitude=74.7973),
        area_km2=222236.0,
        bbox=[73.5, 32.5, 76.5, 35.5],
    )

    with patch.object(settings, "PRITHVI_WORKER_URL", "https://mock-worker.satquery.internal"):
        with patch.object(settings, "ALLOW_MOCK_FALLBACK", False):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                with pytest.raises(RemoteWorkerUnavailableError) as exc_info:
                    await client.execute(model_id="prithvi-eo-2.0", query="vegetation change in Kashmir", aoi=aoi)

                assert "JSONDecodeError" in str(exc_info.value) or "unavailable" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Case F: Scenario matcher blocked when ALLOW_MOCK_FALLBACK=False
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_case_f_scenario_matcher_blocked_in_live_mode():
    with patch.object(settings, "ALLOW_MOCK_FALLBACK", False):
        with patch.object(settings, "EO_EXECUTION_MODE", "live"):
            aoi = AOIInfo(
                name="Kashmir",
                center=Coordinates(latitude=34.0837, longitude=74.7973),
                area_km2=222236.0,
                bbox=[73.5, 32.5, 76.5, 35.5],
            )
            state = {
                "user_query": "how kashmir has changed in last 10 years in terms of vegetation, i am thinking to start an apple farm there, will it be good option",
                "aoi": aoi,
                "target_sensor": "sentinel-2-l2a",
                "discovered_assets": [],
                "search_metadata": {},
            }
            # Even if remote worker fails, scenario mock MUST NOT be used
            with patch("app.services.worker_client.EOWorkerClient.execute", new_callable=AsyncMock, side_effect=RemoteWorkerUnavailableError("Specialist worker 404")):
                out = await execute_unknown_analysis(state)
                norm_dict = out["normalized_result"]
                norm = NormalizedResult.model_validate(norm_dict)

                # Ensure source is 'unavailable', NOT 'mock'
                assert norm.provenance.source == "unavailable"
                assert norm.provenance.fallback is False
                assert norm.metrics == []
                # Ensure 14.82% or 38420 are NOT present
                for m in norm.metrics:
                    assert "14.82" not in m.value
                    assert "38,420" not in m.value


# ---------------------------------------------------------------------------
# Case G: Visualization registry does not fabricate specialist layers / flood
# ---------------------------------------------------------------------------
def test_case_g_no_fabricated_specialist_layers_when_offline():
    aoi = AOIInfo(
        name="Kashmir",
        center=Coordinates(latitude=34.0837, longitude=74.7973),
        area_km2=222236.0,
        bbox=[73.5, 32.5, 76.5, 35.5],
    )
    norm = NormalizedResult(
        query="how kashmir has changed in last 10 years in terms of vegetation",
        analysis_type="temporal_vegetation_analysis",
        aoi=aoi,
        provenance=Provenance(
            source="unavailable",
            execution_status="unavailable",
            fallback=False,
            model_id="prithvi-eo-2.0",
            model_name="Prithvi-EO-2.0",
            dataset_ids=["sentinel-2-l2a"],
        ),
        metrics=[],
        key_finding="Specialist inference unavailable.",
        scientific_explanation="Remote worker offline.",
    )
    # Unavailable specialist analysis
    layers = build_data_layers(
        norm=norm,
        query="how kashmir has changed in last 10 years in terms of vegetation",
    )

    layer_ids = [l.layer_id for l in layers]
    # Should NOT have flood_extent
    assert "flood_extent" not in layer_ids
    # Should NOT have any water layer for a vegetation query
    for l in layers:
        assert "flood" not in l.layer_id.lower()


# ---------------------------------------------------------------------------
# Case H: Narrative generator reports honest unavailable state and decoupled advisory
# ---------------------------------------------------------------------------
def test_case_h_narrative_honesty_and_apple_farm_decoupling():
    aoi = AOIInfo(
        name="Kashmir",
        center=Coordinates(latitude=34.0837, longitude=74.7973),
        area_km2=222236.0,
        bbox=[73.5, 32.5, 76.5, 35.5],
    )
    norm = NormalizedResult(
        query="how kashmir has changed in last 10 years in terms of vegetation, i am thinking to start an apple farm there, will it be good option",
        analysis_type="temporal_vegetation_analysis",
        aoi=aoi,
        provenance=Provenance(
            source="unavailable",
            execution_status="unavailable",
            fallback=False,
            model_id="prithvi-eo-2.0",
            model_name="Prithvi-EO-2.0",
            dataset_ids=["sentinel-2-l2a"],
        ),
        metrics=[],
        confidence=None,
        key_finding="Specialist change-detection inference unavailable. Optical scenes discovered for inspection.",
        scientific_explanation="Remote specialist worker offline.",
    )

    plan = evidence_service.build_presentation_plan(
        query="how kashmir has changed in last 10 years in terms of vegetation, i am thinking to start an apple farm there, will it be good option",
        norm=norm,
    )
    norm.presentation_plan = plan.model_dump()

    md = _format_presentation_plan_markdown(norm.model_dump())

    # 1. Honest reporting
    assert "Specialist foundation model inference (Prithvi-EO-2.0) is currently offline" in md or "offline" in md.lower()
    # 2. No fabricated percentage
    assert "14.82%" not in md
    assert "38,420" not in md
    # 3. Decoupled apple farming advisory
    assert "Agricultural Decision Support" in md
    assert "Apple Cultivation Feasibility" in md
    assert "chilling hours" in md.lower()
    assert "pH" in md
    assert "soil sampling" in md.lower() or "cannot establish in-situ agronomic feasibility" in md.lower()


# ---------------------------------------------------------------------------
# Case I: Strict provenance consistency contract
# ---------------------------------------------------------------------------
def test_case_i_provenance_consistency_contract():
    # 1. Valid remote_worker
    p1 = Provenance(
        source="remote_worker",
        fallback=False,
        worker_url="https://worker.satquery.internal/predict",
        model_id="prithvi",
        model_name="Prithvi-EO-2.0",
        dataset_ids=["sentinel-2-l2a"],
        execution_status="success",
    )
    assert p1.source == "remote_worker"
    assert p1.fallback is False

    # 2. Invalid: remote_worker with fallback=True must raise
    with pytest.raises(ValueError, match="fallback=True is only valid when source is 'mock'"):
        Provenance(
            source="remote_worker",
            fallback=True,
            worker_url="https://worker.satquery.internal/predict",
            model_id="prithvi",
            model_name="Prithvi-EO-2.0",
            dataset_ids=["sentinel-2-l2a"],
        )

    # 3. Invalid: remote_worker with empty worker_url must raise
    with pytest.raises(ValueError, match="worker_url must exist"):
        Provenance(
            source="remote_worker",
            fallback=False,
            worker_url=None,
            model_id="prithvi",
            model_name="Prithvi-EO-2.0",
            dataset_ids=["sentinel-2-l2a"],
        )

    # 4. Valid mock: source=mock must have fallback=True
    p_mock = Provenance(
        source="mock",
        model_id="prithvi",
        model_name="Prithvi-EO-2.0",
        dataset_ids=["sentinel-2-l2a"],
    )
    assert p_mock.fallback is True

    # 5. Invalid: source=mock with fallback=False must raise
    with pytest.raises(ValueError, match="source cannot be 'mock' when fallback is False"):
        Provenance(
            source="mock",
            fallback=False,
            model_id="prithvi",
            model_name="Prithvi-EO-2.0",
            dataset_ids=["sentinel-2-l2a"],
        )

    # 6. Valid unavailable: source=unavailable, fallback=False
    p_unavail = Provenance(
        source="unavailable",
        fallback=False,
        execution_status="unavailable",
        model_id="prithvi",
        model_name="Prithvi-EO-2.0",
        dataset_ids=["sentinel-2-l2a"],
    )
    assert p_unavail.source == "unavailable"
    assert p_unavail.fallback is False
