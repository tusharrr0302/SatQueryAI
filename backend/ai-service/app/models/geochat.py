"""
app/models/geochat.py
─────────────────────────────────────────────────────────────────────────────
GeoChat-7B specialist model wrapper.

HuggingFace model: MBZUAI/GeoChat-7B
Paper: https://arxiv.org/abs/2311.15826

WHAT THIS MODEL DOES:
  GeoChat is a vision-language model fine-tuned specifically on remote-sensing
  imagery. It can answer questions about satellite images, describe land cover,
  identify objects, and perform visual grounding.

HOW THIS FILE IS ORGANISED:
  ┌─────────────────────────────────────────────────────────────────────┐
  │  GeoChatModel                                                       │
  │    ├── __init__(mode)  — reads MODEL_MODE from config               │
  │    ├── _run_mock(...)  — returns a labelled fake result (safe)       │
  │    └── _run_real(...)  — STUB: calls actual HuggingFace model       │
  └─────────────────────────────────────────────────────────────────────┘

  The tool (analyze_image.py) calls GeoChatModel.infer(), which delegates
  to either _run_mock or _run_real depending on MODEL_MODE.

TO SWITCH TO REAL INFERENCE:
  1. Set MODEL_MODE=real in your .env
  2. Implement _run_real() below (load the model, run forward pass)
  3. The rest of the system works unchanged
"""

from loguru import logger
from app.config import settings


class GeoChatModel:
    """
    Wrapper for the GeoChat-7B vision-language model.

    The orchestrator/tool layer never calls this directly.
    It is called by the AnalyzeImageTool.
    """

    MODEL_ID = "MBZUAI/GeoChat-7B"

    def __init__(self) -> None:
        self.mode = settings.model_mode
        logger.info(f"GeoChatModel initialised | mode={self.mode}")

        # In real mode, you would load the model and processor here.
        # For mock mode, nothing to load.
        if self.mode == "real":
            self._load_real_model()

    def _load_real_model(self) -> None:
        """
        Load GeoChat model weights from HuggingFace Hub.

        ── STUB ─────────────────────────────────────────────────────────────
        This is intentionally not implemented yet.
        GeoChat-7B requires ~14 GB VRAM in fp16 — more than the RTX 3050 has.
        You will implement this when running on a Colab/Kaggle T4 or A100.

        Implementation sketch (uncomment when ready):

            from transformers import AutoProcessor, AutoModelForVision2Seq
            import torch

            self.processor = AutoProcessor.from_pretrained(self.MODEL_ID)
            self.model = AutoModelForVision2Seq.from_pretrained(
                self.MODEL_ID,
                torch_dtype=torch.float16,
                device_map="auto",   # auto-selects GPU/CPU
            )
            self.model.eval()
        ─────────────────────────────────────────────────────────────────────
        """
        logger.warning(
            "GeoChatModel real inference is not yet implemented. "
            "Falling back to mock mode."
        )
        self.mode = "mock"

    def infer(self, image: str | None, query: str) -> dict:
        """
        Run inference on a single satellite image.

        Args:
            image: Path to image file (or base64 string, or None for text-only)
            query: The question to answer about the image

        Returns:
            dict with keys: answer, confidence
        """
        if self.mode == "real":
            return self._run_real(image, query)
        else:
            return self._run_mock(image, query)

    def _run_mock(self, image: str | None, query: str) -> dict:
        """
        Return a clearly-labelled mock result.
        Used during development when the real model is not available.

        The [MOCK] prefix ensures GPT-OSS and log readers know this is
        not a real inference result.
        """
        logger.debug(f"GeoChatModel MOCK inference | image={image} | query={query}")

        image_desc = f" of image '{image}'" if image else ""
        return {
            "answer": (
                f"[MOCK — GeoChat-7B] Analysis{image_desc}: "
                "This appears to be a multispectral satellite image showing mixed "
                "land cover including urban areas, vegetation patches, and what "
                "appears to be a water body in the lower-left quadrant. "
                "Several rectangular building footprints are visible in the "
                "central portion, consistent with a suburban residential area. "
                f"(Query received: '{query}')"
            ),
            "confidence": None,  # GeoChat does not output confidence scores
        }

    def _run_real(self, image: str | None, query: str) -> dict:
        """
        Run actual GeoChat-7B inference.

        ── STUB ─────────────────────────────────────────────────────────────
        Implementation sketch (fill in when GPU is available):

            from PIL import Image
            import torch

            pil_image = Image.open(image).convert("RGB") if image else None
            inputs = self.processor(
                images=pil_image,
                text=query,
                return_tensors="pt"
            ).to("cuda")

            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=512,
                )
            answer = self.processor.batch_decode(
                output_ids, skip_special_tokens=True
            )[0]
            return {"answer": answer, "confidence": None}
        ─────────────────────────────────────────────────────────────────────
        """
        logger.warning("GeoChatModel._run_real called but not implemented — using mock")
        return self._run_mock(image, query)
