"""
Tests for Phase 2: Deterministic Temporal Observation Pipeline.
Verifies:
  - Multi-year temporal window generation (e.g. 10 years, 2016-2026 -> 11 annual observation windows)
  - Missing temporal periods marked as status='unavailable' with deterministic scientific reasons
  - Transparent execution with remaining valid observations (no synthetic interpolation)
  - Insufficient observations handling (< 2 observations -> honest warning, no fabricated trend)
"""
import pytest
import datetime
from app.schemas.analysis_request import (
    AnalysisRequest,
    Intent,
    AOI,
    DataRequirements,
    ModelSelection,
    Analysis,
    Outputs,
    Execution,
    TemporalScope,
)
from app.schemas.data_asset import DataAsset
from app.schemas.data_requirement import (
    DataRequirement,
    TemporalWindow,
    TemporalObservationRecord,
)
from app.dataset.data_requirement_mapper import map_analysis_request_to_requirement
from app.dataset.asset_selector import select_temporal_series, select_temporal_assets
from app.dataset.discovery_service import SatelliteDataDiscoveryService
from app.dataset.providers import MockSatelliteDataProvider


def test_01_multi_year_10_year_annual_windows():
    """Verifies that a 10-year query constructs 11 distinct annual temporal slots."""
    ar = AnalysisRequest(
        query="How has vegetation changed in Kashmir from 2016 to 2026?",
        intent=Intent(
            primary_task="vegetation_analysis",
            temporal_scope=TemporalScope(start="2016", end="2026"),
            question_type="new_analysis",
        ),
        aoi=AOI(name="Kashmir", bbox=[74.0, 33.5, 75.5, 34.5]),
        data_requirements=DataRequirements(modalities=["optical"]),
        model_selection=ModelSelection(model="earthdial-4b-ms", reason="Vegetation trend"),
        analysis=Analysis(operation="vegetation_monitoring"),
        outputs=Outputs(),
        execution=Execution(),
    )
    req = map_analysis_request_to_requirement(ar)
    assert req.acquisition_strategy == "temporal"
    assert req.temporal_frequency == "annual"
    assert req.temporal_count == 11
    assert len(req.temporal_windows) == 11
    slots = [w.slot for w in req.temporal_windows]
    expected = [str(y) for y in range(2016, 2027)]
    assert slots == expected
    # Each slot targets the peak vegetative window
    assert req.temporal_windows[0].target_date == "2016-07-15"
    assert req.temporal_windows[-1].target_date == "2026-07-15"


def test_02_missing_temporal_slot_honesty():
    """
    Verifies that if an observation is missing for a year (e.g. 2018 missing in 2016-2020),
    the system does NOT fabricate it, marks it status='unavailable' with a clear reason,
    and returns valid observations for the remaining years.
    """
    req = DataRequirement(
        aoi_name="Kashmir",
        bbox=[74.0, 33.5, 75.5, 34.5],
        temporal={"start": "2016-01-01", "end": "2020-12-31"},
        modalities=["optical"],
        cloud_cover_max=20.0,
        temporal_frequency="annual",
        temporal_count=5,
        temporal_windows=[
            TemporalWindow(slot="2016", start="2016-01-01", end="2016-12-31", target_date="2016-07-15", label="2016"),
            TemporalWindow(slot="2017", start="2017-01-01", end="2017-12-31", target_date="2017-07-15", label="2017"),
            TemporalWindow(slot="2018", start="2018-01-01", end="2018-12-31", target_date="2018-07-15", label="2018"),
            TemporalWindow(slot="2019", start="2019-01-01", end="2019-12-31", target_date="2019-07-15", label="2019"),
            TemporalWindow(slot="2020", start="2020-01-01", end="2020-12-31", target_date="2020-07-15", label="2020"),
        ],
    )

    # Candidates for 2016, 2017, 2019, 2020 (2018 completely missing)
    candidates = [
        DataAsset(asset_id="S2_2016", id="S2_2016", dataset_id="sentinel-2", acquisition_time="2016-07-12T05:30:00Z", cloud_cover=5.0, bbox=[74.0, 33.5, 75.5, 34.5], bands=["B02", "B03", "B04", "B08"]),
        DataAsset(asset_id="S2_2017", id="S2_2017", dataset_id="sentinel-2", acquisition_time="2017-07-18T05:30:00Z", cloud_cover=8.0, bbox=[74.0, 33.5, 75.5, 34.5], bands=["B02", "B03", "B04", "B08"]),
        # 2018 missing!
        DataAsset(asset_id="S2_2019", id="S2_2019", dataset_id="sentinel-2", acquisition_time="2019-08-02T05:30:00Z", cloud_cover=12.0, bbox=[74.0, 33.5, 75.5, 34.5], bands=["B02", "B03", "B04", "B08"]),
        DataAsset(asset_id="S2_2020", id="S2_2020", dataset_id="sentinel-2", acquisition_time="2020-06-25T05:30:00Z", cloud_cover=4.0, bbox=[74.0, 33.5, 75.5, 34.5], bands=["B02", "B03", "B04", "B08"]),
    ]

    selected_slots, missing_slots, obs_records = select_temporal_series(candidates, req)

    assert "2018" in missing_slots
    assert len(selected_slots) == 4
    assert set(selected_slots.keys()) == {"2016", "2017", "2019", "2020"}

    # Inspect 2018 observation record
    obs_2018 = next((o for o in obs_records if o.slot == "2018"), None)
    assert obs_2018 is not None
    assert obs_2018.status == "unavailable"
    assert obs_2018.reason == "NO_VALID_SCENE"
    assert "No observation found" in obs_2018.explanation
    assert obs_2018.selected is False

    # Inspect 2016 observation record
    obs_2016 = next((o for o in obs_records if o.slot == "2016"), None)
    assert obs_2016 is not None
    assert obs_2016.status == "ready"
    assert obs_2016.asset_id == "S2_2016"
    assert obs_2016.cloud_cover == 5.0
    assert obs_2016.selected is True


def test_03_cloud_filtering_failure_classification():
    """Verifies that scenes rejected solely due to cloud threshold report CLOUD_THRESHOLD_FAILED."""
    req = DataRequirement(
        aoi_name="Kashmir",
        bbox=[74.0, 33.5, 75.5, 34.5],
        temporal={"start": "2018-01-01", "end": "2018-12-31"},
        modalities=["optical"],
        cloud_cover_max=10.0,  # Strict 10% threshold
        temporal_windows=[
            TemporalWindow(slot="2018", start="2018-01-01", end="2018-12-31", target_date="2018-07-15", label="2018"),
        ],
    )
    # Candidate exists in 2018, but has 45% cloud cover
    candidates = [
        DataAsset(asset_id="S2_2018_cloudy", id="S2_2018_cloudy", dataset_id="sentinel-2", acquisition_time="2018-07-15T05:30:00Z", cloud_cover=45.0, bbox=[74.0, 33.5, 75.5, 34.5], bands=["B02", "B03", "B04", "B08"]),
    ]

    selected_slots, missing_slots, obs_records = select_temporal_series(candidates, req)
    assert "2018" in missing_slots
    assert len(selected_slots) == 0

    obs_2018 = obs_records[0]
    assert obs_2018.status == "unavailable"
    assert obs_2018.reason == "CLOUD_THRESHOLD_FAILED"
    assert "exceeded cloud cover threshold" in obs_2018.explanation


def test_04_insufficient_observations_no_fabricated_trend():
    """
    Verifies that if fewer than 2 valid observations exist across a multi-temporal query,
    discovery returns status='needs_data' with an explicit message refusing to claim a trend.
    """
    svc = SatelliteDataDiscoveryService()
    ar = AnalysisRequest(
        query="How has vegetation changed in Kashmir over the last 5 years?",
        intent=Intent(
            primary_task="vegetation_analysis",
            temporal_scope=TemporalScope(start="2020", end="2025"),
            question_type="new_analysis",
        ),
        aoi=AOI(name="Kashmir", bbox=[74.0, 33.5, 75.5, 34.5]),
        data_requirements=DataRequirements(modalities=["optical"]),
        model_selection=ModelSelection(model="earthdial-4b-ms", reason="Vegetation trend"),
        analysis=Analysis(operation="vegetation_monitoring"),
        outputs=Outputs(),
        execution=Execution(),
    )

    # Candidate with only 1 valid observation across the whole 5 years
    single_candidate = [
        DataAsset(asset_id="S2_2024", id="S2_2024", dataset_id="sentinel-2", acquisition_time="2024-07-10T05:30:00Z", cloud_cover=4.0, bbox=[74.0, 33.5, 75.5, 34.5], bands=["B02", "B03", "B04", "B08"]),
    ]

    class SingleAssetProvider(MockSatelliteDataProvider):
        def search_sync(self, req):
            return single_candidate

    custom_svc = SatelliteDataDiscoveryService(provider=SingleAssetProvider())
    res = custom_svc.discover_data_sync(ar)

    assert res.status == "needs_data"
    assert "Insufficient valid observations (1) to establish a temporal trend" in res.message
    assert len(res.temporal_observations) >= 5
