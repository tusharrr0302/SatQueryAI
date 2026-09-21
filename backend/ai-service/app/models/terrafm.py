"""
app/models/terrafm.py
─────────────────────────────────────────────────────────────────────────────
TerraFM specialist model wrapper for cross-modal SAR+optical analysis.

HuggingFace model: mbzuai-oryx/TerraFM
Developer: MBZUAI (Mohamed bin Zayed University of AI)
Task: Terrain Foundation Model — multimodal remote sensing understanding.

TerraFM is a large geospatial foundation model that handles multiple
input modalities including SAR and optical. It's used as a powerful
alternative to CLOSP for complex cross-modal analysis queries.

The AnalyzeSarOpticalTool can select between CLOSP and TerraFM.
"""

from loguru import logger
from app.config import settings


class TerraFMModel:
    """
    Wrapper for the MBZUAI TerraFM foundation model.
    Called by the AnalyzeSarOpticalTool as an alternative to CLOSP.
    """

    MODEL_ID = "mbzuai-oryx/TerraFM"

    def __init__(self) -> None:
        self.mode = settings.model_mode
        logger.info(f"TerraFMModel initialised | mode={self.mode}")

        if self.mode == "real":
            self._load_real_model()

    def _load_real_model(self) -> None:
        """
        ── STUB ─────────────────────────────────────────────────────────────
        TerraFM may require significant VRAM. Suitable for Colab/Kaggle A100.

        Implementation sketch:
            from transformers import AutoModel, AutoProcessor
            self.processor = AutoProcessor.from_pretrained(
                self.MODEL_ID, trust_remote_code=True
            )
            self.model = AutoModel.from_pretrained(
                self.MODEL_ID,
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            )
        ─────────────────────────────────────────────────────────────────────
        """
        logger.warning("TerraFMModel real inference not yet implemented — using mock")
        self.mode = "mock"

    def infer(self, sar_image: str | None, optical_image: str | None, query: str) -> dict:
        """
        Run multimodal SAR+optical analysis using TerraFM.

        Args:
            sar_image: Path to SAR image
            optical_image: Path to optical/multispectral image
            query: Analysis question

        Returns:
            dict with keys: answer, confidence
        """
        if self.mode == "real":
            return self._run_real(sar_image, optical_image, query)
        return self._run_mock(sar_image, optical_image, query)

    def _run_mock(self, sar_image: str | None, optical_image: str | None, query: str) -> dict:
        logger.debug(f"TerraFMModel MOCK | sar={sar_image} | optical={optical_image}")
        return {
            "answer": (
                "[MOCK — TerraFM] Multimodal terrain analysis (SAR + optical): "
                "Fusing Sentinel-1 SAR and Sentinel-2 optical data using TerraFM "
                "foundation model embeddings. "
                "Terrain classification results: "
                "- Urban fabric (high-density): 34.2% of scene "
                "- Vegetation (mixed forest/shrubland): 28.7% "
                "- Agricultural land: 19.1% "
                "- Water bodies: 11.3% "
                "- Bare soil/construction sites: 6.7% "
                "SAR coherence analysis indicates stable structures in urban zones. "
                "No significant temporal decorrelation suggesting flood events. "
                f"(Query: '{query}')"
            ),
            "confidence": None,
        }

    def _run_real(self, sar_image: str | None, optical_image: str | None, query: str) -> dict:
        """── STUB — implement when GPU is available ──────────────────────"""
        logger.warning("TerraFMModel._run_real called but not implemented — using mock")
        return self._run_mock(sar_image, optical_image, query)
