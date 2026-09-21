import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.db.models import User, Conversation, Message

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test_token_alice"}


@pytest.fixture(autouse=True)
def clean_test_user(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ALLOW_MOCK_FALLBACK", True)
    monkeypatch.setattr(settings, "PRITHVI_WORKER_URL", None)
    monkeypatch.setattr(settings, "CHANGE_DETECTION_WORKER_URL", None)
    monkeypatch.setattr(settings, "CLOSP_WORKER_URL", None)
    monkeypatch.setattr(settings, "EARTHDIAL_WORKER_URL", None)

    db = SessionLocal()
    try:
        users = db.query(User).filter(User.clerk_user_id == "user_alice").all()
        for u in users:
            db.delete(u)
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.clerk_user_id == "user_alice").all()
        for u in users:
            db.delete(u)
        db.commit()
    finally:
        db.close()


def test_multiturn_six_message_sequence():
    """
    Test 1: Mandatory Multi-Turn sequence from Section 25:
    1. 'Analyze vegetation in Delhi.'
    2. 'What about the southern region?'
    3. 'Compare that with urban expansion.'
    4. 'Show this on the globe.'
    5. 'What datasets did you use?'
    6. 'Explain that result like I'm a beginner.'

    Verifies:
    - Same conversation_id preserved throughout.
    - Previous messages reliably preserved in database.
    - Each turn answers specifically.
    - No turn returns empty message or crashes.
    """
    # 1. Turn 1
    t1_res = client.post("/api/chat", json={"query": "Analyze vegetation in Delhi."}, headers=AUTH_HEADERS)
    assert t1_res.status_code == 200, f"Turn 1 failed: {t1_res.text}"
    t1 = t1_res.json()
    conv_id = t1.get("conversation_id")
    assert conv_id is not None
    assert len(t1["assistant_message"]["content"]) > 10
    assert t1["status"] == "success"

    # 2. Turn 2: Follow-up on southern region
    t2_res = client.post("/api/chat", json={"query": "What about the southern region?", "conversation_id": conv_id}, headers=AUTH_HEADERS)
    assert t2_res.status_code == 200, f"Turn 2 failed: {t2_res.text}"
    t2 = t2_res.json()
    assert t2.get("conversation_id") == conv_id
    assert len(t2["assistant_message"]["content"]) > 10
    assert t2["status"] == "success"
    # Should understand southern in context of Delhi
    assert any(k in t2["assistant_message"]["content"].lower() or (t2.get("result") and "delhi" in str(t2.get("result")).lower()) for k in ["south", "delhi", "vegetation"])

    # 3. Turn 3: Compare with urban expansion
    t3_res = client.post("/api/chat", json={"query": "Compare that with urban expansion.", "conversation_id": conv_id}, headers=AUTH_HEADERS)
    assert t3_res.status_code == 200, f"Turn 3 failed: {t3_res.text}"
    t3 = t3_res.json()
    assert t3.get("conversation_id") == conv_id
    assert len(t3["assistant_message"]["content"]) > 10
    assert t3["status"] == "success"

    # 4. Turn 4: Show on globe
    t4_res = client.post("/api/chat", json={"query": "Show this on the globe.", "conversation_id": conv_id}, headers=AUTH_HEADERS)
    assert t4_res.status_code == 200, f"Turn 4 failed: {t4_res.text}"
    t4 = t4_res.json()
    assert t4.get("conversation_id") == conv_id
    assert len(t4["assistant_message"]["content"]) > 10
    assert t4["status"] == "success"

    # 5. Turn 5: Conversational inquiry about datasets
    t5_res = client.post("/api/chat", json={"query": "What datasets did you use?", "conversation_id": conv_id}, headers=AUTH_HEADERS)
    assert t5_res.status_code == 200, f"Turn 5 failed: {t5_res.text}"
    t5 = t5_res.json()
    assert t5.get("conversation_id") == conv_id
    assert len(t5["assistant_message"]["content"]) > 10
    assert t5["status"] == "success"
    content_t5 = t5["assistant_message"]["content"].lower()
    assert any(k in content_t5 for k in ["sentinel", "imagery", "satellite", "dataset", "data", "model", "prithvi"])

    # 6. Turn 6: Conversational explanation for beginner
    t6_res = client.post("/api/chat", json={"query": "Explain that result like I'm a beginner.", "conversation_id": conv_id}, headers=AUTH_HEADERS)
    assert t6_res.status_code == 200, f"Turn 6 failed: {t6_res.text}"
    t6 = t6_res.json()
    assert t6.get("conversation_id") == conv_id
    assert len(t6["assistant_message"]["content"]) > 10
    assert t6["status"] == "success"

    # Verify all 12 messages (6 user, 6 assistant) are preserved in database
    db = SessionLocal()
    try:
        msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at.asc()).all()
        assert len(msgs) == 12, f"Expected 12 messages in conversation {conv_id}, found {len(msgs)}"
        assert msgs[0].role == "user" and "Delhi" in msgs[0].content
        assert msgs[1].role == "assistant"
        assert msgs[2].role == "user" and "southern" in msgs[2].content
        assert msgs[4].role == "user" and "urban" in msgs[4].content
        assert msgs[6].role == "user" and "globe" in msgs[6].content
        assert msgs[8].role == "user" and "datasets" in msgs[8].content
        assert msgs[10].role == "user" and "beginner" in msgs[10].content
    finally:
        db.close()


def test_new_topic_does_not_repeat_previous_analysis():
    """
    Test 2: New topic must not reuse prior analysis results:
    1. 'Analyze vegetation in Delhi.'
    2. 'Now analyze flood risk in Mumbai.'
    """
    # Turn 1: Delhi
    t1_res = client.post("/api/chat", json={"query": "Analyze vegetation in Delhi."}, headers=AUTH_HEADERS)
    assert t1_res.status_code == 200
    t1 = t1_res.json()
    conv_id = t1["conversation_id"]

    # Turn 2: Mumbai flood risk
    t2_res = client.post("/api/chat", json={"query": "Now analyze flood risk in Mumbai.", "conversation_id": conv_id}, headers=AUTH_HEADERS)
    assert t2_res.status_code == 200
    t2 = t2_res.json()
    assert t2["conversation_id"] == conv_id

    # The result MUST be about Mumbai, NOT Delhi!
    content = t2["assistant_message"]["content"].lower()
    res_json = t2.get("result") or {}
    aoi_name = (res_json.get("aoi", {}).get("name") or "").lower()

    assert "mumbai" in content or "mumbai" in aoi_name, "New topic Mumbai was lost to previous Delhi analysis!"
    # Ensure it is not returning Delhi vegetation
    if "delhi" in content:
        assert "mumbai" in content


def test_out_of_scope_query():
    """
    Test 5: Out of scope queries (e.g. Mars) must return polite limitation without crashing or returning Delhi.
    """
    res = client.post("/api/chat", json={"query": "What is the population of Mars?"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["unsupported", "success"]
    content = data["assistant_message"]["content"]
    assert "earth observation" in content.lower() or "mars" in content.lower()
    assert "delhi" not in content.lower()


def test_history_restoration_and_continuation():
    """
    Test 6: Reopening an old conversation allows continuing chat without reset.
    """
    # Create conversation
    t1_res = client.post("/api/chat", json={"query": "Analyze vegetation in Delhi."}, headers=AUTH_HEADERS)
    conv_id = t1_res.json()["conversation_id"]

    # Fetch conversation details
    detail_res = client.get(f"/api/conversations/{conv_id}", headers=AUTH_HEADERS)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["messages"]) == 2

    # Send third message continuing conversation
    t2_res = client.post("/api/chat", json={"query": "What datasets did you use?", "conversation_id": conv_id}, headers=AUTH_HEADERS)
    assert t2_res.status_code == 200
    assert t2_res.json()["conversation_id"] == conv_id

    # Verify conversation now has 4 messages
    detail_after = client.get(f"/api/conversations/{conv_id}", headers=AUTH_HEADERS).json()
    assert len(detail_after["messages"]) == 4
