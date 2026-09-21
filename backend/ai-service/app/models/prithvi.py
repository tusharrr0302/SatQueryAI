"""
app/models/prithvi.py
─────────────────────────────────────────────────────────────────────────────
Prithvi-EO-2.0-300M specialist model wrapper for change detection.

HuggingFace model: ibm-nasa-geospatial/Prithvi-EO-2.0-300M
Developer: IBM + NASA
Task: Earth observation foundation model — multi-task geospatial analysis
       including change detection, flood mapping, and burned area detection.

Prithvi is a geospatial foundation model trained on Harmonized Landsat
Sentinel-2 (HLS) data. It understands multi-spectral bands natively.

The detect_change tool can use EITHER VisTA or Prithvi — the tool selects
the best model based on the query and available image metadata.
"""

from loguru import logger
from app.config import settings


class PrithviModel:
    """
    Wrapper for IBM/NASA Prithvi-EO-2.0-300M.
    Called by the DetectChangeTool as an alternative to VisTA.
    """

    MODEL_ID = "ibm-nasa-geospatial/Prithvi-EO-2.0-300M"

    def __init__(self) -> None:
        self.mode = settings.model_mode
        logger.info(f"PrithviModel initialised | mode={self.mode}")

        if self.mode == "real":
            self._load_real_model()

    def _load_real_model(self) -> None:
        """
        ── STUB ─────────────────────────────────────────────────────────────
        Prithvi uses a custom HuggingFace architecture.
        You may need: pip install timm einops

        Implementation sketch:
            from transformers import AutoModel, AutoProcessor
            self.model = AutoModel.from_pretrained(
                self.MODEL_ID,
                trust_remote_code=True,
                device_map="auto",
            )
        ─────────────────────────────────────────────────────────────────────
        """
        logger.warning("PrithviModel real inference not yet implemented — using mock")
        self.mode = "mock"

    def infer(self, image_t1: str | None, image_t2: str | None, query: str) -> dict:
        """
        Detect changes between two temporal satellite images using Prithvi.

        Args:
            image_t1: Path to earlier image
            image_t2: Path to later image
            query: Change detection question

        Returns:
            dict with keys: answer, change_mask, confidence
        """
        if self.mode == "real":
            return self._run_real(image_t1, image_t2, query)
        return self._run_mock(image_t1, image_t2, query)

    def _run_mock(self, image_t1: str | None, image_t2: str | None, query: str) -> dict:
        logger.debug(f"PrithviModel MOCK | t1={image_t1} | t2={image_t2}")
        return {
            "answer": (
                "[MOCK — Prithvi-EO-2.0-300M] Multi-spectral change analysis: "
                "Processing HLS-format inputs across 6 spectral bands (Blue, Green, "
                "Red, NIR, SWIR-1, SWIR-2). Change detection segmentation identifies "
                "three primary change classes: "
                "(1) Flood inundation — new water coverage detected in low-lying areas "
                "(SWIR-1 decrease, NIR decrease), estimated extent ~340 hectares. "
                "(2) Vegetation recovery — NDVI increase in previously disturbed areas. "
                "(3) Bare soil exposure — likely infrastructure development. "
                "Foundation model confidence score: not available in this configuration. "
                f"(Query: '{query}')"
            ),
            "change_mask": None,
            "confidence": None,
        }

    def _run_real(self, image_t1: str | None, image_t2: str | None, query: str) -> dict:
        """
        ── STUB — implement when GPU is available ─────────────────────────
        """
        logger.warning("PrithviModel._run_real called but not implemented — using mock")
        return self._run_mock(image_t1, image_t2, query)
