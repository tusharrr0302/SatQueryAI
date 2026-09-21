"""
app/tools/analyze_image.py
─────────────────────────────────────────────────────────────────────────────
The analyze_image tool: single-image remote-sensing VQA via EarthDial-4B-MS.

SPECIALIST MODEL CHANGE:
  GeoChat-7B has been replaced by EarthDial-4B-MS (MBZUAI/EarthDial-4B-MS).
  EarthDial-4B-MS is a 4B-parameter multimodal EO-VLM with native
  multi-spectral (MS) support, enabling richer analysis of GeoTIFF imagery.

  The local backend does NOT load EarthDial. It is a pure HTTP client.
  Inference is handled by the remote Kaggle worker (EarthDialWorkerClient).

ROLE IN THE ARCHITECTURE:
  This is the thin "glue" layer between the orchestrator and the EarthDial
  Kaggle worker. The orchestrator knows about this tool through the registry.
  This tool knows nothing about GPT-OSS or FastAPI — only about the worker.

WHAT GPT-OSS SEES:
  name: "analyze_image"
  description: (see below — GPT-OSS reads this to decide when to call it)
  parameters: { image, query, metadata }

WHAT THIS TOOL DOES:
  1. Receives validated arguments from the orchestrator
  2. Calls EarthDialWorkerClient.call()
     - In mock mode: returns a local mock result (no HTTP)
     - In real mode: HTTP POST to the EarthDial Kaggle notebook via ngrok
  3. Wraps the result in a ToolResult envelope
  4. Returns it to the orchestrator, which feeds it back to GPT-OSS

REMOTE WORKER CONTRACT:
  The Kaggle EarthDial notebook exposes:
    GET  /health
    POST /analyze
  Request:  { "image_url": str|null, "question": str }
  Response: { "answer": str, "model": str, "mode": "mock"|"real" }
"""

from typing import Any
from loguru import logger

from app.tools.base import BaseTool
from app.services.remote_worker import EarthDialWorkerClient
from app.schemas.responses import ToolResult
from app.schemas.requests import AnalyzeImageInput


class AnalyzeImageTool(BaseTool):
    """
    Tool: analyze_image
    Specialist model: EarthDial-4B-MS (MBZUAI/EarthDial-4B-MS)
    Task: Visual question answering on a single satellite/aerial image.
    Remote worker: EARTHDIAL_WORKER_URL (Kaggle notebook via ngrok)
    """

    def __init__(self) -> None:
        # Worker client is created once per service startup.
        # In mock mode: no HTTP connections are made.
        # In real mode: calls EARTHDIAL_WORKER_URL at inference time.
        self._worker = EarthDialWorkerClient()

    @property
    def name(self) -> str:
        return "analyze_image"

    @property
    def description(self) -> str:
        # This text is shown directly to GPT-OSS.
        # Write it clearly — GPT-OSS decides to call this tool based on it.
        return (
            "Analyze a single satellite or aerial image using the EarthDial-4B-MS "
            "vision-language model (a multi-spectral EO specialist). Use this tool "
            "for: describing image content, identifying land cover types, detecting "
            "objects (buildings, roads, vehicles, vegetation), answering questions "
            "about a single image, performing visual grounding in remote-sensing "
            "imagery, and interpreting multi-spectral GeoTIFF data. "
            "Do NOT use for comparing two images (use detect_change instead) "
            "or for SAR+optical fusion (use analyze_sar_optical instead)."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        # JSON Schema format — GPT-OSS uses this to know what args to provide.
        return {
            "type": "object",
            "properties": {
                "image": {
                    "type": "string",
                    "description": (
                        "Path or URL to the satellite image file that EarthDial-4B-MS "
                        "must analyze. For real inference, this must be a publicly "
                        "accessible URL (not a local file path)."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": "The question or analysis request about the image.",
                },
                "metadata": {
                    "type": ["object", "null"],
                    "description": (
                        "Optional satellite metadata: satellite name, sensor, "
                        "acquisition_time, bands list, CRS."
                    ),
                    "properties": {
                        "satellite": {"type": "string"},
                        "sensor": {"type": "string"},
                        "acquisition_time": {"type": "string"},
                        "bands": {"type": "array", "items": {"type": "string"}},
                        "crs": {"type": "string"},
                    },
                    "additionalProperties": True,
                },
            },
            "required": ["image", "query"],
        }

    def execute(self, args: dict[str, Any]) -> ToolResult:
        """
        Execute the analyze_image tool.

        The orchestrator calls this after GPT-OSS emits a tool_call for
        "analyze_image". The args dict comes directly from GPT-OSS.

        Steps:
          1. Validate the arguments with the Pydantic schema
          2. Call EarthDial worker (mock or real)
          3. Return a ToolResult
        """
        logger.info(f"[analyze_image] Executing | args keys: {list(args.keys())}")

        # ── Validate arguments ────────────────────────────────────────────────
        try:
            validated = AnalyzeImageInput(**args)
        except Exception as e:
            logger.error(f"[analyze_image] Invalid arguments: {e}")
            return ToolResult(
                tool=self.name,
                model=EarthDialWorkerClient.MODEL_ID,
                mode="error",
                answer="Invalid tool arguments provided.",
                error=str(e),
            )

        # ── Call remote worker ────────────────────────────────────────────────
        try:
            result = self._worker.call(
                image=validated.image,
                question=validated.query,
            )
        except RuntimeError as e:
            # Worker is unavailable or returned an error
            logger.error(f"[analyze_image] Worker error: {e}")
            return ToolResult(
                tool=self.name,
                model=EarthDialWorkerClient.MODEL_ID,
                mode="error",
                answer=f"EarthDial worker error: {e}",
                error=str(e),
            )
        except Exception as e:
            logger.exception("[analyze_image] Unexpected error calling worker")
            return ToolResult(
                tool=self.name,
                model=EarthDialWorkerClient.MODEL_ID,
                mode="error",
                answer="EarthDial inference encountered an error.",
                error=str(e),
            )

        # ── Package and return ────────────────────────────────────────────────
        image_metadata = result.get("image")
        artifacts = []
        if image_metadata:
            artifacts.append({
                "type": "image_metadata",
                "data": image_metadata,
            })

        return ToolResult(
            tool=self.name,
            model=result.get("model", EarthDialWorkerClient.MODEL_ID),
            mode=result.get("mode", "mock"),
            answer=result["answer"],
            confidence=result.get("confidence"),
            artifacts=artifacts,
        )
