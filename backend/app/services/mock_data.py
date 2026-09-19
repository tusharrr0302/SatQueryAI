import math
import random
from typing import Dict, Any, Optional
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


def _generate_surface_grid(rows=16, cols=16, base=0.35, variance=0.3) -> list[list[float]]:
    """Generates a realistic 2D matrix representing scientific values (e.g. NDVI or elevation)."""
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            # smooth undulating terrain
            val = base + (r * 0.02) - (c * 0.015) + (math.sin(r * 0.6) * 0.15) + (math.cos(c * 0.6) * 0.12)
            val = max(-0.2, min(0.85, round(val, 3)))
            row.append(val)
        grid.append(row)
    return grid



MOCK_CATALOG: Dict[str, Dict[str, Any]] = {
    "delhi_vegetation": {
        "analysis_type": "vegetation",
        "aoi": AOIInfo(
            name="Delhi, India",
            country="India",
            type="Polygon",
            center=Coordinates(latitude=28.6139, longitude=77.2090),
            area_km2=1483.0,
            bbox=[76.84, 28.40, 77.34, 28.88],
            polygon=[
                [76.84, 28.40], [77.34, 28.40], [77.34, 28.88], [76.84, 28.88], [76.84, 28.40]
            ],
        ),
        "model_id": "prithvi-eo-2.0",
        "model_name": "Prithvi-EO-2.0",
        "datasets": ["sentinel-2"],
        "acquisition_dates": "Jun 2023 → Jun 2024",
        "key_finding": "Net NDVI increase of +0.14 observed in the peripheral ridge and Yamuna floodplain buffers.",
        "scientific_explanation": (
            "The vegetation index (NDVI) in Delhi shows a clear increase in green cover in several "
            "peripheral areas between Jun 2023 and Jun 2024. Multispectral analysis indicates canopy "
            "regeneration in the Southern Ridge protected corridors and enhanced seasonal biomass "
            "density across agricultural pockets in Najafgarh."
        ),
        "metrics": [
            MetricItem(label="Mean NDVI", value="0.48", change="+0.14", trend="increase", unit="index"),
            MetricItem(label="Vegetation Cover", value="24.8%", change="+2.6%", trend="increase", unit="%"),
            MetricItem(label="Canopy Density", value="+18.4 km²", change="+5.1%", trend="increase", unit="km²"),
            MetricItem(label="Model Confidence", value="94.2%", change=None, trend="stable", unit="%"),
        ],
        "image_comparison": SatelliteImagePair(
            t1_date="Jun 2023",
            t1_url="/static/images/delhi_2023.jpg",
            t1_label="Jun 2023 (Sentinel-2 L2A)",
            t2_date="Jun 2024",
            t2_url="/static/images/delhi_2024.jpg",
            t2_label="Jun 2024 (Sentinel-2 L2A)",
            description="High-resolution Sentinel-2 false-color infrared comparison displaying accelerated green canopy biomass."
        ),
        "visualization": VisualizationSpec(
            type="3D Surface",
            title="NDVI (Vegetation Index)",
            sub_title="Delhi Region • Jun 2023 - Jun 2024",
            date_range="Jun 2023 - Jun 2024",
            color_map="ndvi",
            legend_min=-0.2,
            legend_max=0.8,
            legend_unit="NDVI",
            surface_opacity=0.85,
            vertical_exaggeration=2.2,
            surface_grid=_generate_surface_grid(16, 16, 0.42, 0.25)
        ),
        "time_series": [
            TimeSeriesPoint(date="2023-06", value=0.34, label="Jun 2023"),
            TimeSeriesPoint(date="2023-09", value=0.51, label="Sep 2023"),
            TimeSeriesPoint(date="2023-12", value=0.42, label="Dec 2023"),
            TimeSeriesPoint(date="2024-03", value=0.38, label="Mar 2024"),
            TimeSeriesPoint(date="2024-06", value=0.48, label="Jun 2024"),
        ],
        "suggested_questions": [
            "Show urban expansion in Delhi",
            "Detect water bodies in this area",
            "Compare with 5 year trend",
            "Show land surface temperature"
        ]
    },
    "delhi_decadal": {
        "analysis_type": "temporal_change",
        "aoi": AOIInfo(
            name="Delhi, India",
            country="India",
            type="Polygon",
            center=Coordinates(latitude=28.6139, longitude=77.2090),
            area_km2=1483.0,
            bbox=[76.84, 28.40, 77.34, 28.88],
            polygon=[
                [76.84, 28.40], [77.34, 28.40], [77.34, 28.88], [76.84, 28.88], [76.84, 28.40]
            ],
        ),
        "model_id": "prithvi-eo-2.0",
        "model_name": "Prithvi-EO-2.0",
        "datasets": ["sentinel-2", "sentinel-1"],
        "acquisition_dates": "2016 → 2026",
        "key_finding": "Urban expansion of +134.2 km² with 21.4% growth rate identified over 2016-2026.",
        "scientific_explanation": (
            "Delhi shows measurable urban expansion between the selected periods (2016 → 2026). "
            "Bi-temporal feature embeddings from Prithvi-EO-2.0 detect intensive land-use transformation "
            "along the Western and Eastern Peripheral Expressways, Dwarka Sector expansion, and the "
            "Gurugram/Noida agglomeration corridors, accompanied by conversion of fallow agricultural land."
        ),
        "metrics": [
            MetricItem(label="Urban expansion", value="+134.2 km²", change="+21.4%", trend="increase", unit="km²"),
            MetricItem(label="Growth rate", value="21.4%", change="+3.2% vs decadal avg", trend="increase", unit="%"),
            MetricItem(label="Impervious Surface", value="68.2%", change="+8.7%", trend="increase", unit="%"),
            MetricItem(label="Confidence", value="93%", change=None, trend="stable", unit="%"),
        ],
        "image_comparison": SatelliteImagePair(
            t1_date="2016",
            t1_url="/static/images/delhi_2016.jpg",
            t1_label="2016 (Sentinel-2)",
            t2_date="2026",
            t2_url="/static/images/delhi_2026.jpg",
            t2_label="2026 (Sentinel-2)",
            description="Bi-temporal composite highlighting extensive urban infrastructure conversion."
        ),
        "visualization": VisualizationSpec(
            type="Change Map",
            title="Urban Expansion & Built-Up Growth",
            sub_title="Delhi NCR • 2016 - 2026",
            date_range="2016 - 2026",
            color_map="diverging",
            legend_min=-1.0,
            legend_max=1.0,
            legend_unit="Change Score",
            surface_opacity=0.90,
            vertical_exaggeration=2.5,
            surface_grid=_generate_surface_grid(16, 16, 0.2, 0.4)
        ),
        "time_series": [
            TimeSeriesPoint(date="2016", value=627.1, label="2016"),
            TimeSeriesPoint(date="2018", value=654.8, label="2018"),
            TimeSeriesPoint(date="2020", value=689.4, label="2020"),
            TimeSeriesPoint(date="2022", value=718.3, label="2022"),
            TimeSeriesPoint(date="2024", value=743.9, label="2024"),
            TimeSeriesPoint(date="2026", value=761.3, label="2026"),
        ],
        "suggested_questions": [
            "Show urban expansion in Delhi",
            "Show vegetation change",
            "Compare with another region",
            "Show the time series"
        ]
    },
    "amazon_deforestation": {
        "analysis_type": "temporal_change",
        "aoi": AOIInfo(
            name="Amazon Basin, Para, Brazil",
            country="Brazil",
            type="Polygon",
            center=Coordinates(latitude=-3.4653, longitude=-62.2159),
            area_km2=28400.0,
            bbox=[-63.1, -4.2, -61.3, -2.7],
            polygon=[
                [-63.1, -4.2], [-61.3, -4.2], [-61.3, -2.7], [-63.1, -2.7], [-63.1, -4.2]
            ],
        ),
        "model_id": "terrafm",
        "model_name": "TerraFM",
        "datasets": ["sentinel-1", "sentinel-2"],
        "acquisition_dates": "2021 → 2024",
        "key_finding": "Forest canopy loss of 312.4 km² flagged by multimodal Optical-SAR cross-validation.",
        "scientific_explanation": (
            "SAR C-band backscatter combined with Sentinel-2 spectral indices identifies significant canopy loss "
            "along logging transects. Cloud-penetrating radar confirms clearcut clusters even during rainy seasons."
        ),
        "metrics": [
            MetricItem(label="Forest Loss", value="-312.4 km²", change="-4.8%", trend="decrease", unit="km²"),
            MetricItem(label="SAR Depolarization", value="-3.8 dB", change="-1.2 dB", trend="decrease", unit="dB"),
            MetricItem(label="Fragmentation Index", value="0.74", change="+0.18", trend="increase", unit="score"),
            MetricItem(label="Confidence", value="96.1%", change=None, trend="stable", unit="%"),
        ],
        "image_comparison": SatelliteImagePair(
            t1_date="Aug 2021",
            t1_url="/static/images/amazon_2021.jpg",
            t1_label="Aug 2021",
            t2_date="Aug 2024",
            t2_url="/static/images/amazon_2024.jpg",
            t2_label="Aug 2024",
            description="Cross-sensor Optical/SAR analysis detecting recent canopy clearings."
        ),
        "visualization": VisualizationSpec(
            type="Change Map",
            title="Forest Canopy Disturbance",
            sub_title="Amazon Basin, Para • 2021 - 2024",
            date_range="2021 - 2024",
            color_map="diverging",
            legend_min=-1.0,
            legend_max=1.0,
            legend_unit="Loss Index",
            surface_opacity=0.88,
            vertical_exaggeration=1.8,
            surface_grid=_generate_surface_grid(16, 16, 0.6, 0.3)
        ),
        "time_series": [
            TimeSeriesPoint(date="2021", value=28400, label="2021"),
            TimeSeriesPoint(date="2022", value=28290, label="2022"),
            TimeSeriesPoint(date="2023", value=28180, label="2023"),
            TimeSeriesPoint(date="2024", value=28087, label="2024"),
        ],
        "suggested_questions": [
            "Highlight roads and access routes",
            "Calculate carbon stock equivalent",
            "Show monthly SAR coherence loss",
            "Compare with Mato Grosso state"
        ]
    },
    "punjab_agriculture": {
        "analysis_type": "vegetation",
        "aoi": AOIInfo(
            name="Punjab Agricultural Belt",
            country="India",
            type="Polygon",
            center=Coordinates(latitude=31.1471, longitude=75.3412),
            area_km2=50362.0,
            bbox=[74.5, 30.1, 76.8, 32.3],
            polygon=[
                [74.5, 30.1], [76.8, 30.1], [76.8, 32.3], [74.5, 32.3], [74.5, 30.1]
            ],
        ),
        "model_id": "prithvi-eo-2.0",
        "model_name": "Prithvi-EO-2.0",
        "datasets": ["sentinel-2"],
        "acquisition_dates": "Oct 2023 → Apr 2024",
        "key_finding": "Rabi wheat crop health index averages 0.72 with favorable biomass accumulation.",
        "scientific_explanation": (
            "Temporal red-edge and NIR reflectance profiles indicate robust vegetative development "
            "across Jalandhar and Ludhiana districts. Chlorophyll absorption metrics peaked during early March."
        ),
        "metrics": [
            MetricItem(label="Peak NDVI", value="0.74", change="+0.08 vs 5yr", trend="increase", unit="index"),
            MetricItem(label="Yield Estimate", value="4.8 t/ha", change="+3.4%", trend="increase", unit="ton/ha"),
            MetricItem(label="Water Stress", value="Low (12%)", change="-4%", trend="decrease", unit="%"),
            MetricItem(label="Confidence", value="95%", change=None, trend="stable", unit="%"),
        ],
        "image_comparison": SatelliteImagePair(
            t1_date="Nov 2023",
            t1_url="/static/images/punjab_nov.jpg",
            t1_label="Nov 2023 (Early Tillering)",
            t2_date="Mar 2024",
            t2_url="/static/images/punjab_mar.jpg",
            t2_label="Mar 2024 (Peak Flowering)",
            description="False color infrared comparing emergence against peak crop heading."
        ),
        "visualization": VisualizationSpec(
            type="3D Surface",
            title="Crop Health & Biomass Index",
            sub_title="Punjab Agricultural Grid • Rabi Season",
            date_range="Nov 2023 - Mar 2024",
            color_map="ndvi",
            legend_min=0.0,
            legend_max=0.9,
            legend_unit="NDVI",
            surface_opacity=0.85,
            vertical_exaggeration=2.0,
            surface_grid=_generate_surface_grid(16, 16, 0.55, 0.2)
        ),
        "time_series": [
            TimeSeriesPoint(date="2023-11", value=0.28, label="Nov"),
            TimeSeriesPoint(date="2023-12", value=0.45, label="Dec"),
            TimeSeriesPoint(date="2024-01", value=0.62, label="Jan"),
            TimeSeriesPoint(date="2024-02", value=0.74, label="Feb"),
            TimeSeriesPoint(date="2024-03", value=0.71, label="Mar"),
            TimeSeriesPoint(date="2024-04", value=0.35, label="Apr"),
        ],
        "suggested_questions": [
            "Show moisture stress anomaly",
            "Identify stubble burning hotspots",
            "Compare canal vs tube-well irrigated tracts",
            "Estimate harvest completion percentage"
        ]
    },
    "derna_flood": {
        "analysis_type": "flood",
        "aoi": AOIInfo(
            name="Derna, Libya",
            country="Libya",
            type="Polygon",
            center=Coordinates(latitude=32.7667, longitude=22.6367),
            area_km2=240.0,
            bbox=[22.58, 32.72, 22.70, 32.81],
            polygon=[
                [22.58, 32.72], [22.70, 32.72], [22.70, 32.81], [22.58, 32.81], [22.58, 32.72]
            ],
        ),
        "model_id": "terrafm",
        "model_name": "TerraFM",
        "datasets": ["sentinel-1", "sentinel-2"],
        "acquisition_dates": "Sep 08, 2023 → Sep 13, 2023",
        "key_finding": "Flash flood surge inundated 4.6 km² of urban fabric with significant sediment discharge.",
        "scientific_explanation": (
            "SAR specular backscatter drop coupled with post-storm optical imagery identifies extensive "
            "wadi valley erosion following Storm Daniel. Severe debris scouring is mapped along the coastal fan."
        ),
        "metrics": [
            MetricItem(label="Inundation Extent", value="4.6 km²", change=None, trend="increase", unit="km²"),
            MetricItem(label="Structures Impacted", value="2,140", change=None, trend="increase", unit="bldgs"),
            MetricItem(label="Sediment Plume", value="18.2 km²", change=None, trend="increase", unit="km²"),
            MetricItem(label="Confidence", value="97.4%", change=None, trend="stable", unit="%"),
        ],
        "image_comparison": SatelliteImagePair(
            t1_date="08 Sep 2023",
            t1_url="/static/images/derna_pre.jpg",
            t1_label="Pre-Event (08 Sep 2023)",
            t2_date="13 Sep 2023",
            t2_url="/static/images/derna_post.jpg",
            t2_label="Post-Event (13 Sep 2023)",
            description="Sentinel-1 SAR coherence contrast revealing dam break floodway destruction."
        ),
        "visualization": VisualizationSpec(
            type="Change Map",
            title="Storm Daniel Inundation & Sedimentation",
            sub_title="Derna Wadi Corridor",
            date_range="Sep 2023",
            color_map="diverging",
            legend_min=0.0,
            legend_max=1.0,
            legend_unit="Inundation Probability",
            surface_opacity=0.92,
            vertical_exaggeration=3.0,
            surface_grid=_generate_surface_grid(16, 16, 0.15, 0.5)
        ),
        "time_series": [
            TimeSeriesPoint(date="2023-09-08", value=0.05, label="Pre-Storm"),
            TimeSeriesPoint(date="2023-09-11", value=4.60, label="Peak Surge"),
            TimeSeriesPoint(date="2023-09-15", value=1.20, label="Receding"),
        ],
        "suggested_questions": [
            "Estimate damaged road network length",
            "Show pre-flood dam reservoir capacity",
            "Display SAR difference backscatter mask",
            "Export GeoJSON inundation polygon"
        ]
    }
}


def build_audit_trace(model_name: str, dataset_names: list[str], source: str = "mock") -> list[AuditTraceStage]:
    return [
        AuditTraceStage(
            stage="1",
            name="UNDERSTANDING REQUEST",
            status="completed",
            duration_ms=38,
            details="Natural language intent parsed, spatial/temporal scope bounded"
        ),
        AuditTraceStage(
            stage="2",
            name="SELECTING DATA",
            status="completed",
            duration_ms=45,
            details=f"Datasets resolved: {', '.join(dataset_names)}"
        ),
        AuditTraceStage(
            stage="3",
            name="SELECTING MODEL",
            status="completed",
            duration_ms=29,
            details=f"EO Specialist model bound: {model_name}"
        ),
        AuditTraceStage(
            stage="4",
            name="RUNNING ANALYSIS",
            status="completed",
            duration_ms=184 if source == "mock" else 1420,
            details=f"Execution pipeline dispatched (source: {source})"
        ),
        AuditTraceStage(
            stage="5",
            name="GENERATING VISUALIZATION",
            status="completed",
            duration_ms=52,
            details="3D geospatial surface and comparison layers constructed"
        ),
        AuditTraceStage(
            stage="6",
            name="COMPLETE",
            status="completed",
            duration_ms=12,
            details="Audited normalized result delivered"
        )
    ]


def get_mock_result_for_query(query: str, source: str = "mock", fallback: bool = False) -> NormalizedResult:
    q = query.lower()
    
    # Matching logic
    if "vegetation" in q or "jun 2023" in q or "ndvi" in q:
        entry = MOCK_CATALOG["delhi_vegetation"]
    elif "delhi" in q or "urban" in q or "growth" in q or "10 year" in q:
        entry = MOCK_CATALOG["delhi_decadal"]
    elif "amazon" in q or "deforest" in q:
        entry = MOCK_CATALOG["amazon_deforestation"]
    elif "punjab" in q or "crop" in q or "wheat" in q:
        entry = MOCK_CATALOG["punjab_agriculture"]
    elif "derna" in q or "flood" in q or "libya" in q:
        entry = MOCK_CATALOG["derna_flood"]
    else:
        # Default to Delhi vegetation/change flagship demo
        entry = MOCK_CATALOG["delhi_vegetation"]

    audit = build_audit_trace(entry["model_name"], entry["datasets"], source=source)

    return NormalizedResult(
        query=query,
        analysis_type=entry["analysis_type"],
        aoi=entry["aoi"],
        provenance=Provenance(
            source=source,
            fallback=fallback,
            model_id=entry["model_id"],
            model_name=entry["model_name"],
            dataset_ids=entry["datasets"],
            acquisition_dates=entry["acquisition_dates"],
            pipeline="ATS / LangGraph"
        ),
        key_finding=entry["key_finding"],
        scientific_explanation=entry["scientific_explanation"],
        metrics=entry["metrics"],
        image_comparison=entry["image_comparison"],
        visualization=entry["visualization"],
        time_series=entry["time_series"],
        confidence=0.93 if entry["model_id"] == "prithvi-eo-2.0" else 0.95,
        confidence_level="High",
        audit_trace=audit,
        suggested_questions=entry["suggested_questions"]
    )
