"""
app/models/vista.py
─────────────────────────────────────────────────────────────────────────────
VisTA specialist model wrapper for bi-temporal change detection.

HuggingFace model: like413/vista
Task: Remote-sensing change detection between two temporal images.

VisTA (Vision Transformer Aggregator) detects semantic changes
between two co-registered satellite images taken at different times.
"""

from loguru import logger
from app.config import settings


class VisTAModel:
    """
    Wrapper for the VisTA change detection model.
    Called by the DetectChangeTool when change_model="vista".
    """

    MODEL_ID = "like413/vista"

    def __init__(self) -> None:
        self.mode = settings.model_mode
        logger.info(f"VisTAModel initialised | mode={self.mode}")

        if self.mode == "real":
            self._load_real_model()

    def _load_real_model(self) -> None:
        """
        ── STUB ─────────────────────────────────────────────────────────────
        Load VisTA weights from HuggingFace Hub.

        Implementation sketch:
            from transformers import AutoModelForImageSegmentation, AutoImageProcessor
            self.processor = AutoImageProcessor.from_pretrained(self.MODEL_ID)
            self.model = AutoModelForImageSegmentation.from_pretrained(
                self.MODEL_ID, device_map="auto"
            )
        ─────────────────────────────────────────────────────────────────────
        """
        logger.warning("VisTAModel real inference not yet implemented — using mock")
        self.mode = "mock"

    def infer(self, image_t1: str | None, image_t2: str | None, query: str) -> dict:
        """
        Detect changes between two temporal images.

        Args:
            image_t1: Path to earlier image
            image_t2: Path to later image
            query: Description of what changes to look for

        Returns:
            dict with keys: answer, change_mask (None in mock), confidence
        """
        if self.mode == "real":
            return self._run_real(image_t1, image_t2, query)
        return self._run_mock(image_t1, image_t2, query)

    def _run_mock(self, image_t1: str | None, image_t2: str | None, query: str) -> dict:
        logger.debug(f"VisTAModel MOCK | t1={image_t1} | t2={image_t2}")
        return {
            "answer": (
                "[MOCK — VisTA] Change detection analysis: Comparing the two "
                "provided temporal images, significant land cover change is "
                "detected in approximately 18% of the scene. "
                "The primary change category is 'Urban expansion': new impervious "
                "surfaces (roads and buildings) have appeared in the north-eastern "
                "quadrant. Additionally, a reduction in vegetation coverage (~12%) "
                "is observed along the western edge, possibly due to deforestation "
                "or seasonal variation. "
                "No significant water body changes detected. "
                f"(Query: '{query}')"
            ),
            "change_mask": None,   # In real mode: a binary segmentation mask
            "confidence": None,
        }

    def _run_real(self, image_t1: str | None, image_t2: str | None, query: str) -> dict:
        """
        ── STUB ─────────────────────────────────────────────────────────────
        Run real VisTA inference.

        Implementation sketch:
            from PIL import Image
            img1 = Image.open(image_t1).convert("RGB")
            img2 = Image.open(image_t2).convert("RGB")
            inputs = self.processor(images=[img1, img2], return_tensors="pt")
            outputs = self.model(**inputs)
            mask = outputs.logits.argmax(dim=1).squeeze().cpu().numpy()
            # Convert mask to a description or GeoJSON
        ─────────────────────────────────────────────────────────────────────
        """
        logger.warning("VisTAModel._run_real called but not implemented — using mock")
        return self._run_mock(image_t1, image_t2, query)
