"""
app/tools/analyze_sar_optical.py
─────────────────────────────────────────────────────────────────────────────
The analyze_sar_optical tool: cross-modal SAR+optical fusion.

SPECIALIST MODELS (on dedicated remote Kaggle workers):
  - CLOSP   (DarthReca/closp)        — contrastive cross-modal embedding model
  - TerraFM (mbzuai-oryx/TerraFM)   — large multisensor foundation model

MODEL SELECTION:
  Model selection is performed by the SAR/optical LLM selector subgraph
  (app/orchestrator/sar_optical_selector.py). The LLM semantically evaluates
  the query and image types to decide whether CLOSP, TerraFM, or both should
  be invoked — no keyword matching or hard-coded routing is used.

  CLOSP specialises in:
    - Cross-modal SAR ↔ optical similarity and retrieval
    - Flood mapping (SAR penetrates cloud; optical gives colour context)
    - Building damage assessment (SAR double-bounce vs. optical appearance)
    - Structural change detection via cross-modal embedding distance

  TerraFM specialises in:
    - Multi-sensor scene classification (SAR + optical fusion)
    - Terrain / land-cover mapping with multi-spectral input
    - Complex scene understanding across sensor modalities

WHAT GPT-OSS SEES:
  name: "analyze_sar_optical"
  description: (SAR+optical specific use cases)
  parameters: { sar_image, optical_image, metadata, query }

REMOTE WORKER CONTRACT:
  Two independent Kaggle notebooks:

  CLOSP worker (CLOSP_WORKER_URL):
    GET  /health
    POST /analyze
  Request:  { "sar_image_url": str, "optical_image_url": str, "query": str }
  Response: { "answer": str, "model": str, "mode": str,
              "similarity_score": float|null, "embeddings": dict|null }

  TerraFM worker (TERRAFM_WORKER_URL):
    GET  /health
    POST /analyze
  Request:  { "sar_image_url": str, "optical_image_url": str, "query": str }
  Response: { "answer": str, "model": str, "mode": str,
              "classifications": dict|null }

  Legacy combined worker (SAR_OPTICAL_WORKER_URL) is kept for backward
  compatibility but is no longer the primary execution path.
"""
from __future__ import annotations

from typing import Any
from loguru import logger

from app.tools.base import BaseTool
from app.services.remote_worker import CLOSPWorkerClient, TerraFMWorkerClient
from app.schemas.responses import ToolResult
from app.schemas.requests import AnalyzeSarOpticalInput
from app.config import settings


class AnalyzeSarOpticalTool(BaseTool):
    """
    Tool: analyze_sar_optical
    Specialist models: CLOSP + TerraFM (on separate remote Kaggle workers)
    Task: Fuse SAR and optical imagery for cross-modal analysis.
    Remote workers: CLOSP_WORKER_URL, TERRAFM_WORKER_URL (Kaggle notebooks)

    Model selection is LLM-driven (no keyword matching):
      - The LLM selects CLOSP, TerraFM, or both based on query semantics.
      - If both are selected, both workers are called and results combined.
      - In mock mode, both mock results are returned regardless.
    """

    def __init__(self) -> None:
        self._closp = CLOSPWorkerClient()
        self._terrafm = TerraFMWorkerClient()

    @property
    def name(self) -> str:
        return "analyze_sar_optical"

    @property
    def description(self) -> str:
        return (
            "Analyze a combination of SAR (Synthetic Aperture Radar) and optical "
            "satellite imagery together using cross-modal fusion models (CLOSP and/or "
            "TerraFM). Use this tool when the user provides BOTH a SAR image (e.g., "
            "Sentinel-1) AND an optical image (e.g., Sentinel-2), or asks about "
            "cloud-penetrating radar analysis combined with optical context. "
            "Common use cases: flood mapping through clouds, building damage "
            "assessment, urban structure analysis using radar and optical fusion, "
            "terrain classification, wetland mapping. "
            "CLOSP is optimal for cross-modal similarity, flood and damage analysis. "
            "TerraFM is optimal for terrain classification and broad scene understanding. "
            "Both models may be selected for comprehensive analysis. "
            "Do NOT use for single-image analysis (use analyze_image) or "
            "two-time-period change detection without SAR (use detect_change). "
            "The 'selected_models' field in the args specifies which specialist(s) "
            "to invoke: 'closp', 'terrafm', or 'both'."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sar_image": {
                    "type": ["string", "null"],
                    "description": "Path or URL to the SAR image (e.g., Sentinel-1 GRD product).",
                },
                "optical_image": {
                    "type": ["string", "null"],
                    "description": "Path or URL to the optical image (e.g., Sentinel-2 RGB/multispectral).",
                },
                "metadata": {
                    "type": ["object", "null"],
                    "description": "Metadata about the imagery (satellite, sensor, acquisition_time, bands, crs).",
                    "additionalProperties": True,
                },
                "query": {
                    "type": "string",
                    "description": "Analysis question combining SAR and optical data.",
                },
                "selected_models": {
                    "type": "string",
                    "enum": ["closp", "terrafm", "both"],
                    "description": (
                        "Which specialist model(s) to invoke. "
                        "Choose 'closp' for cross-modal similarity/flood/damage tasks. "
                        "Choose 'terrafm' for terrain classification and scene understanding. "
                        "Choose 'both' for comprehensive dual-model analysis."
                    ),
                },
            },
            "required": ["query"],
        }

    def execute(self, args: dict[str, Any]) -> ToolResult:
        """
        Execute SAR+optical cross-modal analysis.

        The LLM sets 'selected_models' to 'closp', 'terrafm', or 'both'.
        This method calls the appropriate worker(s) and combines results.
        """
        logger.info(f"[analyze_sar_optical] Executing | args keys: {list(args.keys())}")

        # ── Validate arguments ────────────────────────────────────────────────
        try:
            validated = AnalyzeSarOpticalInput(**args)
        except Exception as e:
            logger.error(f"[analyze_sar_optical] Invalid arguments: {e}")
            return ToolResult(
                tool=self.name,
                model="unknown",
                mode="error",
                answer="Invalid tool arguments for SAR+optical analysis.",
                error=str(e),
            )

        # Read the LLM's model selection (defaults to "closp" if not provided)
        selected = (
            getattr(validated, "selected_models", None)
            or args.get("selected_models", "closp")
        )
        selected = selected.lower().strip()
        logger.info(f"[analyze_sar_optical] selected_models={selected!r}")

        sar_image = validated.sar_image
        optical_image = validated.optical_image
        query = validated.query

        # ── Execute selected worker(s) ────────────────────────────────────────
        if selected == "terrafm":
            return self._run_terrafm(sar_image, optical_image, query)

        elif selected == "both":
            return self._run_both(sar_image, optical_image, query)

        else:
            # Default: closp
            return self._run_closp(sar_image, optical_image, query)

    # ── Private worker dispatch helpers ───────────────────────────────────────

    def _run_closp(
        self,
        sar_image: str | None,
        optical_image: str | None,
        query: str,
    ) -> ToolResult:
        """Call the CLOSP worker only."""
        try:
            result = self._closp.call(
                sar_image=sar_image,
                optical_image=optical_image,
                query=query,
            )
        except RuntimeError as e:
            logger.error(f"[analyze_sar_optical] CLOSP worker error: {e}")
            return ToolResult(
                tool=self.name,
                model=CLOSPWorkerClient.MODEL_ID,
                mode="error",
                answer=f"CLOSP worker error: {e}",
                error=str(e),
            )
        except Exception as e:
            logger.exception("[analyze_sar_optical] Unexpected error calling CLOSP worker")
            return ToolResult(
                tool=self.name,
                model=CLOSPWorkerClient.MODEL_ID,
                mode="error",
                answer="CLOSP inference encountered an error.",
                error=str(e),
            )

        return ToolResult(
            tool=self.name,
            model=result.get("model", CLOSPWorkerClient.MODEL_ID),
            mode=result.get("mode", "mock"),
            answer=result["answer"],
            confidence=result.get("confidence"),
            artifacts=[],
        )

    def _run_terrafm(
        self,
        sar_image: str | None,
        optical_image: str | None,
        query: str,
    ) -> ToolResult:
        """Call the TerraFM worker only."""
        try:
            result = self._terrafm.call(
                sar_image=sar_image,
                optical_image=optical_image,
                query=query,
            )
        except RuntimeError as e:
            logger.error(f"[analyze_sar_optical] TerraFM worker error: {e}")
            return ToolResult(
                tool=self.name,
                model=TerraFMWorkerClient.MODEL_ID,
                mode="error",
                answer=f"TerraFM worker error: {e}",
                error=str(e),
            )
        except Exception as e:
            logger.exception("[analyze_sar_optical] Unexpected error calling TerraFM worker")
            return ToolResult(
                tool=self.name,
                model=TerraFMWorkerClient.MODEL_ID,
                mode="error",
                answer="TerraFM inference encountered an error.",
                error=str(e),
            )

        return ToolResult(
            tool=self.name,
            model=result.get("model", TerraFMWorkerClient.MODEL_ID),
            mode=result.get("mode", "mock"),
            answer=result["answer"],
            confidence=result.get("confidence"),
            artifacts=[],
        )

    def _run_both(
        self,
        sar_image: str | None,
        optical_image: str | None,
        query: str,
    ) -> ToolResult:
        """
        Call both CLOSP and TerraFM workers and synthesise results.
        Errors from individual workers are noted but don't fail the whole call.
        """
        closp_answer = terrafm_answer = None
        closp_model = CLOSPWorkerClient.MODEL_ID
        terrafm_model = TerraFMWorkerClient.MODEL_ID
        mode = "mock" if settings.model_mode != "real" else "real"

        # CLOSP
        try:
            closp_result = self._closp.call(
                sar_image=sar_image, optical_image=optical_image, query=query
            )
            closp_answer = closp_result.get("answer", "")
            closp_model = closp_result.get("model", closp_model)
            mode = closp_result.get("mode", mode)
        except Exception as e:
            logger.warning(f"[analyze_sar_optical] CLOSP failed in 'both' mode: {e}")
            closp_answer = f"[CLOSP error: {e}]"

        # TerraFM
        try:
            terrafm_result = self._terrafm.call(
                sar_image=sar_image, optical_image=optical_image, query=query
            )
            terrafm_answer = terrafm_result.get("answer", "")
            terrafm_model = terrafm_result.get("model", terrafm_model)
        except Exception as e:
            logger.warning(f"[analyze_sar_optical] TerraFM failed in 'both' mode: {e}")
            terrafm_answer = f"[TerraFM error: {e}]"

        combined_answer = (
            f"=== CLOSP Analysis ===\n{closp_answer}\n\n"
            f"=== TerraFM Analysis ===\n{terrafm_answer}"
        )
        combined_model = f"{closp_model} + {terrafm_model}"

        return ToolResult(
            tool=self.name,
            model=combined_model,
            mode=mode,
            answer=combined_answer,
            confidence=None,
            artifacts=[],
        )
