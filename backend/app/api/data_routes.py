"""
SatQuery AI — Data Assets API Routes
User-owned satellite raster ingestion and inspection layer.
Files stored under app_data/users/<clerk_user_id>/assets/<asset_id>/
PostgreSQL/SQLite is authoritative for asset ownership and profiles.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.data.inspector import DataInspector
from app.data.relationships import DataRelationshipAnalyzer
from app.schemas.data_asset import (
    AssetRelationship,
    DataAsset,
    DataProfile,
    UploadAssetResponse,
)
from app.db.session import get_db
from app.db.models import User, DataAssetRecord
from app.api.auth import get_current_user

data_router = APIRouter(prefix="/api/data", tags=["data"])

# Storage root for user uploaded assets
APP_USERS_DATA_DIR = Path(__file__).resolve().parents[2] / "app_data" / "users"
APP_USERS_DATA_DIR.mkdir(parents=True, exist_ok=True)

# In-memory fast-lookup index (mirrored from database)
_ASSET_CATALOG: Dict[str, DataAsset] = {}


def _record_to_asset(rec: DataAssetRecord) -> DataAsset:
    profile = DataProfile.model_validate(rec.profile_json)
    return DataAsset(
        asset_id=rec.id,
        filename=rec.filename,
        file_path=rec.file_path,
        file_size_bytes=rec.file_size_bytes,
        preview_url=rec.preview_url or f"/api/data/assets/{rec.id}/preview",
        thumbnail_url=rec.thumbnail_url or f"/api/data/assets/{rec.id}/thumbnail",
        created_at=rec.created_at.isoformat() if hasattr(rec.created_at, "isoformat") else str(rec.created_at),
        profile=profile,
    )


class LocalPathUploadRequest(BaseModel):
    local_path: str
    filename: Optional[str] = None


@data_router.post("/upload")
async def upload_asset(
    request: Request,
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dual-mode ingest:
    1. Tauri desktop: receives JSON payload with `local_path`
    2. Web browser: receives standard multipart `file` stream
    Stores file securely in user-scoped directory and registers in database.
    """
    asset_id = f"asset_{uuid.uuid4().hex[:10]}"
    user_storage_dir = APP_USERS_DATA_DIR / current_user.clerk_user_id / "assets" / asset_id
    user_storage_dir.mkdir(parents=True, exist_ok=True)

    dest_file = user_storage_dir / "original.tif"
    source_filename = "data.tif"
    file_size = 0

    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        # Native Tauri path mode
        body = await request.json()
        local_path_str = body.get("local_path")
        if not local_path_str:
            raise HTTPException(status_code=400, detail="Missing local_path in request body")
        src_path = Path(local_path_str)
        if not src_path.exists():
            raise HTTPException(status_code=404, detail=f"Local file not found: {local_path_str}")

        source_filename = body.get("filename") or src_path.name
        file_size = src_path.stat().st_size

        # Copy into user's controlled app storage
        shutil.copy2(str(src_path), str(dest_file))
    elif file is not None:
        # Browser multipart upload mode
        source_filename = file.filename or "upload.tif"
        with open(dest_file, "wb") as f_out:
            while chunk := await file.read(1024 * 1024):
                f_out.write(chunk)
        file_size = dest_file.stat().st_size
    else:
        raise HTTPException(status_code=400, detail="No file or local_path provided")

    # Run deterministic raster inspection
    try:
        profile, preview_url, thumb_url = DataInspector.inspect(
            file_path=str(dest_file),
            asset_id=asset_id,
            output_dir=str(user_storage_dir),
        )
    except Exception as exc:
        shutil.rmtree(user_storage_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"Corrupted or unsupported raster file: {exc}")

    now = datetime.utcnow()

    # Save profile to user folder
    with open(user_storage_dir / "profile.json", "w") as f:
        json.dump(profile.model_dump(), f, indent=2)

    # Persist in Database
    rec = DataAssetRecord(
        id=asset_id,
        user_id=current_user.id,
        filename=source_filename,
        file_path=str(dest_file),
        file_size_bytes=file_size,
        preview_url=preview_url,
        thumbnail_url=thumb_url,
        created_at=now,
        profile_json=profile.model_dump(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    asset = _record_to_asset(rec)
    _ASSET_CATALOG[asset_id] = asset

    return UploadAssetResponse(
        asset_id=asset_id,
        profile=profile,
        preview_url=preview_url,
        thumbnail_url=thumb_url,
        message=f"Dataset {source_filename} inspected and registered successfully.",
    )


@data_router.get("/assets", response_model=List[DataAsset])
async def list_assets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists only data assets owned by the authenticated user."""
    records = (
        db.query(DataAssetRecord)
        .filter(DataAssetRecord.user_id == current_user.id)
        .order_by(DataAssetRecord.created_at.desc())
        .all()
    )
    assets = [_record_to_asset(r) for r in records]
    for a in assets:
        _ASSET_CATALOG[a.asset_id] = a
    return assets


@data_router.get("/assets/{asset_id}", response_model=DataAsset)
async def get_asset(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetches details and DataProfile for a user's asset with ownership validation."""
    rec = (
        db.query(DataAssetRecord)
        .filter(DataAssetRecord.id == asset_id, DataAssetRecord.user_id == current_user.id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset = _record_to_asset(rec)
    _ASSET_CATALOG[asset_id] = asset
    return asset


@data_router.get("/assets/{asset_id}/preview")
async def get_asset_preview(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serves the generated downsampled preview PNG for an authorized asset."""
    rec = (
        db.query(DataAssetRecord)
        .filter(DataAssetRecord.id == asset_id, DataAssetRecord.user_id == current_user.id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Asset not found")

    user_storage_dir = APP_USERS_DATA_DIR / current_user.clerk_user_id / "assets" / asset_id
    preview_file = user_storage_dir / "preview.png"
    if not preview_file.exists():
        raise HTTPException(status_code=404, detail="Preview image not found")
    return FileResponse(str(preview_file), media_type="image/png")


@data_router.get("/assets/{asset_id}/thumbnail")
async def get_asset_thumbnail(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serves the generated thumbnail PNG for an authorized asset."""
    rec = (
        db.query(DataAssetRecord)
        .filter(DataAssetRecord.id == asset_id, DataAssetRecord.user_id == current_user.id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Asset not found")

    user_storage_dir = APP_USERS_DATA_DIR / current_user.clerk_user_id / "assets" / asset_id
    thumb_file = user_storage_dir / "thumbnail.png"
    if not thumb_file.exists():
        raise HTTPException(status_code=404, detail="Thumbnail image not found")
    return FileResponse(str(thumb_file), media_type="image/png")


@data_router.delete("/assets/{asset_id}")
async def delete_asset(
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes an asset from database and user storage."""
    rec = (
        db.query(DataAssetRecord)
        .filter(DataAssetRecord.id == asset_id, DataAssetRecord.user_id == current_user.id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Asset not found")

    db.delete(rec)
    db.commit()

    _ASSET_CATALOG.pop(asset_id, None)

    user_storage_dir = APP_USERS_DATA_DIR / current_user.clerk_user_id / "assets" / asset_id
    shutil.rmtree(user_storage_dir, ignore_errors=True)
    return {"status": "success", "message": f"Asset {asset_id} deleted."}


@data_router.post("/relationships", response_model=AssetRelationship)
async def evaluate_relationship(
    asset_a_id: str,
    asset_b_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evaluates compatibility between two assets owned by current user."""
    rec_a = (
        db.query(DataAssetRecord)
        .filter(DataAssetRecord.id == asset_a_id, DataAssetRecord.user_id == current_user.id)
        .first()
    )
    rec_b = (
        db.query(DataAssetRecord)
        .filter(DataAssetRecord.id == asset_b_id, DataAssetRecord.user_id == current_user.id)
        .first()
    )
    if not rec_a or not rec_b:
        raise HTTPException(status_code=404, detail="One or both assets not found in your catalog")

    prof_a = DataProfile.model_validate(rec_a.profile_json)
    prof_b = DataProfile.model_validate(rec_b.profile_json)

    return DataRelationshipAnalyzer.analyze(prof_a, prof_b)
