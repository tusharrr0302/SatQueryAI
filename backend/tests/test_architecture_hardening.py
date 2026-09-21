import asyncio
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.schemas.normalized_result import ConversationalMode, VisualizationType, AOIInfo, Coordinates
from app.imagery.planetary_computer import SceneData
from app.graph.nodes import (
    determine_conversational_mode_and_gate,
    _format_unknown_markdown_fallback,
)
from app.services.scenario_matcher import find_matching_scenario
from app.models.manager import ModelManager
from app.services.worker_client import EOWorkerClient, RemoteWorkerUnavailableError

client = TestClient(app, headers={"Authorization": "Bearer test_token_analyst"})


def _mock_scene(ndvi: float, name: str) -> SceneData:
    red = np.full((2, 2), 100.0)
    nir = np.full((2, 2), 100.0 * (1 + ndvi) / (1 - ndvi))
    return SceneData(name, "2025-01-01", red, red, red, nir, {}, 0.0, Path("/tmp/test.png"))


# ==============================================================================
# TEST A: Query "What is NDVI?" -> mode=ANSWER, vis_required=False, zero layers/charts
# ==============================================================================
def test_a_what_is_ndvi_answer_first_no_visualization():
    query = "What is NDVI?"
    mode, gate = determine_conversational_mode_and_gate(query, geographic_entity=None)
    assert mode == ConversationalMode.ANSWER
    assert gate.visualization_required is False
    assert gate.visualization_type == VisualizationType.NONE.value

    # Test through /api/chat endpoint
    res = client.post("/api/chat", json={"query": query})
    assert res.status_code == 200
    data = res.json()

    assert data["visualization"]["required"] is False
    assert data["visualization"]["type"] == "none"
    assert data["layers"] == []
    assert data["visualizations"] == []
    assert data["globe_actions"] == []
    assert data["globe_action"] is None
    assert data["visualization_plan"] is None
    assert "response" in data
    assert data["response"]["mode"] == "answer"


# ==============================================================================
# TEST B: Query "Show vegetation in Delhi" -> mode=EARTH_ANALYSIS, vis_required=True
# ==============================================================================
def test_b_show_vegetation_delhi_visualizes_minimum_useful(monkeypatch):
    monkeypatch.setattr(settings, "EO_EXECUTION_MODE", "mock")
    query = "Show vegetation in Delhi"
    mode, gate = determine_conversational_mode_and_gate(query, geographic_entity="Delhi")
    assert mode in [ConversationalMode.EARTH_ANALYSIS, ConversationalMode.VISUALIZATION]
    assert gate.visualization_required is True

    res = client.post("/api/chat", json={"query": query})
    assert res.status_code == 200
    data = res.json()

    assert data["visualization"]["required"] is True
    assert len(data["layers"]) >= 1  # 1 primary layer
    assert len(data["layers"]) <= 4  # minimum useful (1 primary + 0-2 supporting)
    assert data["globe_action"] is not None
    assert data["globe_action"]["action"] in ["fly_to", "set_camera"]


# ==============================================================================
# TEST C: Query "What satellites do you have in the catalog?" -> mode=ANSWER, vis_required=False
# ==============================================================================
def test_c_catalog_query_answer_first():
    query = "What satellites do you have in the catalog?"
    mode, gate = determine_conversational_mode_and_gate(query, geographic_entity=None)
    assert mode == ConversationalMode.ANSWER
    assert gate.visualization_required is False

    res = client.post("/api/chat", json={"query": query})
    assert res.status_code == 200
    data = res.json()
    assert data["visualization"]["required"] is False
    assert data["layers"] == []
    assert data["visualizations"] == []


# ==============================================================================
# TEST D: Query "Compare vegetation between Munich and Berlin" -> mode=COMPARISON, vis_required=True
# ==============================================================================
def test_d_compare_munich_and_berlin():
    query = "Compare vegetation between Munich and Berlin"
    mode, gate = determine_conversational_mode_and_gate(query, geographic_entity="Munich")
    assert mode == ConversationalMode.COMPARISON
    assert gate.visualization_required is True
    assert gate.visualization_type == VisualizationType.COMPARISON.value


# ==============================================================================
# TEST E: Deterministic Sentinel-2 NDVI provenance
# ==============================================================================
@patch("app.models.manager.fetch_before_after_and_series")
def test_e_deterministic_ndvi_provenance(mock_fetch):
    mock_fetch.return_value = (_mock_scene(0.2, "before"), _mock_scene(0.4, "after"), [_mock_scene(0.2, "series")])
    manager = ModelManager()
    aoi = AOIInfo(name="Delhi", center=Coordinates(latitude=28.6, longitude=77.2), bbox=[76.8, 28.4, 77.4, 28.9], area_km2=100.0)
    result = manager.execute(
        model_id="deterministic-spectral-analysis",
        query="Show vegetation in Delhi",
        request={"aoi": {"name": "Delhi"}},
        aoi=aoi,
    )
    prov = result.provenance
    assert prov.model_id == "deterministic-spectral-analysis"
    assert prov.model_name == "Deterministic Spectral Analysis"
    assert "Sentinel-2 L2A" in prov.dataset_ids
    assert prov.algorithm == "NDVI = (B08 - B04) / (B08 + B04)"


# ==============================================================================
# TEST F: Prithvi provenance only on real Prithvi inference
# ==============================================================================
@patch("app.models.manager.fetch_before_after_and_series")
def test_f_prithvi_provenance_isolation(mock_fetch, monkeypatch):
    monkeypatch.setattr(settings, "PRITHVI_WORKER_URL", None)
    monkeypatch.setattr(settings, "CHANGE_DETECTION_WORKER_URL", None)
    mock_fetch.return_value = (_mock_scene(0.2, "before"), _mock_scene(0.4, "after"), [_mock_scene(0.2, "series")])
    manager = ModelManager()
    aoi = AOIInfo(name="Delhi", center=Coordinates(latitude=28.6, longitude=77.2), bbox=[76.8, 28.4, 77.4, 28.9], area_km2=100.0)
    # When requesting local execution for prithvi-eo-2.0 without a hosted model,
    # fallback to deterministic analysis must NEVER be falsely labeled as prithvi-eo-2.0
    result = manager.execute(
        model_id="prithvi-eo-2.0",
        query="Calculate NDVI",
        request={"aoi": {"name": "Delhi"}},
        aoi=aoi,
    )
    assert result.provenance.model_id != "prithvi-eo-2.0"
    assert result.provenance.model_name != "Prithvi-EO-2.0"
    assert result.provenance.model_id == "deterministic-spectral-analysis"


# ==============================================================================
# TEST G: Remote worker unavailable + ALLOW_MOCK_FALLBACK=False -> explicit error
# ==============================================================================
def test_g_worker_unavailable_strict_mode(monkeypatch):
    monkeypatch.setattr(settings, "EO_EXECUTION_MODE", "worker")
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", False)
    monkeypatch.setattr(settings, "PRITHVI_WORKER_URL", "http://127.0.0.1:59999")

    worker_client = EOWorkerClient()
    with pytest.raises(RemoteWorkerUnavailableError):
        asyncio.run(worker_client.execute("prithvi-eo-2.0", {"query": "Delhi vegetation"}))


# ==============================================================================
# TEST H: Remote worker unavailable + ALLOW_MOCK_FALLBACK=True -> explicit provenance
# ==============================================================================
def test_h_worker_unavailable_mock_fallback(monkeypatch):
    monkeypatch.setattr(settings, "EO_EXECUTION_MODE", "worker")
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", True)
    monkeypatch.setattr(settings, "PRITHVI_WORKER_URL", "http://127.0.0.1:59999")

    worker_client = EOWorkerClient()
    result = asyncio.run(worker_client.execute(
        "prithvi-eo-2.0",
        {"query": "Show me the vegetation change in Delhi over the last 1 year using Sentinel-2 data.", "location": "Delhi"},
    ))
    assert result.provenance.source == "mock"
    assert result.provenance.fallback is True
    assert "worker unavailable" in result.provenance.notes.lower()


# ==============================================================================
# TEST I: Unknown query does NOT match Delhi vegetation scenario
# ==============================================================================
def test_i_unknown_query_does_not_match_mock_delhi():
    unknown_queries = [
        "Explain photosynthesis in detail",
        "How do nuclear power plants work?",
        "What is the capital of France?",
        "Write a poem about satellites",
    ]
    for q in unknown_queries:
        matched = find_matching_scenario(q)
        assert matched is None, f"Query '{q}' unexpectedly matched mock scenario {matched.get('id') if matched else ''}"


# ==============================================================================
# TEST J: Deterministic analysis final answer has safe causal claims
# ==============================================================================
def test_j_safe_causal_claims_in_explanation():
    norm_dict = {
        "analysis_type": "vegetation_health",
        "key_finding": "Observed a 12% decline in vegetative index over the designated AOI.",
        "aoi": {"name": "Test Region"},
        "provenance": {
            "model_name": "Deterministic Spectral Analysis",
            "dataset_ids": ["sentinel-2-l2a"],
            "source": "live",
            "algorithm": "NDVI = (B08 - B04) / (B08 + B04)",
        },
        "metrics": [{"label": "NDVI Drop", "value": "-0.12"}],
    }
    md = _format_unknown_markdown_fallback("Why did vegetation drop in Test Region?", norm_dict)
    assert "Observed" in md
    assert "Possible explanations" in md
    assert "Not established" in md
    # Ensure it states satellite data alone cannot prove ground causation
    assert "cannot establish" in md.lower() or "does not establish" in md.lower() or "further field verification" in md.lower()


# ==============================================================================
# TEST K: Response contract on /api/chat
# ==============================================================================
def test_k_response_contract_structure():
    res = client.post("/api/chat", json={"query": "What is the difference between Sentinel-1 and Sentinel-2?"})
    assert res.status_code == 200
    data = res.json()

    assert "response" in data
    assert "mode" in data["response"]
    assert "answer" in data["response"]

    assert "visualization" in data
    assert "required" in data["visualization"]
    assert "reason" in data["visualization"]
    assert "type" in data["visualization"]

    assert "evidence" in data
    assert isinstance(data["evidence"], list)

    assert "provenance" in data
    assert isinstance(data["provenance"], list)

    assert "execution" in data
    assert isinstance(data["execution"], list)


# ==============================================================================
# TEST L: Visualization suppression when visualization.required == False
# ==============================================================================
def test_l_visualization_suppression():
    res = client.post("/api/chat", json={"query": "Explain what SAR interferometry is"})
    assert res.status_code == 200
    data = res.json()

    assert data["visualization"]["required"] is False
    assert data["layers"] == []
    assert data["visualizations"] == []
    assert data["globe_actions"] == []
    assert data["globe_action"] is None
    assert data["visualization_plan"] is None


# ==============================================================================
# TEST M: Auth hardening rejects unverified JWT in production
# ==============================================================================
def test_m_auth_production_rejects_unverified_jwt(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    
    prod_client = TestClient(app)
    # Sending test token or unverified token in production must result in 401
    response = prod_client.get("/api/conversations", headers={"Authorization": "Bearer test_token_unverified"})
    assert response.status_code == 401
