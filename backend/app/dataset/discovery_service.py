"""
backend/app/dataset/discovery_service.py
─────────────────────────────────────────────────────────────────────────────
High-level Satellite Data Discovery and Asset Selection Service.
Orchestrates:
  AnalysisRequest + ToolPlan ──> DataRequirement ──> Provider Search ──> Asset Ranking ──> Selected Assets
"""
from typing import Dict, Any, List, Optional
import datetime
import logging

from app.schemas.analysis_request import AnalysisRequest, ToolPlan
from app.schemas.data_asset import DataAsset
from app.schemas.data_requirement import DataRequirement, DataDiscoveryResult
from app.dataset.data_requirement_mapper import map_analysis_request_to_requirement
from app.dataset.providers import get_data_provider, MockSatelliteDataProvider, SatelliteDataProvider
from app.dataset.asset_selector import (
    rank_candidate_assets,
    select_best_asset,
    select_temporal_assets,
    select_temporal_series,
    match_sar_optical_pair,
)

logger = logging.getLogger(__name__)


class SatelliteDataDiscoveryService:
    """
    Central service for discovering and selecting satellite assets to satisfy
    an AnalysisRequest and ATS ToolPlan.
    """

    def __init__(self, provider: Optional[SatelliteDataProvider] = None):
        self._provider = provider

    def _get_provider(self, modality: str = "optical", force_mock: bool = False) -> SatelliteDataProvider:
        if self._provider:
            return self._provider
        return get_data_provider(modality=modality, force_mock=force_mock)

    def discover_data_sync(
        self,
        request: AnalysisRequest,
        tool_plan: Optional[ToolPlan] = None,
        aoi_info: Optional[Dict[str, Any]] = None,
        force_mock: bool = False,
    ) -> DataDiscoveryResult:
        """
        Executes data discovery synchronously:
          1. Maps AnalysisRequest + ToolPlan ──> DataRequirement
          2. Validates temporal era (e.g. pre-1972)
          3. Queries provider(s) for candidate assets
          4. Deterministically ranks and selects assets according to strategy
        """
        # 1. Map to DataRequirement
        req = map_analysis_request_to_requirement(request, tool_plan, aoi_info)

        # 2. Check historical feasibility (Section 29, 30)
        start_year = req.temporal.get("start", "")[:4]
        if start_year.isdigit() and int(start_year) < 1972:
            return DataDiscoveryResult(
                status="unsupported_data_period",
                requirement=req,
                message=f"No compatible civil satellite data exists for {start_year}. Observation missions began with Landsat 1 in 1972.",
            )

        # 3. Determine Provider(s) & Search Candidates
        has_sar = "sar" in req.modalities
        has_optical = "optical" in req.modalities or "multispectral" in req.modalities

        all_candidates: List[DataAsset] = []
        sar_candidates: List[DataAsset] = []
        optical_candidates: List[DataAsset] = []

        try:
            if has_optical:
                opt_prov = self._get_provider(modality="optical", force_mock=force_mock)
                opt_req = req.model_copy(update={"modalities": ["optical"]})
                optical_candidates = [c for c in opt_prov.search_sync(opt_req) if c.dataset_id != "sentinel-1"]
                all_candidates.extend(optical_candidates)

            if has_sar:
                sar_prov = self._get_provider(modality="sar", force_mock=force_mock)
                sar_req = req.model_copy(update={"modalities": ["sar"]})
                sar_candidates = [c for c in sar_prov.search_sync(sar_req) if c.dataset_id != "sentinel-2"]
                all_candidates.extend(sar_candidates)
        except Exception as e:
            logger.warning(f"Data provider search failed: {e}")
            return DataDiscoveryResult(
                status="provider_unavailable",
                requirement=req,
                message=f"Satellite provider search unavailable: {str(e)}",
            )

        if not all_candidates:
            return DataDiscoveryResult(
                status="no_assets_found",
                requirement=req,
                message=f"No matching satellite assets found for {req.aoi_name} within the requested parameters.",
            )

        # 4. Deterministic Asset Selection based on Strategy
        strat = req.acquisition_strategy
        selected: List[DataAsset] = []
        temporal_map: Dict[str, DataAsset] = {}
        temporal_obs: List[Any] = []
        sar_optical_dict: Optional[Dict[str, DataAsset]] = None

        if strat == "sar_optical_pair":
            pair = match_sar_optical_pair(sar_candidates, optical_candidates, max_delta_days=req.max_pair_delta_days)
            if not pair:
                missing = []
                if not sar_candidates:
                    missing.append("sar")
                if not optical_candidates:
                    missing.append("optical")
                if sar_candidates and optical_candidates:
                    missing.append(f"co-registered pair within {req.max_pair_delta_days} days")
                return DataDiscoveryResult(
                    status="needs_data",
                    requirement=req,
                    candidates=all_candidates,
                    missing_inputs=missing,
                    message=f"Cannot execute SAR+optical analysis: missing {', '.join(missing)}.",
                )
            sar_asset, opt_asset = pair
            selected = [sar_asset, opt_asset]
            sar_optical_dict = {"sar": sar_asset, "optical": opt_asset}

        elif strat in ("temporal", "multitemporal"):
            temp_count = req.temporal_count or 4
            target_candidates = sar_candidates if ("sar" in req.modalities and not optical_candidates) else (optical_candidates or all_candidates)
            temporal_map, missing_slots, temporal_obs = select_temporal_series(target_candidates, req, temporal_count=temp_count)

            if not temporal_map:
                return DataDiscoveryResult(
                    status="no_assets_found",
                    requirement=req,
                    candidates=all_candidates,
                    temporal_assets=temporal_map,
                    temporal_observations=temporal_obs,
                    missing_inputs=missing_slots,
                    message=f"No valid observations found across the requested temporal range ({req.temporal.get('start')[:4]}–{req.temporal.get('end')[:4]}).",
                )
            elif len(temporal_map) < 2 and temp_count and temp_count > 1:
                # Need at least 2 distinct observations to establish change/trend
                return DataDiscoveryResult(
                    status="needs_data",
                    requirement=req,
                    candidates=all_candidates,
                    temporal_assets=temporal_map,
                    temporal_observations=temporal_obs,
                    missing_inputs=missing_slots,
                    message=f"Insufficient valid observations ({len(temporal_map)}) to establish a temporal trend; at least 2 distinct observations required.",
                )

            # Succeeded with available observations (missing periods preserved in temporal_observations)
            selected = list(temporal_map.values())

        else:  # "single" or "paired"
            best = select_best_asset(optical_candidates or all_candidates, req)
            if not best:
                return DataDiscoveryResult(
                    status="needs_data",
                    requirement=req,
                    candidates=all_candidates,
                    message="No candidates met cloud cover and band completeness requirements.",
                )
            selected = [best]

        datasets_meta = [
            {"dataset_id": "sentinel-2", "available": bool(optical_candidates)},
            {"dataset_id": "sentinel-1", "available": bool(sar_candidates)},
        ]

        return DataDiscoveryResult(
            status="success",
            requirement=req,
            datasets=datasets_meta,
            candidates=all_candidates,
            selected_assets=selected,
            temporal_assets=temporal_map,
            temporal_observations=temporal_obs,
            sar_optical_pair=sar_optical_dict,
            message="Data discovery completed successfully.",
        )

    async def discover_data(
        self,
        request: AnalysisRequest,
        tool_plan: Optional[ToolPlan] = None,
        aoi_info: Optional[Dict[str, Any]] = None,
        force_mock: bool = False,
    ) -> DataDiscoveryResult:
        """Asynchronous wrapper around discover_data_sync."""
        import asyncio
        return await asyncio.to_thread(self.discover_data_sync, request, tool_plan, aoi_info, force_mock)


# Global singleton instance
data_discovery_service = SatelliteDataDiscoveryService()
