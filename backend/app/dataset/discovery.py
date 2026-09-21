"""
SatQuery AI — Intelligent Dataset & Layer Discovery Engine
Performs deterministic requirement formulation, multi-criteria dataset ranking,
and semantic active layer discovery (DATASET ≠ LAYER).
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.data_catalog import (
    DataRequirementPlan,
    DatasetMetadata,
    LayerDefinition,
)
from app.dataset.registry import list_datasets, get_dataset
from app.dataset.layer_catalog import list_layers_for_dataset, search_layer_catalog


def infer_data_requirement_plan(
    query: str,
    active_asset: Optional[Any] = None,
    location_hint: Optional[str] = None,
) -> DataRequirementPlan:
    """
    Formulates a structured DataRequirementPlan from the user query.
    Extracts targeted phenomenon, required modalities, spatial, and temporal scopes.
    """
    import datetime
    q_low = query.lower().strip()

    # Handle if string was passed in active_asset position as location_hint
    if isinstance(active_asset, str) and not location_hint:
        location_hint = active_asset
        active_asset = None

    # Extract location if mentioned
    loc_cand = location_hint.title() if location_hint else None
    if not loc_cand:
        for place in [
            "kashmir valley", "kashmir", "srinagar", "jammu", "delhi", "mumbai",
            "bengaluru", "chennai", "kolkata", "hyderabad", "pune", "uttarakhand",
            "derna", "leh", "ladakh", "shimla", "himachal", "valencia", "turkey"
        ]:
            if re.search(r"\b" + re.escape(place) + r"\b", q_low):
                loc_cand = place.title()
                break

    # Extract temporal scope
    m_years = re.search(r"last\s+(\d+)\s+years?", q_low)
    years = int(m_years.group(1)) if m_years else 2
    cur_year = datetime.date.today().year
    temporal_dict = {"start": str(cur_year - years), "end": str(cur_year)}

    if isinstance(active_asset, dict):
        return DataRequirementPlan(
            question=query,
            phenomenon="user_asset_inspection",
            modality=["custom_raster"],
            temporal=False,
            spatial=True,
            resolution="high",
            preferred_provider="user_assets",
            location=active_asset.get("filename", "User Asset"),
            temporal_scope=temporal_dict,
            primary_domain="user_data",
            user_intent="data_inspection",
            analysis_requirements=["raster inspection", "spectral band profile"],
            supporting_requirements=["geospatial bounds", "spatial resolution"],
            recommended_data_modalities=["custom_raster"],
        )

    # 0. Agricultural & Environmental Suitability Investigation (e.g. Kashmir apple farm)
    if any(k in q_low for k in ["apple farm", "farm", "orchard", "agriculture", "agricultural", "crop suitability", "farming option", "start a farm"]):
        return DataRequirementPlan(
            question=query,
            phenomenon="vegetation_change",
            modality=["optical", "multispectral", "terrain"],
            temporal=True,
            spatial=True,
            resolution="high",
            preferred_provider="copernicus",
            location=loc_cand or "Kashmir",
            temporal_scope=temporal_dict,
            primary_domain="vegetation",
            user_intent="agricultural investigation",
            analysis_requirements=["temporal vegetation change", "canopy stability"],
            supporting_requirements=["land cover", "terrain", "water availability", "environmental context"],
            recommended_data_modalities=["optical", "multispectral", "terrain"],
        )

    # 0b. Optical + SAR Multimodal Analysis
    if ("optical" in q_low and "sar" in q_low) or ("radar" in q_low and "optical" in q_low) or "cross-modal" in q_low:
        return DataRequirementPlan(
            question=query,
            phenomenon="cross_modal_optical_sar",
            modality=["optical", "sar"],
            temporal=True,
            spatial=True,
            resolution="high",
            preferred_provider="copernicus",
            location=loc_cand,
            temporal_scope=temporal_dict,
            primary_domain="multimodal",
            user_intent="cross_modal_analysis",
            analysis_requirements=["optical multispectral classification", "SAR backscatter roughness"],
            supporting_requirements=["joint mask", "cross-sensor calibration"],
            recommended_data_modalities=["optical", "sar"],
        )

    # 0c. Bi-Temporal Change Detection
    if any(k in q_low for k in ["between these two images", "between images", "what changed", "before and after", "two images", "pre and post", "compare pre", "pre- and post"]):
        return DataRequirementPlan(
            question=query,
            phenomenon="bitemporal_change",
            modality=["optical"],
            temporal=True,
            spatial=True,
            resolution="high",
            preferred_provider="copernicus",
            location=loc_cand,
            temporal_scope=temporal_dict,
            primary_domain="change_detection",
            user_intent="bitemporal_change",
            analysis_requirements=["bi-temporal surface difference", "altered parcel delineation"],
            supporting_requirements=["change magnitude", "false positive filtering"],
            recommended_data_modalities=["optical"],
        )

    # 0d. Single Image Understanding / VQA / Grounding
    if any(k in q_low for k in ["describe this image", "describe this satellite image", "what is visible", "describe the scene", "highlight the water body", "highlight water", "describe what you see", "what do you see", "what you see", "in this satellite image"]):
        intent = "grounding" if "highlight" in q_low else "single_image_vqa"
        return DataRequirementPlan(
            question=query,
            phenomenon="single_image_understanding",
            modality=["optical"],
            temporal=False,
            spatial=True,
            resolution="high",
            preferred_provider="copernicus",
            location=loc_cand,
            temporal_scope=temporal_dict,
            primary_domain="image_understanding",
            user_intent=intent,
            analysis_requirements=["scene feature classification", "spatial entity delineation"],
            supporting_requirements=["confidence scoring", "bounding box extraction"],
            recommended_data_modalities=["optical"],
        )

    # 1. Atmospheric / Pollution Queries
    if any(k in q_low for k in ["no2", "nitrogen dioxide", "air pollution", "air quality", "co ", "so2", "aerosol", "smoke plume", "emissions"]):
        return DataRequirementPlan(
            question=query,
            phenomenon="atmospheric_pollution",
            modality=["atmospheric"],
            temporal=True,
            spatial=True,
            resolution="coarse",
            preferred_provider="copernicus",
            location=loc_cand,
            temporal_scope=temporal_dict,
            primary_domain="atmospheric",
            user_intent="pollution_monitoring",
            analysis_requirements=["tropospheric vertical column density"],
            supporting_requirements=["cloud fraction mask", "quality assurance flags"],
            recommended_data_modalities=["atmospheric"],
        )

    # 2. Flood / Inundation Queries
    if any(k in q_low for k in ["flood", "flooding", "inundat", "submerged", "storm daniel"]):
        return DataRequirementPlan(
            question=query,
            phenomenon="flood_inundation",
            modality=["sar"],
            temporal=True,
            spatial=True,
            resolution="high",
            preferred_provider="copernicus",
            location=loc_cand,
            temporal_scope=temporal_dict,
            primary_domain="flood",
            user_intent="flood_extent_mapping",
            analysis_requirements=["SAR backscatter thresholding", "specular water detection"],
            supporting_requirements=["permanent water exclusion", "optical reference"],
            recommended_data_modalities=["sar", "optical"],
        )

    # 3. Elevation / Topography Queries
    if any(k in q_low for k in ["elevation", "terrain", "3d surface", "topograph", "dem", "slope", "hillshade", "altitude", "heightfield"]):
        return DataRequirementPlan(
            question=query,
            phenomenon="topography_elevation",
            modality=["dem"],
            temporal=False,
            spatial=True,
            resolution="medium",
            preferred_provider="copernicus",
            location=loc_cand,
            temporal_scope=temporal_dict,
            primary_domain="elevation",
            user_intent="terrain_analysis",
            analysis_requirements=["digital elevation model", "slope / hillshade profile"],
            supporting_requirements=["drainage gradient", "cross-section profile"],
            recommended_data_modalities=["dem"],
        )

    # 4. Land Cover Queries
    if any(k in q_low for k in ["land cover", "landcover", "land use", "lulc", "classes", "cropland vs forest", "tree cover fraction"]):
        return DataRequirementPlan(
            question=query,
            phenomenon="land_cover_mapping",
            modality=["land_cover"],
            temporal=True,
            spatial=True,
            resolution="medium",
            preferred_provider="copernicus",
            location=loc_cand,
            temporal_scope=temporal_dict,
            primary_domain="land_cover",
            user_intent="land_cover_mapping",
            analysis_requirements=["ESA WorldCover 10m classification"],
            supporting_requirements=["class area aggregation", "confidence matrix"],
            recommended_data_modalities=["land_cover"],
        )

    # 5. Soil Moisture Queries
    if any(k in q_low for k in ["soil moisture", "topsoil", "saturation degree", "drought severity", "soil water"]):
        return DataRequirementPlan(
            question=query,
            phenomenon="soil_moisture",
            modality=["soil", "sar"],
            temporal=True,
            spatial=True,
            resolution="medium",
            preferred_provider="copernicus",
            location=loc_cand,
            temporal_scope=temporal_dict,
            primary_domain="soil_moisture",
            user_intent="soil_moisture_analysis",
            analysis_requirements=["surface soil moisture retrieval"],
            supporting_requirements=["vegetation optical depth", "soil porosity"],
            recommended_data_modalities=["soil", "sar"],
        )

    # 6. Water Quality / Chlorophyll Queries
    if any(k in q_low for k in ["water quality", "turbidity", "chlorophyll", "algal bloom", "lake quality", "suspended sediment", "coastal water"]):
        return DataRequirementPlan(
            question=query,
            phenomenon="water_quality",
            modality=["water", "optical"],
            temporal=True,
            spatial=True,
            resolution="medium",
            preferred_provider="copernicus",
            location=loc_cand,
            temporal_scope=temporal_dict,
            primary_domain="water_quality",
            user_intent="water_quality_assessment",
            analysis_requirements=["NDWI", "chlorophyll concentration"],
            supporting_requirements=["turbidity index", "thermal sea surface"],
            recommended_data_modalities=["water", "optical"],
        )

    # 7. Urban Expansion / Built-up Queries
    if any(k in q_low for k in ["urban", "built-up", "built up", "city expansion", "sprawl", "impervious"]):
        return DataRequirementPlan(
            question=query,
            phenomenon="urban_expansion",
            modality=["optical"],
            temporal=True,
            spatial=True,
            resolution="high",
            preferred_provider="copernicus",
            location=loc_cand,
            temporal_scope=temporal_dict,
            primary_domain="urban",
            user_intent="urban_expansion_mapping",
            analysis_requirements=["NDBI built-up index", "impervious surface growth"],
            supporting_requirements=["vegetation buffer loss", "optical true-color reference"],
            recommended_data_modalities=["optical"],
        )

    # Default: Optical vegetation / land observation
    return DataRequirementPlan(
        question=query,
        phenomenon="vegetation_change",
        modality=["optical"],
        temporal=True,
        spatial=True,
        resolution="high",
        preferred_provider="copernicus",
        location=loc_cand,
        temporal_scope=temporal_dict,
        primary_domain="vegetation",
        user_intent="vegetation_monitoring",
        analysis_requirements=["temporal vegetation change", "NDVI trajectory"],
        supporting_requirements=["optical reference context", "boundary delineation"],
        recommended_data_modalities=["optical"],
    )


def rank_datasets(
    plan: DataRequirementPlan,
    candidate_datasets: Optional[List[DatasetMetadata]] = None,
    explicit_model: Optional[str] = None,
) -> List[Tuple[float, DatasetMetadata, str]]:
    """
    Ranks datasets using deterministic backend criteria:
    - Task & Phenomenon compatibility (40%)
    - Modality alignment (25%)
    - Spatial resolution appropriateness (15%)
    - Temporal coverage and cadence (10%)
    - Model compatibility (10%)
    Never allows hallucinated dataset IDs; only registered catalog entries are ranked.
    """
    candidates = candidate_datasets or list_datasets()
    scored_results: List[Tuple[float, DatasetMetadata, str]] = []

    for ds in candidates:
        score = 0.0
        reasons = []

        # 1. Phenomenon & Task Compatibility (0 - 40 pts)
        tasks = [t.lower() for t in (ds.tasks or []) + ds.supported_analyses]
        if plan.phenomenon == "atmospheric_pollution" and ds.modality == "atmospheric":
            score += 40.0
            reasons.append("Dedicated atmospheric chemistry sensor (Sentinel-5P)")
        elif plan.phenomenon == "flood_inundation" and ds.modality == "sar":
            score += 40.0
            reasons.append("All-weather cloud-penetrating C-band SAR radar backscatter")
        elif plan.phenomenon == "topography_elevation" and ds.modality == "dem":
            score += 40.0
            reasons.append("Authoritative global 30m digital surface model")
        elif plan.phenomenon == "land_cover_mapping" and ds.modality == "land_cover":
            score += 40.0
            reasons.append("Supervised 23-class FAO thematic land cover product")
        elif plan.phenomenon == "soil_moisture" and ds.modality == "soil":
            score += 40.0
            reasons.append("Microwave soil moisture saturation index")
        elif plan.phenomenon == "water_quality" and ds.modality == "water":
            score += 40.0
            reasons.append("Multi-spectral bio-optical water clarity & turbidity sensors")
        elif plan.phenomenon == "vegetation_change" and "vegetation" in tasks and ds.modality == "optical":
            score += 40.0
            reasons.append("High-resolution multi-spectral optical with red-edge & NIR bands")
        elif plan.phenomenon == "urban_expansion" and ("built_up" in tasks or "urban" in tasks):
            score += 35.0
            reasons.append("Multi-spectral SWIR/NIR bands for NDBI built-up differentiation")
        elif any(p in tasks for p in [plan.phenomenon]):
            score += 30.0
            reasons.append("Compatible secondary task capability")

        # 2. Modality Alignment (0 - 25 pts)
        if any(m.lower() == ds.modality.lower() for m in plan.modality):
            score += 25.0
            reasons.append(f"Direct modality match: {ds.modality.upper()}")
        elif "optical" in plan.modality and ds.modality in ["multispectral", "optical"]:
            score += 20.0
            reasons.append("Compatible multispectral optical modality")

        # 3. Spatial Resolution Appropriateness (0 - 15 pts)
        res_str = ds.spatial_resolution.lower()
        if plan.resolution == "high" and any(k in res_str for k in ["10m", "3m", "sub-meter", "0."]):
            score += 15.0
            reasons.append("High spatial GSD matching target scale")
        elif plan.resolution == "medium" and any(k in res_str for k in ["30m", "100m", "300m"]):
            score += 15.0
            reasons.append("Optimal regional synoptic resolution")
        elif plan.resolution == "coarse" and any(k in res_str for k in ["km"]):
            score += 15.0
            reasons.append("Broad atmospheric footprint")
        else:
            score += 5.0

        # 4. Temporal Coverage & Availability (0 - 10 pts)
        if plan.temporal and ds.temporal_resolution and "present" in ds.available_dates.lower():
            score += 10.0
            reasons.append("Active continuous operational constellation revisit")
        elif not plan.temporal and ds.modality == "dem":
            score += 10.0
            reasons.append("Static authoritative baseline elevation surface")
        else:
            score += 5.0

        # 5. User-Selected Model Requirements (0 - 10 pts)
        if explicit_model:
            exp_low = explicit_model.lower()
            if "prithvi" in exp_low and ds.dataset_id in ["sentinel-2-l2a", "sentinel-1-grd"]:
                score += 10.0
                reasons.append(f"Pre-trained NASA-IBM Prithvi foundation model weights available")
            elif "clay" in exp_low and ds.modality in ["optical", "multispectral"]:
                score += 10.0
                reasons.append("Clay multi-modal embedding compatibility")

        if score > 0:
            rationale_str = "; ".join(reasons)
            scored_results.append((ds, score, rationale_str))

    # Sort descending by score
    scored_results.sort(key=lambda x: x[1], reverse=True)
    return scored_results


def discover_active_layers_plan(
    *args,
    dataset: Optional[DatasetMetadata] = None,
    plan: Optional[DataRequirementPlan] = None,
    query: Optional[str] = None,
    active_asset: Optional[Dict[str, Any]] = None,
    aoi: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Once a dataset is selected (or inferred), discovers and binds its compatible visualization layers.
    Selects:
    - Primary Analysis layer (directly answering the question)
    - Reference layer (e.g. true color imagery or hillshade context)
    - Comparison layer (if multi-variable or change comparison is requested)
    Never activates irrelevant layers.
    """
    if args:
        if isinstance(args[0], str):
            query = args[0]
        elif isinstance(args[0], DataRequirementPlan):
            plan = args[0]
            query = plan.question
        elif isinstance(args[0], DatasetMetadata):
            dataset = args[0]
            if len(args) > 1 and isinstance(args[1], DataRequirementPlan):
                plan = args[1]
            if len(args) > 2 and isinstance(args[2], str):
                query = args[2]

    if not query:
        query = "Earth observation query"

    if active_asset:
        from app.dataset.adapters import adapter_registry
        user_adapter = adapter_registry.get_adapter("user_asset")
        dataset = user_adapter.register_user_asset_dataset(active_asset)
        plan = DataRequirementPlan(
            question=query,
            phenomenon="user_asset",
            modality=["custom", "multispectral"],
            preferred_provider="user_workspace",
        )

    if not plan:
        plan = infer_data_requirement_plan(query)

    if not dataset:
        ranked = rank_datasets(plan)
        dataset = ranked[0][0] if ranked else get_dataset("sentinel-2-l2a")

    available_layers = list_layers_for_dataset(dataset.dataset_id)
    if not available_layers:
        available_layers = search_layer_catalog("", category=dataset.modality)

    q_low = query.lower()
    primary_layer: Optional[LayerDefinition] = None
    reference_layer: Optional[LayerDefinition] = None
    comparison_layer: Optional[LayerDefinition] = None

    # 1. Identify Primary Analysis Layer
    phenom = (plan.phenomenon or "").lower()
    if phenom in ["atmospheric_pollution", "atmospheric", "air_pollution"]:
        primary_layer = next((l for l in available_layers if "no2" in l.layer_id), None)
    elif phenom in ["flood_inundation", "flood", "inundation"]:
        primary_layer = next((l for l in available_layers if "flood" in l.layer_id or "inundation" in l.layer_id), None)
        reference_layer = next((l for l in available_layers if "amplitude" in l.layer_id), None)
    elif phenom in ["topography_elevation", "topography", "elevation", "dem"]:
        primary_layer = next((l for l in available_layers if "surface" in l.layer_id or l.visualization_type == "3d_surface"), None)
        reference_layer = next((l for l in available_layers if "hillshade" in l.layer_id), None)
    elif phenom in ["land_cover_mapping", "land_cover", "lulc"]:
        primary_layer = next((l for l in available_layers if "discrete" in l.layer_id or l.category == "land_cover"), None)
        comparison_layer = next((l for l in available_layers if "fraction" in l.layer_id), None)
    elif phenom in ["soil_moisture", "soil"]:
        primary_layer = next((l for l in available_layers if "soil_moisture" in l.layer_id), None)
    elif phenom in ["water_quality", "water", "marine"]:
        primary_layer = next((l for l in available_layers if "turbidity" in l.layer_id or "chlorophyll" in l.layer_id), None)
        comparison_layer = next((l for l in available_layers if "chlorophyll" in l.layer_id and l.layer_id != (primary_layer.layer_id if primary_layer else "")), None)
    elif phenom in ["bitemporal_change", "change_detection"] or plan.user_intent == "bitemporal_change":
        primary_layer = next((l for l in available_layers if "diff" in l.layer_id or "change" in l.layer_id), None)
        if not primary_layer and available_layers:
            primary_layer = available_layers[0]
        reference_layer = next((l for l in available_layers if "rgb" in l.layer_id), None)
        comparison_layer = next((l for l in available_layers if "ndvi" in l.layer_id and l.layer_id != (primary_layer.layer_id if primary_layer else "")), None)
    elif phenom in ["urban_expansion", "urban", "built_up"]:
        primary_layer = next((l for l in available_layers if "ndbi" in l.layer_id or "urban" in l.layer_id), None)
        reference_layer = next((l for l in available_layers if "rgb" in l.layer_id), None)
    elif phenom == "user_asset":
        primary_layer = next((l for l in available_layers if "ndvi" in l.layer_id or "true_color" in l.layer_id), None)
        if not primary_layer and available_layers:
            primary_layer = available_layers[0]
    else:  # vegetation
        primary_layer = next((l for l in available_layers if "ndvi" in l.layer_id), None)
        reference_layer = next((l for l in available_layers if "rgb" in l.layer_id), None)

    # Fallbacks if specific layer not found
    if not primary_layer and available_layers:
        primary_layer = available_layers[0]

    # Check for comparative queries (e.g. "compare urban expansion and vegetation loss")
    if "compare" in q_low or ("vegetation" in q_low and "urban" in q_low):
        if not comparison_layer or (primary_layer and comparison_layer.layer_id == primary_layer.layer_id):
            if primary_layer and ("ndvi" in primary_layer.layer_id or "veg" in primary_layer.layer_id):
                comparison_layer = next(
                    (l for l in available_layers if ("ndbi" in l.layer_id or "urban" in l.layer_id or "swir" in l.layer_id) and l.layer_id != primary_layer.layer_id),
                    None,
                )
            else:
                comparison_layer = next(
                    (l for l in available_layers if ("ndvi" in l.layer_id or "veg" in l.layer_id) and (not primary_layer or l.layer_id != primary_layer.layer_id)),
                    None,
                )

    selected_layers: List[Dict[str, Any]] = []
    active_layer_defs: List[LayerDefinition] = []

    # Handle cross-modal Optical + SAR
    if plan.user_intent == "cross_modal_analysis" or (dataset.dataset_id == "sentinel-2-l2a" and "sar" in plan.modality):
        sar_layers = list_layers_for_dataset("sentinel-1-grd")
        if sar_layers and not comparison_layer:
            comparison_layer = sar_layers[0]

    # Handle Agricultural Investigation (Sentinel-2 + WorldCover + DEM)
    supporting_context_layers: List[Tuple[DatasetMetadata, LayerDefinition, str]] = []
    if plan.user_intent in ["agricultural_investigation", "agricultural investigation"] or "apple farm" in query.lower() or "farm" in query.lower():
        wc_ds = get_dataset("worldcover-10m")
        if wc_ds:
            wc_layers = list_layers_for_dataset("worldcover-10m")
            if wc_layers:
                supporting_context_layers.append((wc_ds, wc_layers[0], "Land-cover classification and cropland context"))
        dem_ds = get_dataset("copernicus-dem-30m")
        if dem_ds:
            dem_layers = list_layers_for_dataset("copernicus-dem-30m")
            if dem_layers:
                supporting_context_layers.append((dem_ds, dem_layers[0], "Copernicus DEM terrain and slope drainage profile"))

    if primary_layer:
        p_def = primary_layer.model_copy()
        p_def.role = "primary_analysis"
        active_layer_defs.append(p_def)
        selected_layers.append({
            "layer_id": primary_layer.layer_id,
            "dataset_id": primary_layer.dataset_id,
            "title": primary_layer.name,
            "role": "primary_analysis",
            "purpose": f"Primary analytical visualization answering '{query}' via {dataset.name}.",
            "visualization_type": primary_layer.visualization_type,
            "units": primary_layer.units,
            "legend": primary_layer.legend,
            "provenance": {
                "dataset_id": dataset.dataset_id,
                "provider": dataset.provider,
                "sensor": dataset.sensor,
            },
        })

    if comparison_layer and comparison_layer.layer_id != (primary_layer.layer_id if primary_layer else ""):
        c_def = comparison_layer.model_copy()
        c_def.role = "comparison"
        active_layer_defs.append(c_def)
        c_ds_id = comparison_layer.dataset_id
        c_ds = get_dataset(c_ds_id) or dataset
        selected_layers.append({
            "layer_id": comparison_layer.layer_id,
            "dataset_id": comparison_layer.dataset_id,
            "title": comparison_layer.name,
            "role": "comparison",
            "purpose": f"Comparative layer ({c_ds.name}) providing cross-modal or multi-index contrast.",
            "visualization_type": comparison_layer.visualization_type,
            "units": comparison_layer.units,
            "legend": comparison_layer.legend,
            "provenance": {
                "dataset_id": c_ds.dataset_id,
                "provider": c_ds.provider,
                "sensor": c_ds.sensor,
            },
        })

    for s_ds, s_layer, s_purpose in supporting_context_layers:
        if s_layer.layer_id not in [l["layer_id"] for l in selected_layers]:
            s_def = s_layer.model_copy()
            s_def.role = "reference"
            active_layer_defs.append(s_def)
            selected_layers.append({
                "layer_id": s_layer.layer_id,
                "dataset_id": s_layer.dataset_id,
                "title": s_layer.name,
                "role": "reference",
                "purpose": s_purpose,
                "visualization_type": s_layer.visualization_type,
                "units": s_layer.units,
                "legend": s_layer.legend,
                "provenance": {
                    "dataset_id": s_ds.dataset_id,
                    "provider": s_ds.provider,
                    "sensor": s_ds.sensor,
                },
            })

    if reference_layer and reference_layer.layer_id not in [l["layer_id"] for l in selected_layers]:
        r_def = reference_layer.model_copy()
        r_def.role = "reference"
        active_layer_defs.append(r_def)
        selected_layers.append({
            "layer_id": reference_layer.layer_id,
            "dataset_id": reference_layer.dataset_id,
            "title": reference_layer.name,
            "role": "reference",
            "purpose": f"True-color or physical surface context for visual orientation.",
            "visualization_type": reference_layer.visualization_type,
            "units": reference_layer.units,
            "legend": reference_layer.legend,
            "provenance": {
                "dataset_id": dataset.dataset_id,
                "provider": dataset.provider,
                "sensor": dataset.sensor,
            },
        })

    return {
        "dataset": dataset,
        "selected_dataset": dataset,
        "primary_layer": primary_layer,
        "reference_layer": reference_layer,
        "comparison_layer": comparison_layer,
        "active_layers": active_layer_defs,
        "selected_active_layers": selected_layers,
        "why_this_data": f"Selected {dataset.name} ({dataset.provider}) because its {dataset.modality} telemetry directly isolates {plan.phenomenon.replace('_', ' ')}.",
        "why_this_layer": f"Activated {primary_layer.name if primary_layer else 'thematic layer'} as primary analytical view based on physical spectral sensitivity.",
    }
