"""
backend/app/dataset/asset_selector.py
─────────────────────────────────────────────────────────────────────────────
Deterministic Asset Ranking and Selection Engine.
Selects candidate satellite assets based on:
  - AOI coverage & spatial resolution
  - Cloud cover threshold
  - Required spectral bands completeness
  - Discrete temporal window allocation (no silent duplication)
  - Cross-modal temporal delta pairing (Sentinel-1 + Sentinel-2 within max_pair_delta_days)
"""
from typing import List, Tuple, Optional, Dict, Any
import datetime
import math

from app.schemas.data_asset import DataAsset
from app.schemas.data_requirement import DataRequirement, TemporalWindow, TemporalObservationRecord


def score_asset(asset: DataAsset, requirement: DataRequirement, target_date: Optional[datetime.date] = None) -> Tuple[float, str]:
    """
    Computes a deterministic score for a candidate DataAsset against DataRequirement constraints.
    Score components:
      - Cloud cover score (0 - 40 pts)
      - Band completeness (0 - 30 pts)
      - Temporal proximity to target date (0 - 20 pts)
      - Spatial resolution (0 - 10 pts)
    """
    score = 0.0
    reasons = []

    # 1. Cloud Cover Score (0 - 40 pts)
    cc = asset.cloud_cover if asset.cloud_cover is not None else 10.0
    if cc <= requirement.cloud_cover_max:
        # Max score for 0% cloud; decreases down to requirement.cloud_cover_max
        pts = max(0.0, 40.0 * (1.0 - (cc / max(1.0, requirement.cloud_cover_max))))
        score += pts
        reasons.append(f"Cloud cover {cc:.1f}% within threshold (<= {requirement.cloud_cover_max:.1f}%)")
    else:
        reasons.append(f"Cloud cover {cc:.1f}% exceeds threshold ({requirement.cloud_cover_max:.1f}%)")
        return 0.0, "; ".join(reasons)

    # 2. Required Bands Completeness (0 - 30 pts)
    if requirement.required_bands:
        present_bands = [b for b in requirement.required_bands if b in asset.bands]
        band_frac = len(present_bands) / len(requirement.required_bands)
        if band_frac < 1.0:
            reasons.append(f"Missing required bands: {set(requirement.required_bands) - set(asset.bands)}")
            return 0.0, "; ".join(reasons)
        score += 30.0
        reasons.append(f"All {len(requirement.required_bands)} required bands present")
    else:
        score += 30.0

    # 3. Temporal Proximity Score (0 - 20 pts)
    if target_date and asset.acquisition_time:
        try:
            acq_dt = datetime.date.fromisoformat(asset.acquisition_time[:10])
            diff_days = abs((acq_dt - target_date).days)
            pts = max(0.0, 20.0 * math.exp(-diff_days / 60.0))
            score += pts
            reasons.append(f"Temporal proximity: {diff_days} days from target date")
        except Exception:
            score += 10.0
    else:
        score += 20.0

    # 4. Spatial Resolution (0 - 10 pts)
    res = asset.spatial_resolution or 10.0
    if res <= 10.0:
        score += 10.0
        reasons.append(f"Optimal high spatial resolution ({res}m)")
    elif res <= 30.0:
        score += 5.0
        reasons.append(f"Medium spatial resolution ({res}m)")

    return score, "; ".join(reasons)


def rank_candidate_assets(
    candidates: List[DataAsset],
    requirement: DataRequirement,
    target_date: Optional[datetime.date] = None,
) -> List[Tuple[DataAsset, float, str]]:
    """
    Ranks candidate assets deterministically descending by score.
    Assets failing mandatory criteria receive score 0.0 and are excluded.
    """
    scored: List[Tuple[DataAsset, float, str]] = []
    for asset in candidates:
        sc, rationale = score_asset(asset, requirement, target_date=target_date)
        if sc > 0.0:
            scored.append((asset, sc, rationale))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def select_best_asset(
    candidates: List[DataAsset],
    requirement: DataRequirement,
    target_date: Optional[datetime.date] = None,
) -> Optional[DataAsset]:
    """Selects the single highest-scoring valid DataAsset."""
    ranked = rank_candidate_assets(candidates, requirement, target_date=target_date)
    return ranked[0][0] if ranked else None


def select_temporal_series(
    candidates: List[DataAsset],
    requirement: DataRequirement,
    temporal_count: Optional[int] = None,
) -> Tuple[Dict[str, DataAsset], List[str], List[TemporalObservationRecord]]:
    """
    Allocates candidate assets across discrete temporal windows (Section 18, Part 2).
    For each window:
      - Searches actual observations
      - Filters by cloud cover and required bands
      - Scores candidates deterministically
      - Preserves full acquisition metadata, tile info, sensor, and provider
      - If no valid scene exists, deterministically marks status='unavailable' with reason
    Returns:
      (selected_slots, missing_slots, temporal_observations)
    """
    windows = requirement.temporal_windows
    if not windows:
        # Generate default windows across requirement.temporal
        cur_year = datetime.date.today().year
        start_str = requirement.temporal.get("start", f"{cur_year-4}-01-01")[:10]
        end_str = requirement.temporal.get("end", f"{cur_year}-12-31")[:10]
        start_dt = datetime.date.fromisoformat(start_str)
        end_dt = datetime.date.fromisoformat(end_str)
        t_cnt = temporal_count or 4
        total_days = max(1, (end_dt - start_dt).days)
        slice_days = total_days // t_cnt
        windows = []
        for i in range(t_cnt):
            slot_start = start_dt + datetime.timedelta(days=i * slice_days)
            slot_end = slot_start + datetime.timedelta(days=slice_days) if i < t_cnt - 1 else end_dt
            windows.append(TemporalWindow(slot=f"t{i+1}", start=slot_start.isoformat(), end=slot_end.isoformat()))

    selected_slots: Dict[str, DataAsset] = {}
    missing_slots: List[str] = []
    temporal_observations: List[TemporalObservationRecord] = []

    for win in windows:
        slot_candidates = []
        window_raw_candidates = []
        for c in candidates:
            acq = c.acquisition_time[:10] if c.acquisition_time else ""
            if acq and win.start <= acq <= win.end:
                window_raw_candidates.append(c)
                slot_candidates.append(c)

        # Target date for temporal scoring
        if win.target_date:
            try:
                target_dt = datetime.date.fromisoformat(win.target_date[:10])
            except Exception:
                target_dt = datetime.date.fromisoformat(win.start) + (datetime.date.fromisoformat(win.end) - datetime.date.fromisoformat(win.start)) // 2
        else:
            target_dt = datetime.date.fromisoformat(win.start) + (datetime.date.fromisoformat(win.end) - datetime.date.fromisoformat(win.start)) // 2

        best = select_best_asset(slot_candidates, requirement, target_date=target_dt)

        if best:
            selected_slots[win.slot] = best
            meta = best.metadata or {}
            obs = TemporalObservationRecord(
                slot=win.slot,
                period=win.label or win.slot,
                status="ready",
                date=best.acquisition_time[:10] if best.acquisition_time else win.target_date,
                asset_id=best.asset_id,
                sensor=best.sensor or "Sentinel-2 MSI",
                dataset_id=best.dataset_id or "sentinel-2-l2a",
                cloud_cover=best.cloud_cover,
                spatial_resolution=best.spatial_resolution or 10.0,
                provider=best.provider or "planetary_computer",
                source_url=best.source_url or best.preview_url,
                tile_id=meta.get("mgrs_tile") or meta.get("tile_id"),
                coverage_type=meta.get("coverage_type", "single_scene"),
                tile_count=meta.get("tile_count", 1),
                bands=best.bands,
                selected=True,
                explanation=f"Valid observation acquired on {best.acquisition_time[:10]} ({best.cloud_cover:.1f}% cloud).",
            )
            temporal_observations.append(obs)
        else:
            missing_slots.append(win.slot)
            # Classify why data is unavailable for this period (Part 4)
            if not window_raw_candidates:
                reason = "NO_VALID_SCENE"
                expl = f"No observation found for {win.label or win.slot} within the satellite mission archive."
            else:
                clouds = [c.cloud_cover for c in window_raw_candidates if c.cloud_cover is not None]
                if clouds and min(clouds) > requirement.cloud_cover_max:
                    reason = "CLOUD_THRESHOLD_FAILED"
                    expl = f"All candidate scenes for {win.label or win.slot} exceeded cloud cover threshold ({min(clouds):.1f}% > {requirement.cloud_cover_max:.1f}%)."
                else:
                    reason = "MISSING_REQUIRED_BANDS"
                    expl = f"Candidate scenes for {win.label or win.slot} lack required spectral bands."

            obs = TemporalObservationRecord(
                slot=win.slot,
                period=win.label or win.slot,
                status="unavailable",
                reason=reason,
                explanation=expl,
                sensor="Sentinel-2 MSI" if "optical" in requirement.modalities else "Sentinel-1 C-SAR",
                dataset_id="sentinel-2-l2a" if "optical" in requirement.modalities else "sentinel-1-grd",
                selected=False,
            )
            temporal_observations.append(obs)

    return selected_slots, missing_slots, temporal_observations


def select_temporal_assets(
    candidates: List[DataAsset],
    requirement: DataRequirement,
    temporal_count: int = 4,
    return_observations: bool = False,
) -> Any:
    """
    Allocates candidates across N discrete temporal windows (Section 18, 19).
    Maintains backwards compatibility for tests expecting (selected_slots, missing_slots).
    """
    selected_slots, missing_slots, observations = select_temporal_series(
        candidates=candidates,
        requirement=requirement,
        temporal_count=temporal_count,
    )
    if return_observations:
        return selected_slots, missing_slots, observations
    return selected_slots, missing_slots


def match_sar_optical_pair(
    sar_candidates: List[DataAsset],
    optical_candidates: List[DataAsset],
    max_delta_days: int = 5,
) -> Optional[Tuple[DataAsset, DataAsset]]:
    """
    Matches a Sentinel-1 C-SAR and Sentinel-2 optical pair over the same AOI
    where |T_sar - T_optical| <= max_delta_days (Section 21, 22).
    Picks the pair with the smallest temporal difference and lowest optical cloud cover.
    """
    best_pair = None
    min_delta = 999999
    best_cc = 100.0

    for sar in sar_candidates:
        if not sar.acquisition_time:
            continue
        sar_dt = datetime.datetime.fromisoformat(sar.acquisition_time.replace("Z", "+00:00"))

        for opt in optical_candidates:
            if not opt.acquisition_time:
                continue
            opt_dt = datetime.datetime.fromisoformat(opt.acquisition_time.replace("Z", "+00:00"))

            delta_days = abs((sar_dt - opt_dt).total_seconds()) / 86400.0
            if delta_days <= max_delta_days:
                cc = opt.cloud_cover if opt.cloud_cover is not None else 10.0
                # Prefer lowest delta; tie break with lowest cloud cover
                if delta_days < min_delta or (abs(delta_days - min_delta) < 0.5 and cc < best_cc):
                    min_delta = delta_days
                    best_cc = cc
                    best_pair = (sar, opt)

    return best_pair
