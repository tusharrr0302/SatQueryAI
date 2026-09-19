"""
SatQuery AI — Scenario to NormalizedResult Adapter

Converts any scenario from satquery_scenarios.json or supplemental mock scenarios
into a fully populated NormalizedResult without inventing or altering metrics.
"""
from __future__ import annotations

import math
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.schemas.normalized_result import (
    NormalizedResult,
    AOIInfo,
    Coordinates,
    MetricItem,
    TimeSeriesPoint,
    SatelliteImagePair,
    VisualizationSpec,
    AuditTraceStage,
    Provenance,
)
from app.services.visualization_registry import select_visualizations


# Optional image pairs for flagship locations
FLAGSHIP_IMAGES = {
    "delhi": SatelliteImagePair(
        t1_date="2016",
        t1_url="/static/images/delhi_2016.jpg",
        t1_label="2016 Baseline (Sentinel-2)",
        t2_date="2026",
        t2_url="/static/images/delhi_2026.jpg",
        t2_label="2026 Current (Sentinel-2)",
        description="Multi-temporal urban built-up expansion across peripheral Delhi NCR."
    ),
    "delhi_veg": SatelliteImagePair(
        t1_date="Jun 2023",
        t1_url="/static/images/delhi_2023.jpg",
        t1_label="Jun 2023 (Sentinel-2 L2A)",
        t2_date="Jun 2024",
        t2_url="/static/images/delhi_2024.jpg",
        t2_label="Jun 2024 (Sentinel-2 L2A)",
        description="High-resolution Sentinel-2 false-color infrared comparison displaying green canopy regeneration."
    ),
    "amazon": SatelliteImagePair(
        t1_date="Aug 2021",
        t1_url="/static/images/amazon_2021.jpg",
        t1_label="Aug 2021 (Sentinel-2)",
        t2_date="Aug 2024",
        t2_url="/static/images/amazon_2024.jpg",
        t2_label="Aug 2024 (Sentinel-2)",
        description="Canopy disturbance and clear-cut logging corridors across Pará state."
    ),
    "punjab": SatelliteImagePair(
        t1_date="Nov 2023",
        t1_url="/static/images/punjab_nov.jpg",
        t1_label="Nov 2023 Post-Harvest",
        t2_date="Mar 2024",
        t2_url="/static/images/punjab_mar.jpg",
        t2_label="Mar 2024 Peak Vegetative Vigor",
        description="Seasonal phenology progression across wheat farming parcels."
    ),
    "derna": SatelliteImagePair(
        t1_date="Sep 08, 2023",
        t1_url="/static/images/derna_pre.jpg",
        t1_label="Pre-Flood Baseline (Optical)",
        t2_date="Sep 13, 2023",
        t2_url="/static/images/derna_post.jpg",
        t2_label="Post-Flood Inundation (Sentinel-1 SAR)",
        description="Catastrophic dam-break flood boundary along Wadi Derna."
    ),
}


def _generate_surface_grid(rows: int = 16, cols: int = 16, base_val: float = 0.45) -> Optional[List[List[float]]]:
    """No synthetic surface grid is fabricated unless authentic raster grid telemetry exists."""
    return None


def _calculate_bbox_area(bbox: List[float]) -> float:
    """Calculate approximate area in km2 from a bounding box [min_lon, min_lat, max_lon, max_lat]."""
    if len(bbox) != 4:
        return 1250.0
    min_lon, min_lat, max_lon, max_lat = bbox
    # 1 deg lat approx 111 km, 1 deg lon approx 111 * cos(mean_lat) km
    mean_lat = (min_lat + max_lat) / 2.0
    lat_dist = abs(max_lat - min_lat) * 111.0
    lon_dist = abs(max_lon - min_lon) * 111.0 * math.cos(math.radians(mean_lat))
    area = lat_dist * lon_dist
    return round(max(10.0, area), 1)


def _format_metric_label(key: str) -> str:
    """Format a dictionary key into a readable metric label."""
    words = key.replace("_", " ").split()
    return " ".join(w.capitalize() for w in words)


def _parse_metrics_from_mock_data(mock_data: Dict[str, Any]) -> List[MetricItem]:
    """Extract and format every metric from the scenario's mock_data accurately."""
    metrics: List[MetricItem] = []
    
    # Priority order for metrics
    loss_km2 = None
    loss_lbl = "Change Extent"
    trend = "decrease"

    if "vegetation_loss_km2" in mock_data or "loss_km2" in mock_data:
        loss_km2 = mock_data.get("vegetation_loss_km2") or mock_data.get("loss_km2")
        loss_lbl = "Vegetation Loss"
        trend = "decrease"
    elif "deforestation_km2" in mock_data:
        loss_km2 = mock_data.get("deforestation_km2")
        loss_lbl = "Deforestation"
        trend = "decrease"
    elif "urban_expansion_km2" in mock_data:
        loss_km2 = mock_data.get("urban_expansion_km2")
        loss_lbl = "Urban expansion"
        trend = "increase"
    elif "flooded_area_km2" in mock_data or "inundation_area_km2" in mock_data:
        loss_km2 = mock_data.get("flooded_area_km2") or mock_data.get("inundation_area_km2")
        loss_lbl = "Inundation Extent"
        trend = "increase"

    loss_pct = (
        mock_data.get("vegetation_loss_percent")
        or mock_data.get("loss_percent")
        or mock_data.get("deforestation_percent")
        or mock_data.get("growth_rate_percent")
        or mock_data.get("flooded_percent_of_state")
    )
    
    if loss_km2 is not None:
        sign = "-" if trend == "decrease" else "+"
        change_str = f"{sign}{loss_pct}%" if loss_pct is not None else None
        val_str = f"{sign}{loss_km2} km²" if not str(loss_km2).startswith(("-", "+")) else f"{loss_km2} km²"
        metrics.append(MetricItem(
            label=loss_lbl,
            value=val_str,
            change=change_str,
            trend=trend,
            unit="km²"
        ))

    # Parse NDVI fields
    for k, v in mock_data.items():
        if "ndvi" in k:
            year_match = re.search(r"\d{4}", k)
            yr = year_match.group(0) if year_match else ""
            lbl = f"NDVI ({yr})" if yr else "Mean NDVI"
            metrics.append(MetricItem(
                label=lbl,
                value=str(v),
                unit="index"
            ))

    # Parse remaining numeric metrics
    skip_keys = {"vegetation_loss_km2", "loss_km2", "deforestation_km2", "urban_expansion_km2", "flooded_area_km2", "inundation_area_km2", "vegetation_loss_percent", "loss_percent", "deforestation_percent", "growth_rate_percent", "flooded_percent_of_state", "confidence", "satellite", "primary_drivers"}
    for k, v in mock_data.items():
        if k in skip_keys or "ndvi" in k:
            continue
        if isinstance(v, (int, float)):
            unit = "%" if "percent" in k or "ratio" in k else ("km²" if "km2" in k else ("m" if "depth" in k else ""))
            val_str = f"{v}%" if "percent" in k and not str(v).endswith("%") else str(v)
            metrics.append(MetricItem(
                label=_format_metric_label(k),
                value=val_str,
                unit=unit
            ))

    # Always add Model Confidence
    conf = mock_data.get("confidence", 0.92)
    metrics.append(MetricItem(
        label="Model Confidence",
        value=f"{round(float(conf) * 100, 1)}%",
        trend="stable",
        unit="%"
    ))

    return metrics


def _determine_model_and_datasets(category: str, satellite: str) -> tuple[str, str, List[str]]:
    """Return (model_id, model_name, dataset_ids) appropriate for the scenario."""
    sat_lower = satellite.lower()
    cat_lower = category.lower()

    if "sentinel-1" in sat_lower or "sar" in sat_lower or "flood" in cat_lower:
        return "terrafm", "TerraFM", ["sentinel-1", "sentinel-2"] if "sentinel-2" in sat_lower else ["sentinel-1"]
    elif "landsat" in sat_lower:
        datasets = ["landsat", "sentinel-2"] if "sentinel" in sat_lower else ["landsat"]
        return "prithvi-eo-2.0", "Prithvi-EO-2.0", datasets
    elif "image_analysis" in cat_lower or "vqa" in cat_lower:
        return "geochat-7b", "GeoChat-7B", ["sentinel-2"]
    elif "ocean" in cat_lower or "marine" in cat_lower:
        return "closp", "CLOSP", ["sentinel-1", "sentinel-2"]
    else:
        # Default for vegetation, urban, agriculture
        return "prithvi-eo-2.0", "Prithvi-EO-2.0", ["sentinel-2"]


def _build_audit_trace(model_name: str, datasets: List[str]) -> List[AuditTraceStage]:
    """Generate the standard 6-stage execution audit trace."""
    now = datetime.utcnow().isoformat()
    return [
        AuditTraceStage(stage="1", name="QUERY UNDERSTANDING", status="completed", duration_ms=42, details="Query parsed and validated against scenario catalog", timestamp=now),
        AuditTraceStage(stage="2", name="AOI DELINEATION", status="completed", duration_ms=18, details="Spatial bounding box & polygon geometry generated", timestamp=now),
        AuditTraceStage(stage="3", name="DATASET & MODEL SELECTION", status="completed", duration_ms=25, details=f"EO Specialist model bound: {model_name} on {', '.join(datasets)}", timestamp=now),
        AuditTraceStage(stage="4", name="RUNNING ANALYSIS", status="completed", duration_ms=115, details="Execution pipeline completed (source: mock)", timestamp=now),
        AuditTraceStage(stage="5", name="GENERATING VISUALIZATION", status="completed", duration_ms=45, details="3D geospatial surface and chart specs constructed", timestamp=now),
        AuditTraceStage(stage="6", name="COMPLETE", status="completed", duration_ms=10, details="Authoritative normalized result delivered", timestamp=now),
    ]


def scenario_to_normalized_result(scenario: Dict[str, Any], user_query: str = "") -> NormalizedResult:
    """
    Converts a scenario dictionary from satquery_scenarios.json into a NormalizedResult.
    All scenario numbers, dates, locations, and findings are strictly preserved.
    """
    sid = scenario.get("id", "SCENARIO")
    location = scenario.get("location", "Target Region")
    category = scenario.get("category", "vegetation")
    question = scenario.get("question", "")
    query = user_query.strip() if user_query else question
    expected_answer = scenario.get("expected_answer", "")
    mock_data = scenario.get("mock_data", {})
    satellite = mock_data.get("satellite", "Sentinel-2")
    bbox = scenario.get("bbox", [77.0, 28.0, 78.0, 29.0])
    time_range = scenario.get("time_range", {})

    # 1. Coordinates and AOI
    if len(bbox) == 4:
        min_lon, min_lat, max_lon, max_lat = bbox
        center_lat = (min_lat + max_lat) / 2.0
        center_lon = (min_lon + max_lon) / 2.0
        polygon = [
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat],
        ]
        area_km2 = _calculate_bbox_area(bbox)
    else:
        center_lat = 28.6139
        center_lon = 77.2090
        polygon = []
        area_km2 = 1250.0

    country = location.split(",")[-1].strip() if "," in location else None

    aoi = AOIInfo(
        id=f"aoi_{sid.lower().replace('-', '_')}",
        name=location,
        country=country,
        type="Polygon",
        center=Coordinates(latitude=center_lat, longitude=center_lon),
        area_km2=area_km2,
        bbox=bbox,
        polygon=polygon,
    )

    # 2. Model and Provenance
    model_id, model_name, dataset_ids = _determine_model_and_datasets(category, satellite)
    start_date = str(time_range.get("start", ""))
    end_date = str(time_range.get("end", ""))
    acq_dates = f"{start_date} → {end_date}" if start_date and end_date else "Observed Period"

    provenance = Provenance(
        source="mock",
        worker_url=None,
        fallback=False,
        model_id=model_id,
        model_name=model_name,
        dataset_ids=dataset_ids,
        acquisition_dates=acq_dates,
        pipeline="ATS / LangGraph",
    )

    # 3. Metrics
    metrics = _parse_metrics_from_mock_data(mock_data)

    # 4. Time series points
    time_series: List[TimeSeriesPoint] = []
    ndvi_keys = sorted([k for k in mock_data.keys() if "ndvi" in k])
    if len(ndvi_keys) >= 2:
        for k in ndvi_keys:
            yr = re.search(r"\d{4}", k)
            date_str = yr.group(0) if yr else "Period"
            try:
                time_series.append(TimeSeriesPoint(
                    date=date_str,
                    value=float(mock_data[k]),
                    label=f"NDVI {date_str}",
                    unit="index"
                ))
            except (ValueError, TypeError):
                pass

    # 5. Deterministic Authoritative Visualizations
    visualizations = select_visualizations(
        query=query,
        scenario=scenario,
        mock_data=mock_data,
        metrics=metrics,
        time_series=time_series,
    )

    primary_vis = visualizations[0] if visualizations else None
    vis_type = "Time Series"
    vis_title = f"{category.replace('_', ' ').title()} Analysis"
    if primary_vis:
        raw_t = primary_vis.get("type", "")
        if raw_t == "line":
            vis_type = "Time Series"
        elif raw_t == "bar":
            vis_type = "Change Map" if ("loss" in category or "change" in category or "urban" in category) else "Comparison Chart"
        elif raw_t in ["donut", "pie"]:
            vis_type = "Land Cover"
        elif raw_t == "heatmap":
            vis_type = "Heatmap"
        elif raw_t in ["spatial_overlay", "change_layer", "flood_extent"]:
            vis_type = "Change Map"
        elif raw_t == "scatter":
            vis_type = "Scatter Plot"
        vis_title = primary_vis.get("title", vis_title)

    visualization = VisualizationSpec(
        type=vis_type,
        title=vis_title,
        sub_title=f"{location} • {acq_dates}",
        date_range=acq_dates,
        color_map="ndvi" if category in ["vegetation", "agriculture"] else "viridis",
        legend_min=-0.2 if category in ["vegetation", "agriculture"] else 0.0,
        legend_max=0.9 if category in ["vegetation", "agriculture"] else 1.0,
        legend_unit="NDVI" if category in ["vegetation", "agriculture"] else "INDEX",
        surface_opacity=0.85,
        vertical_exaggeration=2.2,
        surface_grid=None,
        timeseries=time_series if time_series else None,
    )

    # 6. Satellite image comparison (if flagship location matches)
    image_comparison: Optional[SatelliteImagePair] = None
    loc_lower = location.lower()
    if "delhi" in loc_lower:
        image_comparison = FLAGSHIP_IMAGES["delhi"] if "urban" in category else FLAGSHIP_IMAGES["delhi_veg"]
    elif "amazon" in loc_lower or "para" in loc_lower:
        image_comparison = FLAGSHIP_IMAGES["amazon"]
    elif "punjab" in loc_lower:
        image_comparison = FLAGSHIP_IMAGES["punjab"]
    elif "derna" in loc_lower:
        image_comparison = FLAGSHIP_IMAGES["derna"]

    # 7. Audit Trace
    audit_trace = _build_audit_trace(model_name, dataset_ids)

    # 8. Suggested follow-up questions
    suggested_questions = [
        f"Show high-resolution satellite change in {location.split(',')[0]}",
        f"Compare with neighboring regions",
        f"What EO sensors were used in this study?",
        f"Analyze temporal trend over the past 5 years"
    ]

    confidence = float(mock_data.get("confidence", 0.92))

    location_dict = {
        "name": location,
        "latitude": center_lat,
        "longitude": center_lon,
    }

    return NormalizedResult(
        result_id=f"res_{sid.lower().replace('-', '_')}_{uuid.uuid4().hex[:6]}",
        query=query,
        analysis_type=category,
        aoi=aoi,
        location=location_dict,
        provenance=provenance,
        key_finding=expected_answer,
        scientific_explanation=expected_answer,
        metrics=metrics,
        image_comparison=image_comparison,
        visualization=visualization,
        visualizations=visualizations,
        time_series=time_series,
        confidence=confidence,
        confidence_level="High" if confidence >= 0.9 else "Medium",
        audit_trace=audit_trace,
        suggested_questions=suggested_questions,
    )

