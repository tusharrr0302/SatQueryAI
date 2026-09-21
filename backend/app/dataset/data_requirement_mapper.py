"""
backend/app/dataset/data_requirement_mapper.py
─────────────────────────────────────────────────────────────────────────────
Deterministic backend mapper:
  AnalysisRequest + ToolPlan + Resolved AOI ──> DataRequirement

GPT-OSS does NOT formulate raw satellite search queries or URLs.
This mapper translates high-level user intent & tool planning constraints into
an authoritative, validated DataRequirement object.
"""
from typing import Optional, Dict, Any, List
import datetime
import re

from app.schemas.analysis_request import AnalysisRequest, ToolPlan
from app.schemas.data_requirement import DataRequirement, TemporalWindow, AcquisitionStrategy


def map_analysis_request_to_requirement(
    request: AnalysisRequest,
    tool_plan: Optional[ToolPlan] = None,
    aoi_info: Optional[Dict[str, Any]] = None,
) -> DataRequirement:
    """
    Deterministically derives a structured DataRequirement from an AnalysisRequest,
    ToolPlan, and resolved AOI geometry.
    """
    task = request.intent.primary_task.lower().strip()
    req_modalities = [m.lower().strip() for m in request.data_requirements.modalities]

    # Incorporate modalities required by ToolPlan if present
    if tool_plan and tool_plan.requires_modalities:
        for m in tool_plan.requires_modalities:
            if m not in req_modalities:
                req_modalities.append(m)

    has_sar = "sar" in req_modalities
    has_optical = "optical" in req_modalities or "multispectral" in req_modalities

    # 1. Determine Task Intent and Modalities
    q_lower = request.query.lower() if request.query else ""
    is_sar_requested = any(k in q_lower for k in ["sar", "radar", "sentinel-1", "backscatter", "vv", "vh"])
    if is_sar_requested and "sar" not in req_modalities:
        req_modalities.append("sar")

    has_sar = "sar" in req_modalities
    has_optical = "optical" in req_modalities or "multispectral" in req_modalities or (not has_sar)

    # 2. Determine Temporal Scope and Duration
    cur_year = datetime.date.today().year
    t_scope = request.intent.temporal_scope
    start_year_str = t_scope.start if t_scope and t_scope.start else None
    end_year_str = t_scope.end if t_scope and t_scope.end else None
    rel_period = t_scope.relative_period if t_scope else None

    # Check query directly for explicit multi-year patterns e.g. "from 2016 to 2026", "2016-2026"
    m_range = re.search(r'\b(20\d{2})\s*(?:to|[-–/])\s*(20\d{2})\b', q_lower)
    if m_range:
        start_year_str = m_range.group(1)
        end_year_str = m_range.group(2)
    elif not start_year_str:
        # Check for "last N years", "past N years", "decade"
        m_years = re.search(r'\b(?:last|past)\s+(\d+)\s+years?\b', q_lower)
        if m_years:
            diff = int(m_years.group(1))
            start_year_str = str(cur_year - diff)
            end_year_str = str(cur_year)
            rel_period = f"{diff}_years"
        elif "decade" in q_lower:
            start_year_str = str(cur_year - 10)
            end_year_str = str(cur_year)
            rel_period = "10_years"
        elif any(k in q_lower for k in ["last year", "past year", "over the last year"]):
            start_year_str = str(cur_year - 1)
            end_year_str = str(cur_year)
            rel_period = "1_year"
        elif rel_period:
            m = re.search(r"(\d+)", str(rel_period))
            if m:
                diff = int(m.group(1))
                start_year_str = str(cur_year - diff)
                end_year_str = str(cur_year)

    if not start_year_str:
        start_year_str = str(cur_year - 2)
    if not end_year_str:
        end_year_str = str(cur_year)

    # Clean 4-digit years
    s_yr = int(start_year_str[:4]) if start_year_str[:4].isdigit() else cur_year - 2
    e_yr = int(end_year_str[:4]) if end_year_str[:4].isdigit() else cur_year
    if s_yr > e_yr:
        s_yr, e_yr = e_yr, s_yr
    duration_years = max(1, e_yr - s_yr)

    # 3. Determine Acquisition Strategy and Temporal Frequency
    is_paired_compare = (
        task in ("image_comparison", "bitemporal_change")
        or "compare" in q_lower
        or "before and after" in q_lower
    )
    is_temporal_intent = (
        task in ("temporal_change_detection", "land_cover_change", "vegetation_analysis", "urban_change")
        or (tool_plan and tool_plan.tool in ("detect_change", "analyze_multitemporal"))
        or any(k in q_lower for k in ["over time", "trend", "change", "timeline", "years", "decade", "multitemporal", "series"])
        or (rel_period is not None)
        or bool(m_range)
    )

    if (has_sar and has_optical and not is_sar_requested) or task in ("flood_analysis", "sar_optical_analysis", "cross_modal_analysis"):
        strategy: AcquisitionStrategy = "sar_optical_pair"
        co_reg = True
        temp_frequency = "paired"
        temp_count = None
    elif is_paired_compare and duration_years <= 2:
        strategy = "paired"
        co_reg = True
        temp_frequency = "paired"
        temp_count = 2
    elif is_temporal_intent:
        strategy = "temporal"
        co_reg = False
        op_name = (getattr(request.analysis, "operation", "") or "").lower() if getattr(request, "analysis", None) else ""
        model_name = (getattr(request.model_selection, "model", "") or "").lower() if getattr(request, "model_selection", None) else ""
        tool_name = (getattr(tool_plan, "tool", "") or "").lower() if tool_plan else ""

        is_prithvi_change = (
            op_name in ("detect_change", "change_detection")
            or (tool_name in ("detect_change", "analyze_multitemporal") and task in ("temporal_change_detection", "urban_change"))
            or ("prithvi" in model_name and task in ("temporal_change_detection", "urban_change"))
        )

        if is_prithvi_change:
            temp_frequency = "prithvi_stack"
            temp_count = 4
        elif duration_years >= 3:
            temp_frequency = "annual"
            temp_count = (e_yr - s_yr) + 1  # Full annual series (e.g. 11 for 2016..2026)
        elif tool_plan and tool_plan.tool in ("detect_change", "analyze_multitemporal"):
            temp_frequency = "prithvi_stack"
            temp_count = 4
        elif duration_years >= 1:
            temp_frequency = "quarterly"
            temp_count = duration_years * 4
        else:
            temp_frequency = "monthly"
            temp_count = 6
    else:
        strategy = "single"
        co_reg = False
        temp_frequency = "single"
        temp_count = 1

    # 4. Determine Required Bands
    required_bands: List[str] = []
    if has_optical:
        required_bands.extend(["B02", "B03", "B04", "B08"])
    if has_sar:
        required_bands.extend(["VV", "VH"])

    # Format dates as YYYY-MM-DD
    start_date_str = f"{s_yr}-01-01"
    end_date_str = f"{e_yr}-12-31"

    temporal_dict = {
        "start": start_date_str,
        "end": end_date_str,
        "relative_period": rel_period,
        "resolution": temp_frequency,
        "frequency": temp_frequency,
    }

    # 5. Generate Discrete Temporal Windows
    windows: List[TemporalWindow] = []
    if strategy in ("temporal", "multitemporal"):
        if temp_frequency == "prithvi_stack":
            start_dt = datetime.date.fromisoformat(start_date_str)
            end_dt = datetime.date.fromisoformat(end_date_str)
            total_days = max(1, (end_dt - start_dt).days)
            slice_days = total_days // 4
            for i in range(4):
                slot_start = start_dt + datetime.timedelta(days=i * slice_days)
                slot_end = (
                    slot_start + datetime.timedelta(days=slice_days)
                    if i < 3
                    else end_dt
                )
                windows.append(
                    TemporalWindow(
                        slot=f"t{i+1}",
                        start=slot_start.isoformat(),
                        end=slot_end.isoformat(),
                        label=f"Period {i+1}",
                        period_type="custom",
                    )
                )
        elif temp_frequency == "annual":
            # Deterministic annual observation sequence (Section 18, Part 2)
            for y in range(s_yr, e_yr + 1):
                # Search full year with target date at peak vegetative / observation window (July 15)
                windows.append(
                    TemporalWindow(
                        slot=str(y),
                        start=f"{y}-01-01",
                        end=f"{y}-12-31",
                        target_date=f"{y}-07-15",
                        label=str(y),
                        period_type="annual",
                    )
                )
        elif temp_frequency == "quarterly":
            for y in range(s_yr, e_yr + 1):
                quarters = [
                    ("Q1", f"{y}-01-01", f"{y}-03-31", f"{y}-02-15"),
                    ("Q2", f"{y}-04-01", f"{y}-06-30", f"{y}-05-15"),
                    ("Q3", f"{y}-07-01", f"{y}-09-30", f"{y}-08-15"),
                    ("Q4", f"{y}-10-01", f"{y}-12-31", f"{y}-11-15"),
                ]
                for q_label, q_start, q_end, q_target in quarters:
                    windows.append(
                        TemporalWindow(
                            slot=f"{y}-{q_label}",
                            start=q_start,
                            end=q_end,
                            target_date=q_target,
                            label=f"{y} {q_label}",
                            period_type="quarterly",
                        )
                    )
        else:
            # Fallback sliced windows
            try:
                start_dt = datetime.date.fromisoformat(start_date_str)
                end_dt = datetime.date.fromisoformat(end_date_str)
                total_days = max(1, (end_dt - start_dt).days)
                slice_days = total_days // max(1, temp_count or 4)
                for i in range(temp_count or 4):
                    slot_start = start_dt + datetime.timedelta(days=i * slice_days)
                    slot_end = (
                        slot_start + datetime.timedelta(days=slice_days)
                        if i < (temp_count or 4) - 1
                        else end_dt
                    )
                    windows.append(
                        TemporalWindow(
                            slot=f"t{i+1}",
                            start=slot_start.isoformat(),
                            end=slot_end.isoformat(),
                            label=f"Period {i+1}",
                            period_type="custom",
                        )
                    )
            except Exception:
                windows = []

    # 4. Resolve Cloud Cover Constraint
    cloud_max = 20.0
    if request.data_requirements.cloud_constraint:
        m_cloud = re.search(r"(\d+)", request.data_requirements.cloud_constraint)
        if m_cloud:
            cloud_max = float(m_cloud.group(1))

    # 5. Extract AOI properties
    KNOWN_BBOXES = {
        "delhi": [76.84, 28.40, 77.34, 28.88],
        "mumbai": [72.77, 18.89, 73.01, 19.27],
        "bengaluru": [77.46, 12.83, 77.75, 13.14],
        "bangalore": [77.46, 12.83, 77.75, 13.14],
        "derna": [22.60, 32.74, 22.68, 32.79],
        "kashmir": [74.0, 33.5, 75.5, 34.5],
        "srinagar": [74.75, 34.05, 74.88, 34.15],
    }
    aoi_name = (aoi_info or {}).get("name") or request.aoi.name or "Delhi"
    bbox = (aoi_info or {}).get("bbox") or request.aoi.bbox
    if not bbox and aoi_name and aoi_name.lower().strip() in KNOWN_BBOXES:
        bbox = KNOWN_BBOXES[aoi_name.lower().strip()]
    raw_geom = (aoi_info or {}).get("polygon") or request.aoi.geometry
    if isinstance(raw_geom, list):
        geometry = {"type": "Polygon", "coordinates": [raw_geom]}
    elif isinstance(raw_geom, dict):
        geometry = raw_geom
    else:
        geometry = None

    # Preferred datasets
    preferred_datasets = []
    if has_optical:
        preferred_datasets.append("sentinel-2")
    if has_sar:
        preferred_datasets.append("sentinel-1")
    if "elevation" in req_modalities or "terrain" in q_lower or "dem" in q_lower or task == "terrain_analysis":
        preferred_datasets.append("copernicus-dem-30m")

    return DataRequirement(
        aoi_name=aoi_name,
        bbox=bbox,
        geometry=geometry,
        temporal=temporal_dict,
        modalities=req_modalities,
        preferred_datasets=preferred_datasets,
        spatial_resolution=request.data_requirements.spatial_resolution or "10m",
        cloud_cover_max=cloud_max,
        required_bands=required_bands,
        temporal_count=temp_count,
        temporal_windows=windows,
        acquisition_strategy=strategy,
        co_registration_required=co_reg,
        max_pair_delta_days=5,
        quality_constraints={"min_valid_pixels_pct": 80.0},
    )
