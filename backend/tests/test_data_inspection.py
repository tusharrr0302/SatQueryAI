import tempfile
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
from fastapi.testclient import TestClient

from app.main import app
from app.data.inspector import DataInspector
from app.data.profile import DataProfileGenerator
from app.data.relationships import DataRelationshipAnalyzer
from app.schemas.data_asset import Dimensions

client = TestClient(app)


def _create_sample_geotiff(path: str, bands: int = 4, crs: str = "EPSG:32643"):
    transform = from_origin(700000, 3100000, 10, 10)
    data = np.ones((bands, 64, 64), dtype=np.uint16) * 1000
    # Simulate NIR reflection for band 4
    if bands >= 4:
        data[3, :, :] = 3500

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=64,
        width=64,
        count=bands,
        dtype="uint16",
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(data)


def test_deterministic_raster_inspector():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tif_path = Path(tmp_dir) / "sample_sentinel2.tif"
        out_dir = Path(tmp_dir) / "output"
        _create_sample_geotiff(str(tif_path), bands=13)

        profile, preview_url, thumb_url = DataInspector.inspect(
            str(tif_path),
            "asset_test123",
            str(out_dir),
        )

        assert profile.dimensions.bands == 13
        assert profile.dimensions.width == 64
        assert profile.dimensions.height == 64
        assert profile.format == "GeoTIFF"
        assert profile.crs == "EPSG:32643"
        assert len(profile.bands) == 13
        # Check that preview and thumbnail files were created
        assert (out_dir / "preview.png").exists()
        assert (out_dir / "thumbnail.png").exists()


def test_data_relationships_temporal_and_multimodal():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tif_a = Path(tmp_dir) / "s2_2020.tif"
        tif_b = Path(tmp_dir) / "s2_2024.tif"
        _create_sample_geotiff(str(tif_a), bands=4)
        _create_sample_geotiff(str(tif_b), bands=4)

        prof_a, _, _ = DataInspector.inspect(str(tif_a), "asset_a", str(Path(tmp_dir) / "out_a"))
        prof_b, _, _ = DataInspector.inspect(str(tif_b), "asset_b", str(Path(tmp_dir) / "out_b"))

        rel = DataRelationshipAnalyzer.analyze(prof_a, prof_b)
        assert rel.compatible is True
        assert rel.relationship_type == "temporal_pair"
        assert len(rel.possible_analyses) > 0


def test_upload_api_local_path():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tif_path = Path(tmp_dir) / "desktop_satellite_image.tif"
        _create_sample_geotiff(str(tif_path), bands=4)

        auth_headers = {"Authorization": "Bearer test_token_inspector"}
        res = client.post(
            "/api/data/upload",
            json={"local_path": str(tif_path), "filename": "desktop_satellite_image.tif"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["asset_id"].startswith("asset_")
        assert data["profile"]["dimensions"]["bands"] == 4
        assert "preview_url" in data

        # Check list endpoint
        list_res = client.get("/api/data/assets", headers=auth_headers)
        assert list_res.status_code == 200
        assets = list_res.json()
        assert any(a["asset_id"] == data["asset_id"] for a in assets)
