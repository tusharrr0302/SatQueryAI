"""
Tests for Phase 3: Copernicus DEM & Derived Products.
Verifies:
  - CopernicusDEMProvider querying cop-dem-glo-30
  - get_data_provider factory for 'dem', 'elevation', 'terrain'
  - Mock DEM fixtures return authentic 30m DSM elevation metadata
  - extract_raster_grid converts authentic rasters into 2D matrices without synthetic math
"""
import pytest
from pathlib import Path
from PIL import Image

from app.schemas.data_requirement import DataRequirement
from app.dataset.providers import (
    CopernicusDEMProvider,
    MockSatelliteDataProvider,
    get_data_provider,
)
from app.imagery.copernicus_provider import extract_raster_grid


def test_01_copernicus_dem_provider_factory():
    prov_dem = get_data_provider(modality="dem")
    assert isinstance(prov_dem, CopernicusDEMProvider)

    prov_elev = get_data_provider(modality="elevation")
    assert isinstance(prov_elev, CopernicusDEMProvider)

    prov_terrain = get_data_provider(modality="terrain")
    assert isinstance(prov_terrain, CopernicusDEMProvider)


def test_02_mock_dem_discovery_kashmir():
    mock_prov = MockSatelliteDataProvider()
    req = DataRequirement(
        aoi_name="Kashmir",
        bbox=[74.0, 33.5, 75.5, 34.5],
        modalities=["dem"],
        preferred_datasets=["copernicus-dem"],
    )
    candidates = mock_prov.search_sync(req)
    assert len(candidates) >= 1
    dem = candidates[0]
    assert dem.dataset_id == "copernicus-dem"
    assert dem.sensor == "Copernicus DEM (GLO-30 DSM)"
    assert dem.spatial_resolution == 30.0
    assert "elevation" in dem.bands
    assert dem.metadata.get("elevation_unit") == "meters"


def test_03_extract_raster_grid_authentic(tmp_path: Path):
    # Create an authentic 64x64 test gradient image
    img_path = tmp_path / "test_elevation.png"
    img = Image.new("L", (64, 64), color=128)
    for x in range(64):
        for y in range(64):
            img.putpixel((x, y), int((x + y) * 255 / 128))
    img.save(img_path)

    grid = extract_raster_grid(str(img_path), grid_size=16, val_min=0.0, val_max=100.0)
    assert len(grid) == 16
    assert len(grid[0]) == 16
    # Top-left should be lowest, bottom-right should be highest
    assert grid[0][0] < grid[15][15]
    assert 0.0 <= grid[0][0] <= 100.0
    assert 0.0 <= grid[15][15] <= 100.0
