"""
backend/app/services/tool_registry.py
─────────────────────────────────────────────────────────────────────────────
Agentic Tool System (ATS) Tool Registry and Capability Matching Engine.

Resolves standardized AnalysisRequest into an executable ToolPlan based on:
  - Canonical primary task
  - Required vs requested modalities
  - Specialist model capabilities
  - Registered tool constraints
  - Strict input completeness (no silent auto-repair)
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.schemas.analysis_request import AnalysisRequest, ToolPlan, PrimaryTask
from app.models.registry import MODEL_REGISTRY


class ToolDefinition(BaseModel):
    tool_id: str
    name: str
    description: str
    supported_tasks: List[str]
    required_modalities: List[str]
    supported_models: List[str]
    default_model: str
    output_types: List[str]
    visualization_compatibility: List[str]


TOOL_CATALOG: Dict[str, ToolDefinition] = {
    "analyze_image": ToolDefinition(
        tool_id="analyze_image",
        name="Single Image VQA & Scene Analysis",
        description="Processes single optical or multispectral satellite images for visual question answering, land-cover description, and grounding.",
        supported_tasks=[
            "single_image_vqa",
            "scene_description",
            "multispectral_analysis",
            "object_detection",
            "visual_grounding",
        ],
        required_modalities=["optical"],
        supported_models=["earthdial-4b-ms", "geochat-7b"],
        default_model="earthdial-4b-ms",
        output_types=["vqa_answer", "scene_interpretation", "observations"],
        visualization_compatibility=["image_evidence", "none"],
    ),
    "detect_change": ToolDefinition(
        tool_id="detect_change",
        name="Bi-Temporal Change Detection",
        description="Analyzes bi-temporal or longitudinal optical imagery to detect land-cover, vegetation, or urban changes.",
        supported_tasks=[
            "temporal_change_detection",
            "land_cover_change",
            "vegetation_analysis",
            "urban_change",
            "image_comparison",
        ],
        required_modalities=["optical"],
        supported_models=["prithvi-eo-2.0", "vista", "deterministic-spectral-analysis"],
        default_model="prithvi-eo-2.0",
        output_types=["change_mask", "time_series", "metrics"],
        visualization_compatibility=["change_map", "time_series", "3D Surface"],
    ),
    "analyze_multitemporal": ToolDefinition(
        tool_id="analyze_multitemporal",
        name="Multitemporal Multispectral Stack Analysis",
        description="Analyzes 4-frame multispectral satellite stacks using ViT MAE temporal encoders (Prithvi-EO-2.0).",
        supported_tasks=[
            "temporal_change_detection",
            "multispectral_analysis",
            "land_cover_change",
            "vegetation_analysis",
        ],
        required_modalities=["multispectral"],
        supported_models=["prithvi-eo-2.0"],
        default_model="prithvi-eo-2.0",
        output_types=["change_mask", "change_percentage", "metrics"],
        visualization_compatibility=["change_map", "time_series", "3D Surface"],
    ),
    "analyze_sar_optical": ToolDefinition(
        tool_id="analyze_sar_optical",
        name="SAR-Optical Cross-Modal Analysis",
        description="Fuses synthetic aperture radar (Sentinel-1 SAR VV/VH) and optical (Sentinel-2) imagery for cross-modal alignment, flood mapping, and structural assessment.",
        supported_tasks=[
            "sar_optical_analysis",
            "flood_analysis",
            "cross_modal_analysis",
            "optical_sar_comparison",
        ],
        required_modalities=["sar", "optical"],
        supported_models=["closp", "terrafm"],
        default_model="closp",
        output_types=["cross_modal_similarity", "alignment_score", "metrics"],
        visualization_compatibility=["optical_sar_comparison", "cesium_spatial_overlay"],
    ),
}


class ToolRegistry:
    """
    Central ATS registry providing capability matching, tool lookup,
    and strict input validation.
    """

    def __init__(self) -> None:
        self._tools = TOOL_CATALOG

    def get_tool(self, tool_id: str) -> Optional[ToolDefinition]:
        return self._tools.get(tool_id)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def plan_execution(
        self,
        request: AnalysisRequest,
        active_asset: Optional[Dict[str, Any]] = None,
        location_info: Optional[Dict[str, Any]] = None,
    ) -> ToolPlan:
        """
        Translates an AnalysisRequest into a ToolPlan using capability matching.
        Strictly enforces required modalities without silent auto-repair.
        """
        task = request.intent.primary_task.lower().strip()
        modalities = [m.lower().strip() for m in request.data_requirements.modalities]
        has_sar = "sar" in modalities
        has_optical = "optical" in modalities or "multispectral" in modalities
        has_multispectral = "multispectral" in modalities

        explicit_model = request.model_selection.explicit_model or request.model_selection.model
        if explicit_model:
            explicit_model = explicit_model.lower().strip()

        # 1. Strict Validation: User requested CLOSP or TerraFM explicitly
        if explicit_model in ("closp", "terrafm"):
            tool_def = self._tools["analyze_sar_optical"]
            # CLOSP requires BOTH SAR and optical
            missing = []
            if not has_sar:
                missing.append("sar")
            if not has_optical:
                missing.append("optical")

            if missing:
                return ToolPlan(
                    tool="analyze_sar_optical",
                    model=explicit_model,
                    status="needs_data",
                    missing_inputs=missing,
                    reason=f"Model '{explicit_model}' requires both SAR and optical observations, but missing: {missing}.",
                    requires_modalities=["sar", "optical"],
                )

            inputs = self._build_inputs_for_tool("analyze_sar_optical", active_asset, location_info)
            return ToolPlan(
                tool="analyze_sar_optical",
                model=explicit_model,
                inputs=inputs,
                reason=f"Matched tool 'analyze_sar_optical' for requested model '{explicit_model}' with SAR and optical modalities.",
                requires_modalities=["sar", "optical"],
                status="planned",
            )

        # 2. SAR + Optical cross-modal or flood task
        if has_sar and has_optical or task in ("sar_optical_analysis", "optical_sar_comparison", "flood_analysis"):
            if not has_sar and task in ("sar_optical_analysis", "optical_sar_comparison"):
                return ToolPlan(
                    tool="analyze_sar_optical",
                    model="closp",
                    status="needs_data",
                    missing_inputs=["sar"],
                    reason=f"Task '{task}' requires SAR observations, but only optical modality was specified.",
                    requires_modalities=["sar", "optical"],
                )

            # Capability matching: select between CLOSP and TerraFM based on task & capabilities
            if explicit_model in ("closp", "terrafm"):
                selected_model = explicit_model
            elif task in ("flood_analysis", "cross_modal_analysis", "sar_optical_analysis", "optical_sar_comparison"):
                # CLOSP specializes in contrastive SAR-optical cross-modal alignment and flood inundation
                selected_model = "closp"
            elif task in ("vegetation_analysis", "land_cover_change", "temporal_change_detection", "urban_change"):
                # TerraFM specializes in multimodal foundation representation for land cover & vegetation
                selected_model = "terrafm"
            else:
                selected_model = "closp"

            inputs = self._build_inputs_for_tool("analyze_sar_optical", active_asset, location_info)
            return ToolPlan(
                tool="analyze_sar_optical",
                model=selected_model,
                inputs=inputs,
                reason=f"Matched tool 'analyze_sar_optical' with model '{selected_model}' based on task '{task}' and SAR+optical capabilities.",
                requires_modalities=["sar", "optical"],
                status="planned",
            )

        # 3. Single-Image VQA & Scene Understanding & Terrain
        if task in ("single_image_vqa", "scene_description", "object_detection", "visual_grounding", "terrain_analysis") or active_asset:
            selected_model = explicit_model if explicit_model in ("earthdial-4b-ms", "geochat-7b") else "earthdial-4b-ms"
            inputs = self._build_inputs_for_tool("analyze_image", active_asset, location_info)
            return ToolPlan(
                tool="analyze_image",
                model=selected_model,
                inputs=inputs,
                reason=f"Matched tool 'analyze_image' for task '{task}' with model '{selected_model}'.",
                requires_modalities=["optical"],
                status="planned",
            )

        # 4. Multitemporal stack or temporal change detection
        if task in ("temporal_change_detection", "land_cover_change", "vegetation_analysis", "urban_change", "multispectral_analysis"):
            if has_multispectral:
                tool_id = "analyze_multitemporal"
                selected_model = explicit_model if explicit_model in ("prithvi-eo-2.0",) else "prithvi-eo-2.0"
            else:
                tool_id = "detect_change"
                selected_model = explicit_model if explicit_model in ("prithvi-eo-2.0", "vista", "deterministic-spectral-analysis") else "prithvi-eo-2.0"

            inputs = self._build_inputs_for_tool(tool_id, active_asset, location_info)
            return ToolPlan(
                tool=tool_id,
                model=selected_model,
                inputs=inputs,
                reason=f"Matched tool '{tool_id}' for task '{task}' with model '{selected_model}'.",
                requires_modalities=["optical"],
                status="planned",
            )

        # 5. Fallback: default observation tool
        default_tool = "detect_change"
        inputs = self._build_inputs_for_tool(default_tool, active_asset, location_info)
        return ToolPlan(
            tool=default_tool,
            model="prithvi-eo-2.0",
            inputs=inputs,
            reason=f"Default observation planning for task '{task}'.",
            requires_modalities=["optical"],
            status="planned",
        )

    def _build_inputs_for_tool(
        self,
        tool_id: str,
        active_asset: Optional[Dict[str, Any]],
        location_info: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        inputs: Dict[str, Any] = {}
        if location_info:
            inputs["location"] = location_info

        if active_asset:
            preview = active_asset.get("preview_url") or active_asset.get("file_path")
            if preview:
                inputs["image_url"] = preview
                inputs["sar_image_url"] = preview
                inputs["optical_image_url"] = active_asset.get("thumbnail_url") or preview

        return inputs


# Global ATS tool registry instance
tool_registry = ToolRegistry()
