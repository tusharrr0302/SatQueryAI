import json
import logging
import uuid
import asyncio
from typing import Dict, Any, Optional
from langchain_groq import ChatGroq
from app.config import settings
from app.dataset.registry import DATASET_REGISTRY
from app.models.registry import MODEL_REGISTRY
from app.models.manager import model_manager
from app.services.scenario_adapter import scenario_to_normalized_result, _generate_surface_grid, _build_audit_trace
from app.services.visualization_registry import select_visualizations, build_data_layers
from app.services.request_validator import RequestValidator
from app.schemas.normalized_result import (
    NormalizedResult,
    AOIInfo,
    Coordinates,
    MetricItem,
    TimeSeriesPoint,
    VisualizationSpec,
    Provenance,
)
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
    ComparisonPeriod,
)
from app.graph.state import AgentState

logger = logging.getLogger(__name__)


# --- Node 1: Resolve Query Source ---
def resolve_query_source(state: AgentState) -> Dict[str, Any]:
    query = state.get("user_query", "")
    location_hint = state.get("location_hint")
    print(f"\n[CHAT]\nQuery: {query}")

    # If user has an active uploaded asset, always use user_data / live execution
    if state.get("active_asset"):
        return {"matched_scenario": None, "source": "user_data"}

    if settings.MODEL_MODE != "live_only":
        try:
            from app.services.scenario_matcher import match_scenario
            matched = match_scenario(query, location_hint=location_hint)
            if matched:
                print(f"[SCENARIO]\nMatched: {matched.get('id', 'YES')}")
                return {"matched_scenario": matched, "source": "mock"}
        except Exception as e:
            logger.warning(f"Scenario matcher error: {e}")

    print("[SCENARIO]\nMatched: DISABLED (live data required)")
    return {"matched_scenario": None, "source": "live"}


# --- Node 2: Load Matched Scenario (Path A) ---
def load_mock_scenario(state: AgentState) -> Dict[str, Any]:
    matched = state.get("matched_scenario")
    query = state.get("user_query", "")
    norm = scenario_to_normalized_result(matched, query)
    
    model_name = norm.provenance.model_name
    datasets_str = ", ".join(norm.provenance.dataset_ids)
    operation = norm.analysis_type
    print(f"[TOOL]\nModel: {model_name}\nDatasets: {datasets_str}\nOperation: {operation}")
    print(f"[RESULT]\nSource: mock\nResult generated: YES")
    
    return {
        "normalized_result": norm.model_dump(),
        "source": "mock",
        "fallback": False,
    }



# --- Node 3: Understand Query (Path B - Unknown Queries) ---
def _generate_fallback_request(query: str, location_hint: Optional[str] = None) -> AnalysisRequest:
    import re
    from datetime import date
    years = int(re.search(r"last\s+(\d+)\s+years?", query.lower()).group(1)) if re.search(r"last\s+(\d+)\s+years?", query.lower()) else 2
    location = next((name for name in ["Delhi", "Mumbai", "Bengaluru", "Bangalore", "Chennai", "Kolkata", "Hyderabad", "Pune"] if name.lower() in query.lower()), None)
    if not location:
        match = re.search(r"(?:in|around|near)\s+([A-Za-z][A-Za-z\s-]*?)(?:\s+(?:over|during|between|using|for)\b|$)", query, re.IGNORECASE)
        location = match.group(1).strip() if match else (location_hint or query)
    end_year = date.today().year
    return AnalysisRequest(
        query=query,
        intent=Intent(
            primary_task="multispectral_observation",
            domain="earth_observation",
            question_type="general_query",
            spatial_scope="regional",
            temporal_scope=TemporalScope(start=str(end_year - years), end=str(end_year), comparison_strategy="annual"),
        ),
        aoi=AOI(type="Polygon", name=location, country=None),
        data_requirements=DataRequirements(
            modalities=["optical"],
            datasets=["sentinel-2"],
            temporal_resolution="monthly",
            cloud_constraint="<20%",
            spatial_resolution="10m",
        ),
        model_selection=ModelSelection(
            model="prithvi-eo-2.0",
            reason="Foundation model for multispectral Earth observation analysis",
        ),
        analysis=Analysis(
            operation="observation",
            comparison_periods=[],
            target_classes=[],
        ),
        outputs=Outputs(
            visualizations=["3D Surface", "Time Series"],
            metrics=["Observation Confidence"],
            explanation=True,
            confidence=True,
        ),
        execution=Execution(priority="accuracy", allow_mock_fallback=False),
    )


def understand_query(state: AgentState) -> Dict[str, Any]:
    query = state.get("user_query", "")
    active_asset = state.get("active_asset")
    recent_messages = state.get("recent_messages") or []
    previous_result = state.get("previous_result")
    location_hint = state.get("location_hint")
    print(f"[SatQuery] CALLING GPT-OSS 120B for planning: {query}")

    context_str = ""
    if recent_messages:
        turns_summary = []
        for m in recent_messages[-4:]:
            role = m.get("role", "user").capitalize()
            content = m.get("content", "")
            content_snippet = content[:160] + ("..." if len(content) > 160 else "")
            turns_summary.append(f"- {role}: {content_snippet}")
        context_str += "RECENT CONVERSATION TURNS:\n" + "\n".join(turns_summary) + "\n\n"

    if previous_result:
        prev_aoi = previous_result.get("aoi", {}).get("name") or location_hint or "Unknown"
        prev_center = previous_result.get("aoi", {}).get("center", {})
        prev_lat = prev_center.get("latitude")
        prev_lon = prev_center.get("longitude")
        prev_type = previous_result.get("analysis_type", "")
        context_str += (
            f"ACTIVE CONVERSATION CONTEXT:\n"
            f"- Active AOI / Location: {prev_aoi}"
            + (f" ({prev_lat}°N, {prev_lon}°E)\n" if prev_lat is not None else "\n")
            + f"- Previous Analysis: {prev_type}\n"
            + "Note: If the current user request is a follow-up (e.g. 'what about the southern region?', 'compare with urban expansion', 'show this on the globe'), resolve it within this contextual location and previous findings.\n\n"
        )

    if settings.GROQ_API_KEY:
        try:
            llm = ChatGroq(
                model=settings.GROQ_MODEL,
                api_key=settings.GROQ_API_KEY,
                temperature=0,
            )
            structured_llm = llm.with_structured_output(AnalysisRequest)

            asset_context_str = ""
            if active_asset:
                asset_context_str = f"""
ACTIVE USER UPLOADED DATASET:
{json.dumps(active_asset.get('profile', {}), indent=2)}
Note: If the user refers to 'this image' or their data, tailor the request to this dataset.
"""

            prompt = f"""You are SatQuery AI's remote sensing query analysis engine.
Convert the user request into a standardized AnalysisRequest.

AVAILABLE MODELS:
{json.dumps(MODEL_REGISTRY, indent=2)}

AVAILABLE DATASETS:
{json.dumps(DATASET_REGISTRY, indent=2)}
{asset_context_str}
{context_str}Rules:
1. Select models and datasets ONLY from the registries (or reference user uploaded data).
2. Never invent a model or dataset ID.
3. Identify the target location cleanly if present (e.g. Kathmandu, Himalayas, Greenland, or the contextual location if this is a follow-up).
4. Never fabricate satellite measurements.

User request: {query}
"""
            result = structured_llm.invoke(prompt)
            print("[LLM]\nAnalysis request generated: YES")
            return {"analysis_request": result.model_dump()}
        except Exception as exc:
            logger.warning(f"Groq structured output failed ({exc}); trying recovery.")
            err_msg = str(exc)
            if "failed_generation" in err_msg:
                try:
                    import re, ast
                    m = re.search(r"'failed_generation':\s*('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")", err_msg)
                    if m:
                        raw = ast.literal_eval(m.group(1))
                        if isinstance(raw, str):
                            fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
                            if fence_match:
                                raw_str = fence_match.group(1)
                            else:
                                brace_match = re.search(r"(\{[\s\S]*\})", raw)
                                raw_str = brace_match.group(1) if brace_match else raw
                            parsed = json.loads(raw_str.strip())
                        else:
                            parsed = raw

                        if isinstance(parsed, dict) and "arguments" in parsed:
                            payload = parsed["arguments"]
                            if isinstance(payload, str):
                                payload = json.loads(payload)
                        else:
                            payload = parsed

                        if isinstance(payload, dict) and "analysis" in payload and isinstance(payload["analysis"], dict):
                            if payload["analysis"].get("target_classes") is None:
                                payload["analysis"]["target_classes"] = []
                            if payload["analysis"].get("comparison_periods") is None:
                                payload["analysis"]["comparison_periods"] = []

                        recovered_req = AnalysisRequest.model_validate(payload)
                        print("[LLM]\nAnalysis request generated: YES")
                        return {"analysis_request": recovered_req.model_dump()}
                except Exception as rec_err:
                    logger.warning(f"Failed to recover generation: {rec_err}")

    fallback_req = _generate_fallback_request(query, location_hint=location_hint)
    print("[LLM]\nAnalysis request generated: NO (fallback)")
    return {"analysis_request": fallback_req.model_dump()}


# --- Node 4: Validate Request ---
def validate_request(state: AgentState) -> Dict[str, Any]:
    req = state.get("analysis_request") or {}
    try:
        RequestValidator.validate_analysis_request(req)
        print("[SatQuery] VALIDATION PASSED")
    except Exception as e:
        logger.warning(f"Request validation warning: {e}")
        print(f"[SatQuery] VALIDATION WARNING: {e}")
    return {}


# --- Node 5: Execute Unknown Analysis ---
async def execute_unknown_analysis(state: AgentState) -> Dict[str, Any]:
    req = state.get("analysis_request") or {}
    query = state.get("user_query", "")
    active_asset = state.get("active_asset")

    # If user is asking about an uploaded dataset
    if active_asset and any(k in query.lower() for k in ["this image", "this data", "what is this", "what is", "dataset", "band", "show", "vegetation", "image"]):
        prof = active_asset.get("profile", {})
        dims = prof.get("dimensions", {})
        bounds = prof.get("bounds") or [0, 0, 0, 0]
        center = prof.get("center") or {
            "latitude": (bounds[1] + bounds[3]) / 2.0 if len(bounds) == 4 else 0.0,
            "longitude": (bounds[0] + bounds[2]) / 2.0 if len(bounds) == 4 else 0.0,
        }
        preview_url = active_asset.get("preview_url") or f"/api/data/assets/{active_asset.get('asset_id')}/preview"

        metrics_items = [
            MetricItem(label="Raster Dimensions", value=f"{dims.get('width', 0):,} × {dims.get('height', 0):,} px", unit="px"),
            MetricItem(label="Spectral Bands", value=str(dims.get("bands", 0)), unit="bands"),
            MetricItem(label="Coordinate Reference", value=str(prof.get("crs") or "Unprojected"), unit="CRS"),
        ]
        if prof.get("resolution"):
            res = prof.get("resolution")
            metrics_items.append(MetricItem(label="Spatial Resolution", value=f"{res[0]}m × {res[1]}m", unit="m"))
        if prof.get("sensor"):
            metrics_items.append(MetricItem(label="Verified Sensor", value=str(prof.get("sensor")), unit="Sensor"))

        vis_specs = [
            {
                "id": "user_raster_preview",
                "type": "raster",
                "renderer": "raster",
                "title": f"Raster Preview: {active_asset.get('filename')}",
                "url": preview_url,
                "data": prof.get("bands", []),
            }
        ]

        norm = NormalizedResult(
            query=query,
            analysis_type="data_inspection",
            aoi=AOIInfo(
                id=f"aoi_{active_asset.get('asset_id')}",
                name=active_asset.get("filename", "User Dataset"),
                type="Polygon",
                center=Coordinates(latitude=center.get("latitude", 0.0), longitude=center.get("longitude", 0.0)),
                area_km2=round(abs(bounds[2] - bounds[0]) * abs(bounds[3] - bounds[1]) * 111.0 * 111.0, 1) if len(bounds) == 4 else 0.0,
                bbox=bounds,
                polygon=[
                    [bounds[0], bounds[1]],
                    [bounds[2], bounds[1]],
                    [bounds[2], bounds[3]],
                    [bounds[0], bounds[3]],
                    [bounds[0], bounds[1]],
                ] if len(bounds) == 4 else [],
            ),
            aoi_bbox=bounds,
            location={"name": active_asset.get("filename"), "latitude": center.get("latitude", 0.0), "longitude": center.get("longitude", 0.0)},
            provenance=Provenance(
                source="user_data",
                fallback=False,
                model_id="deterministic_raster_inspector",
                model_name="Deterministic Rasterio Engine",
                dataset_ids=[active_asset.get("filename")],
                acquisition_dates=prof.get("acquisition_date") or "N/A",
                pipeline="Rasterio / GDAL Deterministic Analysis",
            ),
            key_finding=f"{active_asset.get('filename')} is a {dims.get('bands', 1)}-band {prof.get('format', 'GeoTIFF')} raster ({prof.get('crs', 'Unprojected')}).",
            scientific_explanation=f"Deterministic inspection confirms {dims.get('width', 0):,} × {dims.get('height', 0):,} pixel array across {dims.get('bands', 1)} spectral bands. " + (" ".join(prof.get("limitations", [])) if prof.get("limitations") else ""),
            metrics=metrics_items,
            before_image_url=preview_url,
            visualizations=vis_specs,
        )

        return {
            "normalized_result": norm.model_dump(),
            "source": "user_data",
            "fallback": False,
        }

    model_id = req.get("model_selection", {}).get("model", "prithvi-eo-2.0")
    model_name = MODEL_REGISTRY.get(model_id, {}).get("name", model_id)
    raw_datasets = req.get("data_requirements", {}).get("datasets") or ["sentinel-2"]
    dataset_ids = [d for d in raw_datasets if d and str(d).strip()] or ["sentinel-2"]
    operation = req.get("analysis", {}).get("operation", "observation_planning")

    datasets_str = ", ".join(dataset_ids)
    print(f"[TOOL]\nModel: {model_name}\nDatasets: {datasets_str}\nOperation: {operation}")

    norm = await asyncio.to_thread(
        model_manager.execute,
        model_id=model_id,
        query=query,
        request=req,
    )
    print(f"[RESULT]\nSource: {norm.provenance.source}\nResult generated: YES")
    return {
        "normalized_result": norm.model_dump(),
        "source": norm.provenance.source,
        "fallback": norm.provenance.fallback,
    }



# --- Markdown Fallback Helpers ---
def _format_markdown_fallback(expected_answer: str, norm_dict: Dict[str, Any]) -> str:
    aoi = norm_dict.get("aoi", {})
    aoi_name = aoi.get("name", "Target Region")
    metrics = norm_dict.get("metrics", [])
    prov = norm_dict.get("provenance", {})
    model_name = prov.get("model_name", "Prithvi-EO-2.0")
    datasets = [d for d in prov.get("dataset_ids", []) if d and str(d).strip()] or ["sentinel-2"]
    ds_str = ", ".join(d.upper() if len(d) <= 3 else d.title() for d in datasets)
    acq_dates = prov.get("acquisition_dates") or "the observed temporal window"
    visualizations = norm_dict.get("visualizations", [])
    vis_desc = visualizations[0].get("description", "quantitative remote sensing observation telemetry") if visualizations else "spatial and statistical Earth observation metrics"

    md = f"### Summary\n{expected_answer}\n\n"

    md += "### Key Findings\n"
    if metrics:
        for m in metrics[:5]:
            val = m.get("value", "")
            lbl = m.get("label", "")
            chg = f" ({m.get('change')})" if m.get("change") else ""
            unit = f" {m.get('unit')}" if m.get("unit") and not str(val).endswith(m.get("unit")) else ""
            md += f"- **{lbl}**: **{val}{unit}**{chg}\n"
    else:
        md += f"- Surface alterations confirmed across the {aoi_name} area of interest.\n"
    md += "\n"

    md += f"### Spatial / Temporal Interpretation\nAnalysis across {aoi_name} reveals localized surface transformations during {acq_dates}. The delineated footprint highlights concentrated boundaries of bio-physical change relative to surrounding baseline environments.\n\n"

    md += f"### Data & Method\nObservation metrics derived from **{ds_str}** telemetry analyzed via the specialist **{model_name}** remote sensing model.\n\n"

    md += f"### Visualization\nThe primary chart and interactive 3D map delineate {vis_desc}."
    return md.strip()


def _format_unknown_markdown_fallback(query: str, norm_dict: Dict[str, Any]) -> str:
    aoi = norm_dict.get("aoi", {})
    aoi_name = aoi.get("name") or query
    prov = norm_dict.get("provenance", {})
    model_name = prov.get("model_name", "Prithvi-EO-2.0")
    datasets = [d for d in prov.get("dataset_ids", []) if d and str(d).strip()] or ["sentinel-2"]
    ds_str = ", ".join(d.upper() if len(d) <= 3 else d.title() for d in datasets)
    explanation = norm_dict.get("scientific_explanation") or norm_dict.get("key_finding", "")

    md = f"### Summary\n{explanation}\n\n"

    md += "### Key Findings\n"
    md += f"- **Target AOI**: {aoi_name}\n"
    md += f"- **Recommended Modality**: Multispectral optical and synthetic aperture radar\n"
    md += f"- **Target Constellation**: **{ds_str}**\n\n"

    md += f"### Spatial / Temporal Interpretation\nMulti-temporal baseline acquisitions over {aoi_name} provide optimal spatial resolution for environmental classification and bi-temporal anomaly detection.\n\n"

    md += f"### Data & Method\nWorkflow orchestrated for **{ds_str}** sensors utilizing the **{model_name}** foundation architecture.\n\n"

    md += "### Visualization\nThe visualization panel displays geospatial boundary outlines and preliminary sensor telemetry."
    return md.strip()


# --- Node 8: Generate Visualizations ---
def generate_visualizations(state: AgentState) -> Dict[str, Any]:
    norm = state.get("normalized_result") or {}
    query = state.get("user_query", "")
    matched = state.get("matched_scenario")
    source = state.get("source", "mock")

    # Authoritative visualizations from NormalizedResult if already present
    visualizations = norm.get("visualizations") or []
    if not visualizations and source == "mock":
        raw_mock = matched.get("mock_data", {}) if isinstance(matched, dict) else {}
        visualizations = select_visualizations(
            query=query,
            scenario=matched,
            mock_data=raw_mock,
            metrics=norm.get("metrics"),
            time_series=norm.get("time_series"),
        )


    vis_ids = [v.get("id", v.get("type", "unknown")) for v in visualizations]
    vis_str = " / ".join(vis_ids) if vis_ids else "NONE"
    print(f"[VISUALIZATION]\nSelected: {vis_str}")

    norm["visualizations"] = visualizations
    return {"visualizations": visualizations, "normalized_result": norm}


# --- Node 7: Generate Globe Actions & Data Layers ---
def generate_globe_actions(state: AgentState) -> Dict[str, Any]:
    norm = state.get("normalized_result") or {}
    query = state.get("user_query", "")
    active_asset = state.get("active_asset")
    aoi = norm.get("aoi", {})
    center = aoi.get("center", {})
    lat = center.get("latitude", 28.6139)
    lon = center.get("longitude", 77.2090)
    name = aoi.get("name", "Target Region")
    bbox = aoi.get("bbox", [])
    polygon = aoi.get("polygon", [])

    # Authoritative Backend Layer Registry (Phase 3)
    user_id = state.get("user_id")
    layers = build_data_layers(norm, query=query, user_id=user_id, active_asset=active_asset)
    norm["layers"] = [l.model_dump() for l in layers]

    actions = [
        {
            "type": "fly_to",
            "params": {
                "destination": [lon, lat, 450000],
                "name": name,
            },
        },
        {
            "type": "add_marker",
            "params": {
                "coordinates": [lon, lat],
                "title": name,
            },
        },
    ]

    if polygon:
        actions.append({
            "type": "highlight_aoi",
            "params": {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": polygon,
                },
                "name": name,
            },
        })

    # Add Cesium spatial overlay actions if present in visualizations
    for v in norm.get("visualizations", []):
        if v.get("renderer") == "cesium":
            v_type = v.get("type", "spatial_overlay")
            layer_info = v.get("layer", {})
            action_type = f"add_{v_type}" if not v_type.startswith("add_") else v_type
            actions.append({
                "type": action_type,
                "params": {
                    "name": v.get("title", name),
                    "layer_type": v_type,
                    "bbox": layer_info.get("bbox") or bbox,
                    "polygon": polygon,
                    "color_hint": layer_info.get("color_hint", "emerald"),
                    "metric": layer_info.get("metric", {}),
                    "opacity": layer_info.get("opacity", 0.85),
                },
            })

    return {
        "globe_actions": actions,
        "layers": norm["layers"],
        "normalized_result": norm,
    }


# --- Node 6: Generate Final Response ---
def generate_final_response(state: AgentState) -> Dict[str, Any]:
    query = state.get("user_query", "")
    norm_dict = state.get("normalized_result") or {}
    visualizations = state.get("visualizations") or []
    globe_actions = state.get("globe_actions") or []
    matched = state.get("matched_scenario")
    source = state.get("source", "mock")

    context = {
        "user_query": query,
        "normalized_result": norm_dict,
        "visualizations": visualizations,
        "globe_actions": globe_actions,
    }

    system_prompt = """You are SatQuery AI's scientific Earth observation intelligence engine.

Answer the user's question using ONLY the authoritative analysis result supplied by the backend.
The backend result is the single source of truth.

STRICT PRINCIPLES:
1. Do not invent satellite observations, measurements, coordinates, dates, percentages, areas, datasets, models, or scientific conclusions.
2. Do not modify numerical values, coordinates, or dates.
3. NEVER mention internal terms like "mock", "demo data", "fallback", "hardcoded", "scenario matcher", "LangGraph", "pipeline", or "tool executor".
4. Target approximately 150–250 words for a substantive, polished scientific analysis.

MANDATORY STRUCTURE (Use exact Markdown headers):
### Summary
2–4 authoritative sentences summarizing the primary observation and headline change.

### Key Findings
3–5 bullet points highlighting primary metrics with bold values and units (e.g. - **Vegetation Loss**: **143.8 km²** (-18.7% decline)).

### Spatial / Temporal Interpretation
A concise explanation of the geographic extent, spatial concentration of change, and temporal progression across observed epochs.

### Data & Method
Identify the specific sensor platforms (e.g. **Sentinel-2 MSI**, **Sentinel-1 C-SAR**, **Landsat-8**) and specialist foundation model (e.g. **Prithvi-EO-2.0**, **TerraFM**) utilized.

### Visualization
One sentence explaining what the interactive chart and geospatial map demonstrate to the user.
"""

    if norm_dict.get("provenance", {}).get("source") == "user_data":
        system_prompt = """You are SatQuery AI's scientific Earth observation intelligence engine.
Answer the user's inquiry regarding their uploaded Earth observation dataset using ONLY the authoritative analysis result supplied by the backend.

STRICT PRINCIPLES:
1. Do not invent satellite sensors, measurements, coordinates, dates, or spectral bands.
2. If sensor identity is stated as unverified, clearly report: "Sensor identity could not be verified from available metadata." NEVER hallucinate a sensor name.
3. Target approximately 150–250 words for a substantive, polished scientific analysis.

MANDATORY STRUCTURE (Use exact Markdown headers):
### Dataset Overview
2–3 sentences summarizing the raster format, pixel dimensions, spectral bands, and verified sensor / platform status.

### Spatial Properties
Bullet points detailing spatial resolution, coordinate reference system (CRS), and geographic bounding box coverage.

### Available Analysis
Bullet points highlighting valid remote-sensing workflows feasible with this band configuration (e.g. vegetation indices, spectral profile analysis, false-color composites).

### Limitations
State any limitations present in the metadata (e.g. unverified sensor, missing CRS or acquisition date).
"""

    user_payload = f"""User Query: {query}

Authoritative Result Data:
{json.dumps(context, indent=2)}
"""

    if settings.GROQ_API_KEY:
        try:
            llm = ChatGroq(
                model=settings.GROQ_MODEL,
                api_key=settings.GROQ_API_KEY,
                temperature=0.1,
            )
            resp = llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ])
            answer = resp.content.strip()
            print("[LLM FINAL]\nGPT-OSS final response generated: YES")
            return {"final_answer": answer, "final_response": answer}
        except Exception as exc:
            logger.warning(f"Groq final response generation failed ({exc}); using fallback.")

    # Resilient structured markdown fallback
    if norm_dict.get("provenance", {}).get("source") == "user_data":
        key_finding = norm_dict.get("key_finding", "Uploaded raster dataset inspected.")
        metrics = norm_dict.get("metrics", [])
        answer = f"### Dataset Overview\n{key_finding}\n\n### Spatial Properties\n"
        for m in metrics:
            answer += f"- **{m.get('label')}**: **{m.get('value')}**\n"
        answer += "\n### Available Analysis\n- **Spectral & Vegetation Indices**: Calculate NDVI and spectral band ratios.\n- **Surface Masking**: Extract thematic land-cover boundaries.\n"
        answer += "\n### Limitations\n- Sensor identity could not be verified from available metadata.\n"
    elif matched and matched.get("expected_answer"):
        answer = _format_markdown_fallback(matched.get("expected_answer", ""), norm_dict)
    else:
        answer = _format_unknown_markdown_fallback(query, norm_dict)

    print("[LLM FINAL]\nGPT-OSS final response generated: NO (fallback)")
    return {"final_answer": answer, "final_response": answer}