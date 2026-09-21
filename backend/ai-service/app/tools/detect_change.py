"""
app/tools/detect_change.py
─────────────────────────────────────────────────────────────────────────────
The detect_change tool: bi-temporal change detection.

SPECIALIST MODELS (on the remote Kaggle worker):
  - VisTA   (like413/vista)                  — Change Detection QA & visual grounding
  - Prithvi (ibm-nasa-geospatial/Prithvi-EO-2.0-300M) — multitemporal/multispectral EO

ANALYSIS MODES (set by GPT-OSS via analysis_mode field):
  question_change       → VisTA ONLY
  multitemporal_analysis → Prithvi pipeline ONLY

  Only ONE specialist runs per request.
  GPT-OSS is the orchestrator — no keyword/regex routing is performed here.

WHAT GPT-OSS SEES:
  name: "detect_change"
  description: (explains bi-temporal change use case)
  parameters: { image_t1, image_t2, metadata_t1, metadata_t2, query, analysis_mode }

REMOTE WORKER CONTRACT:
  Kaggle notebook (CHANGE_DETECTION_WORKER_URL):
    GET  /health
    POST /tools/detect_change
  Request:  { "image_t1_url": str, "image_t2_url": str,
              "query": str, "analysis_mode": str|null }
  Response: { "tool": "detect_change", "status": "success",
              "model": str, "mode": str,
              "result": { "answer": str, "confidence": float|null,
                          "change_mask": null|dict } }
"""

from typing import Any
from loguru import logger

from app.tools.base import BaseTool
from app.services.remote_worker import (
    ChangeDetectionWorkerClient,
    VisTAWorkerClient,
    PrithviWorkerClient,
)
from app.schemas.responses import ToolResult
from app.schemas.requests import DetectChangeInput


class DetectChangeTool(BaseTool):
    """
    Tool: detect_change
    Specialist models: VisTA (dedicated worker) + Prithvi-EO-2.0-300M (Prithvi worker)
    Task: Detect and describe changes between temporally separated images.
    Remote workers:
      - question_change        → VisTAWorkerClient (VISTA_WORKER_URL)
      - multitemporal_analysis → PrithviWorkerClient (PRITHVI_WORKER_URL)
    """

    def __init__(self) -> None:
        self._worker = ChangeDetectionWorkerClient()
        self._vista_worker = VisTAWorkerClient()
        self._prithvi_worker = PrithviWorkerClient()

    @property
    def name(self) -> str:
        return "detect_change"

    @property
    def description(self) -> str:
        return (
            "Detect and describe changes between two satellite images taken at "
            "different times (bi-temporal change detection). Use this tool when "
            "the user wants to compare a BEFORE and AFTER image, identify what "
            "changed in a region over time, detect land cover transitions, urban "
            "expansion, deforestation, flood inundation, or disaster impacts. "
            "Requires two images (time-1 and time-2). Do NOT use for single-image "
            "analysis (use analyze_image) or SAR+optical fusion (use analyze_sar_optical)."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "image_t1": {
                    "type": ["string", "null"],
                    "description": "Path or URL to the earlier (time-1, 'before') image.",
                },
                "image_t2": {
                    "type": ["string", "null"],
                    "description": "Path or URL to the later (time-2, 'after') image.",
                },
                "image_t3": {
                    "type": ["string", "null"],
                    "description": "Path or URL to the time-3 image (for multitemporal analysis).",
                },
                "image_t4": {
                    "type": ["string", "null"],
                    "description": "Path or URL to the time-4 image (for multitemporal analysis).",
                },
                "metadata_t1": {
                    "type": ["object", "null"],
                    "description": "Metadata for the time-1 image (satellite, acquisition_time, bands, etc.)",
                    "additionalProperties": True,
                },
                "metadata_t2": {
                    "type": ["object", "null"],
                    "description": "Metadata for the time-2 image.",
                    "additionalProperties": True,
                },
                "metadata_t3": {
                    "type": ["object", "null"],
                    "description": "Metadata for the time-3 image.",
                    "additionalProperties": True,
                },
                "metadata_t4": {
                    "type": ["object", "null"],
                    "description": "Metadata for the time-4 image.",
                    "additionalProperties": True,
                },
                "query": {
                    "type": "string",
                    "description": "Description of what changes to look for, or a general change analysis request.",
                },
                "analysis_mode": {
                    "type": ["string", "null"],
                    "enum": ["question_change", "multitemporal_analysis", None],
                    "description": (
                        "Selects the specialist pipeline to run (only one runs per request). "
                        "'question_change': user wants a natural-language change-detection "
                        "answer and/or visual localization — routes to VisTA. "
                        "'multitemporal_analysis': user needs multitemporal/multispectral "
                        "EO analysis — routes to the Prithvi-EO-2.0-300M pipeline. "
                        "Omit when the mode cannot be determined from context."
                    ),
                },
            },
            "required": ["query"],
        }

    def execute(self, args: dict[str, Any]) -> ToolResult:
        """
        Execute bi-temporal change detection via the remote Kaggle worker.
        """
        logger.info(f"[detect_change] Executing | args keys: {list(args.keys())}")

        # ── Validate arguments ────────────────────────────────────────────────
        try:
            validated = DetectChangeInput(**args)
        except Exception as e:
            logger.error(f"[detect_change] Invalid arguments: {e}")
            return ToolResult(
                tool=self.name,
                model="unknown",
                mode="error",
                answer="Invalid tool arguments for change detection.",
                error=str(e),
            )

        # ── Forward analysis_mode to worker ───────────────────────────────────
        analysis_mode = validated.analysis_mode
        logger.debug(f"[detect_change] analysis_mode={analysis_mode!r}")

        # ── Call remote worker ────────────────────────────────────────────────
        try:
            if analysis_mode == "question_change":
                result = self._vista_worker.call(
                    image_t1=validated.image_t1,
                    image_t2=validated.image_t2,
                    query=validated.query,
                    metadata_t1=validated.metadata_t1,
                    metadata_t2=validated.metadata_t2,
                )
            elif analysis_mode == "multitemporal_analysis":
                result = self._prithvi_worker.call(
                    image_t1=validated.image_t1,
                    image_t2=validated.image_t2,
                    image_t3=validated.image_t3,
                    image_t4=validated.image_t4,
                    query=validated.query,
                    metadata_t1=validated.metadata_t1,
                    metadata_t2=validated.metadata_t2,
                    metadata_t3=validated.metadata_t3,
                    metadata_t4=validated.metadata_t4,
                )
            else:
                result = self._worker.call(
                    image_t1=validated.image_t1,
                    image_t2=validated.image_t2,
                    query=validated.query,
                    analysis_mode=analysis_mode,
                )
        except RuntimeError as e:
            logger.error(f"[detect_change] Worker error: {e}")
            return ToolResult(
                tool=self.name,
                model=analysis_mode or "unknown",
                mode="error",
                answer=f"Change detection worker error: {e}",
                error=str(e),
            )
        except Exception as e:
            logger.exception("[detect_change] Unexpected error calling worker")
            return ToolResult(
                tool=self.name,
                model=analysis_mode or "unknown",
                mode="error",
                answer="Change detection inference encountered an error.",
                error=str(e),
            )

        # ── Package and return ────────────────────────────────────────────────
        artifacts = []
        if result.get("change_mask"):
            artifacts.append({
                "type": "change_mask",
                "data": result["change_mask"],
            })

        if result.get("change_detected") is not None:
            status_data: dict[str, Any] = {
                "change_detected": result["change_detected"],
            }
            if result.get("change_percentage") is not None:
                status_data["change_percentage"] = result["change_percentage"]
            if result.get("temporal_frames") is not None:
                status_data["temporal_frames"] = result["temporal_frames"]
            if result.get("change_analysis"):
                status_data["changed_pixels"] = result["change_analysis"].get("changed_pixels")
                status_data["total_pixels"] = result["change_analysis"].get("total_pixels")
                status_data["threshold"] = result["change_analysis"].get("threshold")
            artifacts.append({
                "type": "change_detection_status",
                "data": status_data,
            })

        if result.get("change_analysis"):
            artifacts.append({
                "type": "change_analysis",
                "data": result["change_analysis"],
            })

        if result.get("model_output"):
            artifacts.append({
                "type": "model_output",
                "data": result["model_output"],
            })

        return ToolResult(
            tool=self.name,
            model=result.get("model", analysis_mode or "unknown"),
            mode=result.get("mode", "mock"),
            answer=result["answer"],
            confidence=result.get("confidence"),
            artifacts=artifacts,
        )
