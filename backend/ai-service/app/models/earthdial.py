"""
app/models/earthdial.py
─────────────────────────────────────────────────────────────────────────────
EarthDial-4B-MS specialist model wrapper.

HuggingFace model: MBZUAI/EarthDial-4B-MS
Paper / Repo:      https://huggingface.co/MBZUAI/EarthDial-4B-MS

WHAT THIS MODEL DOES:
  EarthDial-4B-MS is a 4-billion-parameter multimodal remote-sensing VLM
  fine-tuned on a large corpus of Earth observation imagery and associated
  QA pairs.  It supports multi-spectral (MS) input beyond RGB, making it
  well-suited for GeoTIFF satellite imagery.

  Common tasks:
    - Satellite image VQA (single image)
    - Scene description and land-cover identification
    - Object detection / counting in EO imagery
    - Multi-spectral band interpretation

WHY THIS FILE EXISTS:
  This stub documents the real inference sketch and is referenced by the
  orchestrator architecture.  The local SatQuery backend does NOT load
  EarthDial locally — inference is delegated to the remote Kaggle worker
  via EarthDialWorkerClient (app/services/remote_worker.py).

  This class is the "what would run on Kaggle" side of the architecture.

TO SWITCH TO REAL LOCAL INFERENCE (Kaggle / Colab only):
  1. Install dependencies on the GPU machine:
       pip install transformers torch accelerate
  2. Implement _run_real() below.
  3. Run the Kaggle notebook, expose via ngrok, set EARTHDIAL_WORKER_URL.
  4. The local service remains unchanged (it calls EarthDialWorkerClient).
"""

from loguru import logger
from app.config import settings


class EarthDialModel:
    """
    Stub wrapper for the EarthDial-4B-MS vision-language model.

    On the local backend this is never instantiated — the backend
    only calls EarthDialWorkerClient (HTTP).  This class documents
    what runs inside the remote Kaggle worker.
    """

    MODEL_ID = "MBZUAI/EarthDial-4B-MS"

    def __init__(self) -> None:
        self.mode = settings.model_mode
        logger.info(f"EarthDialModel initialised | mode={self.mode}")

        if self.mode == "real":
            self._load_real_model()

    def _load_real_model(self) -> None:
        """
        Load EarthDial-4B-MS model weights from HuggingFace Hub.

        ── STUB ─────────────────────────────────────────────────────────────
        This is intentionally not implemented locally.
        EarthDial-4B-MS requires ≈8 GB VRAM in fp16 (Kaggle T4 / A100).
        Implement this on the Kaggle notebook worker, NOT locally.

        Implementation sketch (inside Kaggle worker notebook):

            from transformers import AutoProcessor, AutoModelForVision2Seq
            import torch

            self.processor = AutoProcessor.from_pretrained(
                self.MODEL_ID, trust_remote_code=True
            )
            self.model = AutoModelForVision2Seq.from_pretrained(
                self.MODEL_ID,
                trust_remote_code=True,
                torch_dtype=torch.float16,
                device_map="auto",
            )
            self.model.eval()
        ─────────────────────────────────────────────────────────────────────
        """
        logger.warning(
            "EarthDialModel real inference is not implemented locally. "
            "Use EarthDialWorkerClient to call the remote Kaggle worker."
        )
        self.mode = "mock"

    def infer(self, image: str | None, question: str) -> dict:
        """
        Run inference on a single satellite image.

        Args:
            image:    Path or URL to image file (None → text-only question)
            question: The natural-language question about the image

        Returns:
            dict with keys: answer, confidence
        """
        if self.mode == "real":
            return self._run_real(image, question)
        return self._run_mock(image, question)

    def _run_mock(self, image: str | None, question: str) -> dict:
        """
        Return a clearly-labelled mock result.
        Used during development when the real model is not available.
        """
        logger.debug(f"EarthDialModel MOCK inference | image={image} | question={question}")
        image_desc = f" of image '{image}'" if image else ""
        return {
            "answer": (
                f"[MOCK — EarthDial-4B-MS] Analysis{image_desc}: "
                "This appears to be a multispectral remote-sensing image. "
                "Visible features include mixed land cover with urban fabric, "
                "vegetation patches (likely cropland and sparse woodland), "
                "and a water body in the lower portion of the scene. "
                "Multiple building footprints are discernible in the central area, "
                "consistent with a peri-urban settlement. "
                f"(Question received: '{question}')"
            ),
            "confidence": None,
        }

    def _run_real(self, image: str | None, question: str) -> dict:
        """
        Run actual EarthDial-4B-MS inference.

        ── STUB ─────────────────────────────────────────────────────────────
        Implementation sketch (inside Kaggle worker, not locally):

            from PIL import Image
            import torch, requests
            from io import BytesIO

            pil_image = None
            if image:
                if image.startswith("http"):
                    resp = requests.get(image)
                    pil_image = Image.open(BytesIO(resp.content)).convert("RGB")
                else:
                    pil_image = Image.open(image).convert("RGB")

            inputs = self.processor(
                images=pil_image,
                text=question,
                return_tensors="pt",
            ).to("cuda")

            with torch.no_grad():
                output_ids = self.model.generate(**inputs, max_new_tokens=512)
            answer = self.processor.batch_decode(output_ids, skip_special_tokens=True)[0]
            return {"answer": answer, "confidence": None}
        ─────────────────────────────────────────────────────────────────────
        """
        logger.warning("EarthDialModel._run_real called but not implemented — using mock")
        return self._run_mock(image, question)
