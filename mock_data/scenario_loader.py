"""
SatQuery AI — Scenario Loader
Provides clean deterministic access to the mock scenario dataset.

NOTE:
- The dataset is for mock context, testing, evaluation, and demonstrations.
- Expected tools and scenarios are NEVER used for runtime agent routing.
- The LangGraph agent independently and dynamically selects tools via LLM reasoning.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


_SCENARIOS_PATH = Path(__file__).parent / "satquery_scenarios.json"
_FALLBACK_PATH = Path(__file__).parent / "satquery_mock_data.json"


@lru_cache(maxsize=1)
def _load_raw_dataset() -> Dict[str, Any]:
    """Load the raw scenarios dataset from satquery_scenarios.json (or fallback)."""
    if _SCENARIOS_PATH.exists():
        with open(_SCENARIOS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    elif _FALLBACK_PATH.exists():
        with open(_FALLBACK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scenarios": [], "metadata": {}}


_SUPPLEMENTAL_SCENARIOS = [
    {
        "id": "FLD-006",
        "category": "flood",
        "question": "Show the flooding caused by Storm Daniel in Derna",
        "location": "Derna, Libya",
        "bbox": [22.60, 32.74, 22.68, 32.79],
        "time_range": {"start": "2023-09-08", "end": "2023-09-15"},
        "expected_tools": ["fetch_sentinel1", "detect_water", "detect_change", "calculate_area"],
        "mock_data": {
            "satellite": "Sentinel-1 SAR",
            "inundation_area_km2": 4.6,
            "structures_impacted": 2140,
            "flood_depth_mean_m": 2.4,
            "sediment_plume_extent_km2": 18.2,
            "confidence": 0.95
        },
        "expected_answer": "Catastrophic flooding from Storm Daniel inundated approximately 4.6 km² of urban Derna, destroying two upstream dams on Wadi Derna. At least 2,140 structures were severely impacted, with average water depths reaching 2.4 m."
    },
    {
        "id": "URB-006",
        "category": "urban",
        "question": "Show me how Delhi changed over the last 10 years",
        "location": "Delhi NCR, India",
        "bbox": [76.84, 28.40, 77.34, 28.88],
        "time_range": {"start": "2016-01-01", "end": "2026-12-31"},
        "expected_tools": ["fetch_sentinel2", "fetch_landsat", "detect_change", "calculate_area"],
        "mock_data": {
            "satellite": "Sentinel-2 & Landsat-8",
            "urban_expansion_km2": 134.2,
            "growth_rate_percent": 21.4,
            "mean_annual_growth_km2": 13.4,
            "impervious_surface_ratio": 0.68,
            "confidence": 0.942
        },
        "expected_answer": "Between 2016 and 2026, Delhi NCR experienced 134.2 km² of net built-up expansion (+21.4%), primarily across the peripheral sectors of Gurugram, Noida, and Dwarka Expressway corridors."
    },
    {
        "id": "LULC-001",
        "category": "cross_domain",
        "question": "Compare water and built-up area",
        "location": "Bengaluru, Karnataka, India",
        "bbox": [77.4, 12.8, 77.8, 13.2],
        "time_range": {"start": "2020-01-01", "end": "2024-12-31"},
        "expected_tools": ["fetch_sentinel2", "calculate_ndbi", "detect_water", "calculate_area"],
        "mock_data": {
            "satellite": "Sentinel-2 & Landsat-8",
            "built_up_area_km2": 425.6,
            "vegetation_area_km2": 218.2,
            "water_body_area_km2": 38.4,
            "other_land_km2": 58.8,
            "confidence": 0.93
        },
        "expected_answer": "In the monitored Bengaluru region, built-up surfaces span 425.6 km² compared to 38.4 km² of water bodies and 218.2 km² of vegetation cover, demonstrating intense urban density relative to natural surface water reservoirs."
    }
]


def load_scenarios() -> List[Dict[str, Any]]:
    """Return all scenarios in the dataset including flagship scenarios."""
    scenarios = list(_load_raw_dataset().get("scenarios", []))
    existing_ids = {s.get("id") for s in scenarios}
    for supp in _SUPPLEMENTAL_SCENARIOS:
        if supp["id"] not in existing_ids:
            scenarios.append(supp)
    return scenarios


def get_dataset_metadata() -> Dict[str, Any]:
    """Return the dataset metadata/header."""
    data = _load_raw_dataset()
    return {
        "dataset_name": data.get("dataset_name", "SatQuery AI Prototype Mock Scenarios"),
        "version": data.get("version", "1.0"),
        "purpose": data.get("purpose", ""),
        "prototype_only": data.get("prototype_only", True),
        "data_is_real": data.get("data_is_real", False),
        "scenario_count": data.get("scenario_count", len(data.get("scenarios", []))),
        "notes": data.get("notes", {}),
        "categories": data.get("categories", {}),
    }


def get_scenario(scenario_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single scenario by its unique ID (e.g., 'VEG-001')."""
    if not scenario_id:
        return None
    for s in load_scenarios():
        if s.get("id") == scenario_id:
            return s
    return None


def get_scenarios_by_category(category: str) -> List[Dict[str, Any]]:
    """Return all scenarios matching the specified category."""
    cat_lower = category.strip().lower()
    return [
        s for s in load_scenarios()
        if s.get("category", "").lower() == cat_lower
        or cat_lower in s.get("category", "").lower()
    ]


def get_scenario_by_location(location: str) -> Optional[Dict[str, Any]]:
    """Retrieve the first scenario matching a location name."""
    loc_lower = location.strip().lower()
    for s in load_scenarios():
        if loc_lower in s.get("location", "").lower():
            return s
    return None
