import pytest
from app.services.visualization_registry import (
    SCIENTIFIC_VISUALIZATION_TAXONOMY,
    validate_visualization_capability,
    generate_visualization_explanation,
    plan_visualizations,
)
from app.schemas.normalized_result import NormalizedResult


def test_scientific_visualization_taxonomy_completeness():
    """Verify that all 27 controlled visualization types are defined with complete specifications."""
    assert len(SCIENTIFIC_VISUALIZATION_TAXONOMY) == 27
    
    for vis_id, spec in SCIENTIFIC_VISUALIZATION_TAXONOMY.items():
        assert "id" in spec
        assert "title" in spec
        assert "category" in spec
        assert spec["category"] in ["2d_scientific", "temporal", "spatial", "3d"]
        assert "explanation" in spec
        expl = spec["explanation"]
        assert "title" in expl
        assert "what_it_shows" in expl
        assert "data_source" in expl
        assert "variables" in expl
        assert "how_to_read" in expl
        assert "why_it_matters" in expl
        assert "limitations" in expl


def test_validate_visualization_capability_rules():
    """Verify data requirement validation rules prevent hallucinated visualizations."""
    # S2 NDVI requires sentinel-2-l2a
    avail, reason = validate_visualization_capability(
        "ndvi_map",
        available_datasets=["sentinel-1-grd"],
    )
    assert not avail
    assert reason == "MISSING_REQUIRED_DATA"

    # S2 NDVI with sentinel-2-l2a available
    avail, reason = validate_visualization_capability(
        "ndvi_map",
        available_datasets=["sentinel-2-l2a"],
    )
    assert avail
    assert reason is None

    # Temporal chart requires temporal series
    avail, reason = validate_visualization_capability(
        "temporal_line_chart",
        available_datasets=["sentinel-2-l2a"],
        has_temporal_series=False,
    )
    assert not avail
    assert reason == "MISSING_TEMPORAL_SLOT"

    avail, reason = validate_visualization_capability(
        "temporal_line_chart",
        available_datasets=["sentinel-2-l2a"],
        has_temporal_series=True,
    )
    assert avail
    assert reason is None


def test_generate_visualization_explanation_canonical_fields():
    """Verify that deterministic explanations produce all 7 canonical factual fields."""
    expl = generate_visualization_explanation(
        vis_id="3d_terrain_surface",
        data_source="Copernicus DEM GLO-30 (Planetary Computer)",
        observation_date="2024-01-01",
        resolution_m=30.0,
    )
    assert "3D" in expl.title and "Surface" in expl.title

    assert "Digital Surface Model" in expl.what_it_shows or "elevation" in expl.what_it_shows.lower()
    assert expl.data_source == "Copernicus DEM GLO-30 (Planetary Computer)"
    assert len(expl.variables) > 0
    assert len(expl.how_to_read) > 0
    assert len(expl.why_it_matters) > 0
    assert len(expl.limitations) > 0


def test_plan_visualizations_explanation_and_validation():
    """Verify plan_visualizations returns fully populated 7-field explanation and capability validation."""
    norm = {
        "aoi": {"name": "Srinagar Kashmir", "center": {"latitude": 34.0837, "longitude": 74.7973}},
        "provenance": {
            "dataset_ids": ["sentinel-2-l2a"],
            "model_name": "Prithvi-EO-2.0",
            "acquisition_dates": "2016-2026",
        },
        "metrics": [{"label": "NDVI Mean", "value": 0.65}],
        "time_series": [{"date": "2020-07-15", "value": 0.62}, {"date": "2024-07-15", "value": 0.65}],
        "key_finding": "Vegetation index indicates stable canopy across Srinagar valley.",
    }

    plan = plan_visualizations(norm, query="Vegetation trend over time in Kashmir")
    assert plan.explanation is not None
    assert plan.explanation.title is not None
    assert plan.explanation.what_it_shows is not None
    assert plan.explanation.data_source is not None
    assert plan.explanation.how_to_read is not None
    assert plan.explanation.why_it_matters is not None
    assert plan.explanation.limitations is not None

    # Primary and secondary visualizations must have available flag
    assert "available" in plan.primary_visualization
    assert plan.primary_visualization["available"] is True
