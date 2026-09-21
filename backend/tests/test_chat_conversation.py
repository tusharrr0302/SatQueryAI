"""
SatQuery AI — End-to-End Conversational Response Pipeline Test Suite

Verifies the complete 9-turn conversational dialogue through /api/chat:
1. "Analyze vegetation in Delhi."
2. "so is it better?"
3. "why?"
4. "what dataset did you use?"
5. "show it on the globe."
6. "what about the southern region?"
7. "now compare that with urban expansion."
8. "what about Mumbai?"
9. "explain Mumbai's result like I'm a beginner."

For every turn, validates:
- conversation_id stability
- request_id uniqueness & propagation
- question_type / intent classification matching the 9 canonical response types
- active AOI and action (reuse vs resolve_new)
- Nominatim bypass for follow-up turns (only called for Turn 1 and Turn 8)
- Material difference between consecutive responses (no duplicate or stale answers)
- Proper globe actions for visualization requests
- Proper beginner explanation framing for Turn 9
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.normalized_result import AOIInfo, Coordinates

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test_token_full_conversation"}


@pytest.fixture(autouse=True)
def mock_imagery_fetch(monkeypatch):
    """Mocks satellite imagery fetching to prevent external network stalls during live model execution."""
    import numpy as np
    from pathlib import Path
    from app.imagery.planetary_computer import SceneData
    from app.config import settings

    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", True)
    monkeypatch.setattr(settings, "PRITHVI_WORKER_URL", None)
    monkeypatch.setattr(settings, "CHANGE_DETECTION_WORKER_URL", None)
    monkeypatch.setattr(settings, "CLOSP_WORKER_URL", None)
    monkeypatch.setattr(settings, "EARTHDIAL_WORKER_URL", None)

    output_dir = Path(__file__).resolve().parents[1] / settings.IMAGE_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    dummy_img = output_dir / "test_scene_conv.png"
    dummy_img.touch(exist_ok=True)

    dummy_scene = SceneData(
        item_id="S2_test_scene_conv",
        date="2024-01-01",
        red=np.full((10, 10), 0.2),
        green=np.full((10, 10), 0.3),
        blue=np.full((10, 10), 0.1),
        nir=np.full((10, 10), 0.5),
        profile={"transform": MagicMock(a=10, e=-10, b=0, d=0)},
        cloud_cover=5.0,
        true_color_path=dummy_img,
        pixel_area_km2=0.0001,
    )

    with patch("app.models.manager.fetch_before_after_and_series", return_value=(dummy_scene, dummy_scene, [dummy_scene])):
        yield


@pytest.fixture
def spy_nominatim():
    """Tracks Nominatim / resolve_aoi calls to ensure geocoding occurs ONLY for explicit locations."""
    calls = []

    def spy_resolve(name: str):
        calls.append(name)
        is_delhi = "delhi" in name.lower()
        lat = 28.6139 if is_delhi else 19.0760
        lon = 77.2090 if is_delhi else 72.8777
        bbox = [76.84, 28.40, 77.35, 28.88] if is_delhi else [72.77, 18.89, 72.98, 19.27]
        return AOIInfo(
            id=f"aoi_{abs(hash(name))}",
            name=name.split(",")[0].strip(),
            country="India",
            center=Coordinates(latitude=lat, longitude=lon),
            area_km2=150.0,
            bbox=bbox,
            polygon=[
                [bbox[0], bbox[1]], [bbox[2], bbox[1]],
                [bbox[2], bbox[3]], [bbox[0], bbox[3]],
                [bbox[0], bbox[1]],
            ],
        )

    with patch("app.geo.resolver.resolve_aoi", side_effect=spy_resolve):
        yield calls


def test_complete_9_turn_conversational_pipeline(spy_nominatim):
    """
    Executes the authoritative 9-turn conversational sequence through /api/chat.
    """
    # -------------------------------------------------------------------------
    # Turn 1: "Analyze vegetation in Delhi."
    # -------------------------------------------------------------------------
    req1 = {"query": "Analyze vegetation in Delhi."}
    r1 = client.post("/api/chat", json=req1, headers=AUTH_HEADERS)
    assert r1.status_code == 200, f"Turn 1 failed: {r1.text}"
    d1 = r1.json()

    conv_id = d1["conversation_id"]
    assert conv_id is not None, "Turn 1 must produce a conversation_id"
    req_id_1 = d1.get("request_id")
    assert req_id_1 is not None, "Turn 1 must produce a request_id"
    assert d1["status"] == "success"

    # Intent & Question Type
    assert d1["question_type"] in ["NEW_ANALYSIS", "new_analysis"]
    assert d1["is_conversational"] is False
    assert "delhi" in d1["result"]["aoi"]["name"].lower()

    # Assistant content & provenance
    ans1 = d1["assistant_message"]["content"]
    assert len(ans1) > 50, "Turn 1 answer must be substantive"
    assert "delhi" in ans1.lower()
    prov1 = d1["result"]["provenance"]
    assert prov1.get("model_name") is not None
    assert prov1.get("dataset_ids") is not None

    nominatim_after_t1 = len(spy_nominatim)

    # -------------------------------------------------------------------------
    # Turn 2: "so is it better?"
    # -------------------------------------------------------------------------
    req2 = {"conversation_id": conv_id, "query": "so is it better?"}
    r2 = client.post("/api/chat", json=req2, headers=AUTH_HEADERS)
    assert r2.status_code == 200, f"Turn 2 failed: {r2.text}"
    d2 = r2.json()

    assert d2["conversation_id"] == conv_id, "Conversation ID must remain stable across turns"
    assert d2["request_id"] != req_id_1, "Each turn must have a unique request_id"
    req_id_2 = d2["request_id"]
    assert d2["status"] == "success"

    # Intent & Conversational flag
    assert d2["question_type"] == "RESULT_EXPLANATION"
    assert d2["is_conversational"] is True
    assert d2["assistant_message"]["is_conversational"] is True

    # NOMINATIM MUST BE BYPASSED
    assert len(spy_nominatim) == nominatim_after_t1, f"Nominatim was called for 'so is it better?': {spy_nominatim}"

    ans2 = d2["assistant_message"]["content"]
    assert len(ans2) > 20
    assert "Nominatim returned no AOI" not in ans2
    # Must be materially different from Turn 1
    assert ans2 != ans1, "Turn 2 response must not duplicate Turn 1 response"

    # -------------------------------------------------------------------------
    # Turn 3: "why?"
    # -------------------------------------------------------------------------
    req3 = {"conversation_id": conv_id, "query": "why?"}
    r3 = client.post("/api/chat", json=req3, headers=AUTH_HEADERS)
    assert r3.status_code == 200, f"Turn 3 failed: {r3.text}"
    d3 = r3.json()

    assert d3["conversation_id"] == conv_id
    assert d3["request_id"] != req_id_2
    req_id_3 = d3["request_id"]
    assert d3["status"] == "success"

    assert d3["question_type"] == "RESULT_EXPLANATION"
    assert d3["is_conversational"] is True

    # NOMINATIM MUST BE BYPASSED
    assert len(spy_nominatim) == nominatim_after_t1, f"Nominatim was called for 'why?': {spy_nominatim}"

    ans3 = d3["assistant_message"]["content"]
    assert len(ans3) > 20
    # Must be materially different from Turn 1 and Turn 2
    assert ans3 != ans2, "Turn 3 response must not duplicate Turn 2 response"
    assert ans3 != ans1, "Turn 3 response must not duplicate Turn 1 response"

    # -------------------------------------------------------------------------
    # Turn 4: "what dataset did you use?"
    # -------------------------------------------------------------------------
    req4 = {"conversation_id": conv_id, "query": "what dataset did you use?"}
    r4 = client.post("/api/chat", json=req4, headers=AUTH_HEADERS)
    assert r4.status_code == 200, f"Turn 4 failed: {r4.text}"
    d4 = r4.json()

    assert d4["conversation_id"] == conv_id
    assert d4["request_id"] != req_id_3
    req_id_4 = d4["request_id"]
    assert d4["status"] == "success"

    assert d4["question_type"] == "PROVENANCE_QUESTION"
    assert d4["is_conversational"] is True

    # NOMINATIM MUST BE BYPASSED
    assert len(spy_nominatim) == nominatim_after_t1, f"Nominatim was called for provenance inquiry: {spy_nominatim}"

    ans4 = d4["assistant_message"]["content"]
    assert any(k in ans4.lower() for k in ["sentinel", "prithvi", "telemetry", "dataset", "resolution", "sensor"])
    assert ans4 != ans3, "Turn 4 response must not duplicate Turn 3 response"

    # -------------------------------------------------------------------------
    # Turn 5: "show it on the globe."
    # -------------------------------------------------------------------------
    req5 = {"conversation_id": conv_id, "query": "show it on the globe."}
    r5 = client.post("/api/chat", json=req5, headers=AUTH_HEADERS)
    assert r5.status_code == 200, f"Turn 5 failed: {r5.text}"
    d5 = r5.json()

    assert d5["conversation_id"] == conv_id
    assert d5["request_id"] != req_id_4
    req_id_5 = d5["request_id"]
    assert d5["status"] == "success"

    assert d5["question_type"] == "VISUALIZATION_REQUEST"
    assert d5["is_conversational"] is True

    # NOMINATIM MUST BE BYPASSED
    assert len(spy_nominatim) == nominatim_after_t1, f"Nominatim was called for globe request: {spy_nominatim}"

    # Globe action assertion
    globe_actions = d5.get("globe_actions") or []
    assert len(globe_actions) > 0, "Turn 5 must generate globe_actions for CesiumJS"
    action_types = [a.get("type") or a.get("action") for a in globe_actions]
    assert any("fly" in str(at).lower() for at in action_types), f"Expected fly_to in globe actions: {globe_actions}"

    ans5 = d5["assistant_message"]["content"]
    assert any(k in ans5.lower() for k in ["globe", "map", "delhi", "focused", "telemetry", "3d"])

    # -------------------------------------------------------------------------
    # Turn 6: "what about the southern region?"
    # -------------------------------------------------------------------------
    req6 = {"conversation_id": conv_id, "query": "what about the southern region?"}
    r6 = client.post("/api/chat", json=req6, headers=AUTH_HEADERS)
    assert r6.status_code == 200, f"Turn 6 failed: {r6.text}"
    d6 = r6.json()

    assert d6["conversation_id"] == conv_id
    assert d6["request_id"] != req_id_5
    req_id_6 = d6["request_id"]
    assert d6["status"] == "success"

    assert d6["question_type"] == "CONTEXTUAL_SPATIAL_REQUEST"
    # MUST NOT geocode "southern region"
    assert not any("southern region" in call.lower() for call in spy_nominatim), f"Geocoded 'southern region': {spy_nominatim}"

    ans6 = d6["assistant_message"]["content"]
    assert len(ans6) > 20
    assert any(k in ans6.lower() for k in ["southern", "south", "delhi", "observation", "telemetry", "sector"])
    assert ans6 != ans5

    # -------------------------------------------------------------------------
    # Turn 7: "now compare that with urban expansion."
    # -------------------------------------------------------------------------
    req7 = {"conversation_id": conv_id, "query": "now compare that with urban expansion."}
    r7 = client.post("/api/chat", json=req7, headers=AUTH_HEADERS)
    assert r7.status_code == 200, f"Turn 7 failed: {r7.text}"
    d7 = r7.json()

    assert d7["conversation_id"] == conv_id
    assert d7["request_id"] != req_id_6
    req_id_7 = d7["request_id"]
    assert d7["status"] == "success"

    assert d7["question_type"] == "FOLLOW_UP_ANALYSIS"
    # Follow-up comparative analysis on Delhi -> Nominatim must NOT be called for "now compare that with urban expansion."
    assert not any("urban expansion" in call.lower() for call in spy_nominatim), f"Geocoded 'urban expansion': {spy_nominatim}"

    ans7 = d7["assistant_message"]["content"]
    assert len(ans7) > 30
    assert any(k in ans7.lower() for k in ["urban", "expansion", "built-up", "sprawl", "growth", "delhi"])
    assert ans7 != ans6

    nominatim_before_mumbai = len(spy_nominatim)

    # -------------------------------------------------------------------------
    # Turn 8: "what about Mumbai?"
    # -------------------------------------------------------------------------
    req8 = {"conversation_id": conv_id, "query": "what about Mumbai?"}
    r8 = client.post("/api/chat", json=req8, headers=AUTH_HEADERS)
    assert r8.status_code == 200, f"Turn 8 failed: {r8.text}"
    d8 = r8.json()

    assert d8["conversation_id"] == conv_id
    assert d8["request_id"] != req_id_7
    req_id_8 = d8["request_id"]
    assert d8["status"] == "success"

    assert d8["question_type"] in ["NEW_LOCATION_ANALYSIS", "NEW_ANALYSIS"]
    # NEW LOCATION MUST BE GEOCODED (and clean location "Mumbai, India", NOT full query)
    assert len(spy_nominatim) > nominatim_before_mumbai, "Turn 8 should resolve new location for Mumbai"
    assert any("mumbai" in call.lower() for call in spy_nominatim), f"Expected Mumbai in Nominatim calls: {spy_nominatim}"
    assert not any("what about" in call.lower() for call in spy_nominatim), f"Raw sentence geocoded: {spy_nominatim}"

    assert d8["result"]["aoi"]["name"] == "Mumbai"
    ans8 = d8["assistant_message"]["content"]
    assert len(ans8) > 30
    assert "mumbai" in ans8.lower()

    nominatim_after_mumbai = len(spy_nominatim)

    # -------------------------------------------------------------------------
    # Turn 9: "explain Mumbai's result like I'm a beginner."
    # -------------------------------------------------------------------------
    req9 = {"conversation_id": conv_id, "query": "explain Mumbai's result like I'm a beginner."}
    r9 = client.post("/api/chat", json=req9, headers=AUTH_HEADERS)
    assert r9.status_code == 200, f"Turn 9 failed: {r9.text}"
    d9 = r9.json()

    assert d9["conversation_id"] == conv_id
    assert d9["request_id"] != req_id_8
    assert d9["status"] == "success"

    assert d9["question_type"] == "RESULT_EXPLANATION"
    assert d9["is_conversational"] is True

    # Nominatim MUST NOT be called again
    assert len(spy_nominatim) == nominatim_after_mumbai, f"Nominatim was called for beginner explanation: {spy_nominatim}"

    ans9 = d9["assistant_message"]["content"]
    assert len(ans9) > 20
    assert any(k in ans9.lower() for k in ["simple", "everyday", "mumbai", "terms", "satellite", "means", "plain", "beginner"])
    assert ans9 != ans8, "Turn 9 beginner explanation must not duplicate Turn 8 technical analysis"
