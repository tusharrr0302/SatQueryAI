import os
import uuid
import pytest
import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.db.session import SessionLocal
from app.db.models import User, Conversation, Message, DataAssetRecord, InvestigationRecord
from app.api.websocket import ws_manager

client = TestClient(app)

ALICE_TOKEN = "test_token_alice"
BOB_TOKEN = "test_token_bob"

ALICE_HEADERS = {"Authorization": f"Bearer {ALICE_TOKEN}"}
BOB_HEADERS = {"Authorization": f"Bearer {BOB_TOKEN}"}


@pytest.fixture(autouse=True)
def clean_db():
    db = SessionLocal()
    try:
        # Clean up test users
        users = db.query(User).filter(User.clerk_user_id.in_(["user_alice", "user_bob"])).all()
        for u in users:
            db.delete(u)
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.clerk_user_id.in_(["user_alice", "user_bob"])).all()
        for u in users:
            db.delete(u)
        db.commit()
    finally:
        db.close()


def test_unauthenticated_request_rejected():
    """Verify 401 Unauthorized when auth token is missing across all endpoints."""
    endpoints = [
        "/api/conversations",
        "/api/investigations",
        "/api/data/assets",
        "/api/datasets",
        "/api/models",
        "/api/aoi",
        "/api/settings",
        "/api/agent/tools",
    ]
    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 401, f"Expected 401 for {ep}, got {res.status_code}"


def test_invalid_token_rejected():
    """Verify 401 Unauthorized when an invalid Bearer token is provided."""
    orig_key = settings.CLERK_SECRET_KEY
    settings.CLERK_SECRET_KEY = "sk_test_mock_secret_key"
    try:
        res = client.get("/api/conversations", headers={"Authorization": "Bearer invalid_garbage_token"})
        assert res.status_code == 401
    finally:
        settings.CLERK_SECRET_KEY = orig_key


def test_user_identity_resolution():
    """Verify test tokens resolve to distinct User records in database."""
    res_alice = client.get("/api/conversations", headers=ALICE_HEADERS)
    assert res_alice.status_code == 200

    res_bob = client.get("/api/conversations", headers=BOB_HEADERS)
    assert res_bob.status_code == 200

    db = SessionLocal()
    try:
        alice = db.query(User).filter(User.clerk_user_id == "user_alice").first()
        bob = db.query(User).filter(User.clerk_user_id == "user_bob").first()
        assert alice is not None
        assert bob is not None
        assert alice.id != bob.id
    finally:
        db.close()


def test_conversation_ownership_isolation():
    """Verify Alice's conversation cannot be read or deleted by Bob."""
    # Create conversation for Alice directly in DB
    db = SessionLocal()
    alice = client.get("/api/conversations", headers=ALICE_HEADERS) # Ensure user exists
    user_alice = db.query(User).filter(User.clerk_user_id == "user_alice").first()
    
    conv_id = f"conv_alice_{uuid.uuid4().hex[:6]}"
    alice_conv = Conversation(
        id=conv_id,
        user_id=user_alice.id,
        title="Alice Private AOI Analysis",
    )
    alice_msg = Message(
        id=f"msg_{uuid.uuid4().hex[:6]}",
        conversation_id=conv_id,
        user_id=user_alice.id,
        role="user",
        content="Analyze private crop field",
    )
    db.add(alice_conv)
    db.add(alice_msg)
    db.commit()
    db.close()

    # Alice can view conversation
    alice_list = client.get("/api/conversations", headers=ALICE_HEADERS).json()
    assert any(c["id"] == conv_id for c in alice_list["conversations"])

    alice_detail = client.get(f"/api/conversations/{conv_id}", headers=ALICE_HEADERS)
    assert alice_detail.status_code == 200
    assert alice_detail.json()["title"] == "Alice Private AOI Analysis"

    # Bob CANNOT see Alice's conversation in list
    bob_list = client.get("/api/conversations", headers=BOB_HEADERS).json()
    assert not any(c["id"] == conv_id for c in bob_list["conversations"])

    # Bob CANNOT get Alice's conversation
    bob_detail = client.get(f"/api/conversations/{conv_id}", headers=BOB_HEADERS)
    assert bob_detail.status_code == 404

    # Bob CANNOT delete Alice's conversation
    bob_delete = client.delete(f"/api/conversations/{conv_id}", headers=BOB_HEADERS)
    assert bob_delete.status_code == 404

    # Alice deletes her own conversation
    alice_delete = client.delete(f"/api/conversations/{conv_id}", headers=ALICE_HEADERS)
    assert alice_delete.status_code == 200


def test_investigation_ownership_isolation():
    """Verify Alice's saved investigations cannot be seen or deleted by Bob."""
    # Alice creates an investigation
    inv_payload = {
        "name": "Alice Secret Study",
        "query": "Study border glacier retreat",
        "location": "Alps",
        "datasets": ["sentinel-2"],
        "analysis_type": "cryosphere",
        "summary": "Glacier area loss 12%",
    }
    save_res = client.post("/api/investigations", json=inv_payload, headers=ALICE_HEADERS)
    assert save_res.status_code == 200
    inv_id = save_res.json()["investigation"]["id"]

    # Alice sees it
    alice_invs = client.get("/api/investigations", headers=ALICE_HEADERS).json()
    assert any(inv["id"] == inv_id for inv in alice_invs["investigations"])

    # Bob does not see it
    bob_invs = client.get("/api/investigations", headers=BOB_HEADERS).json()
    assert not any(inv["id"] == inv_id for inv in bob_invs["investigations"])

    # Bob cannot fetch it
    bob_get = client.get(f"/api/investigations/{inv_id}", headers=BOB_HEADERS)
    assert bob_get.status_code == 404

    # Bob cannot delete it
    bob_del = client.delete(f"/api/investigations/{inv_id}", headers=BOB_HEADERS)
    assert bob_del.status_code == 404

    # Alice can delete it
    alice_del = client.delete(f"/api/investigations/{inv_id}", headers=ALICE_HEADERS)
    assert alice_del.status_code == 200


def test_data_asset_ownership_isolation():
    """Verify user-uploaded GeoTIFF data assets are strictly isolated between users."""
    # Alice creates a synthetic asset
    db = SessionLocal()
    client.get("/api/conversations", headers=ALICE_HEADERS)
    user_alice = db.query(User).filter(User.clerk_user_id == "user_alice").first()

    asset_id = f"asset_alice_{uuid.uuid4().hex[:6]}"
    asset = DataAssetRecord(
        id=asset_id,
        user_id=user_alice.id,
        filename="alice_drone_ortho.tif",
        file_path=f"app_data/users/user_alice/assets/{asset_id}/alice_drone_ortho.tif",
        file_size_bytes=10240,
        profile_json={
            "asset_id": asset_id,
            "filename": "alice_drone_ortho.tif",
            "format": "GeoTIFF",
            "dimensions": {"width": 512, "height": 512, "bands": 3},
            "dtype": "uint8",
            "bands": [
                {"index": 1, "name": "Red"},
                {"index": 2, "name": "Green"},
                {"index": 3, "name": "Blue"}
            ],
        },
    )
    db.add(asset)
    db.commit()
    db.close()

    # Alice sees it
    alice_assets = client.get("/api/data/assets", headers=ALICE_HEADERS).json()
    assert any(a["asset_id"] == asset_id for a in alice_assets)

    # Bob does not see it
    bob_assets = client.get("/api/data/assets", headers=BOB_HEADERS).json()
    assert not any(a["asset_id"] == asset_id for a in bob_assets)

    # Bob cannot fetch asset details
    bob_get = client.get(f"/api/data/assets/{asset_id}", headers=BOB_HEADERS)
    assert bob_get.status_code == 404

    # Bob cannot delete asset
    bob_del = client.delete(f"/api/data/assets/{asset_id}", headers=BOB_HEADERS)
    assert bob_del.status_code == 404

    # Alice can delete asset
    alice_del = client.delete(f"/api/data/assets/{asset_id}", headers=ALICE_HEADERS)
    assert alice_del.status_code == 200


def test_websocket_user_isolation():
    """Verify WebSocket broadcast_event respects user_id isolation."""
    # Test WebSocket connection with token
    with client.websocket_connect(f"/ws/chat?token={ALICE_TOKEN}") as ws_alice:
        # First message is connection acknowledgment
        init_alice = ws_alice.receive_json()
        assert init_alice.get("event") == "connected"

        with client.websocket_connect(f"/ws/chat?token={BOB_TOKEN}") as ws_bob:
            init_bob = ws_bob.receive_json()
            assert init_bob.get("event") == "connected"

            # Broadcast event targeted to Alice only
            asyncio.run(
                ws_manager.broadcast_event(
                    "test_alice_event",
                    {"secret": "alice_data"},
                    user_id="user_alice",
                )
            )

            # Alice receives it
            alice_event = ws_alice.receive_json()
            assert alice_event["event"] == "test_alice_event"
            assert alice_event["data"]["secret"] == "alice_data"
