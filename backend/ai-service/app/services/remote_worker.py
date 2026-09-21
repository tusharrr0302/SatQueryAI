"""
app/services/remote_worker.py
─────────────────────────────────────────────────────────────────────────────
Remote Kaggle GPU Worker client abstraction.

ARCHITECTURE:
  Each specialist capability runs on its own independent Kaggle notebook.
  The local AI-service communicates with these workers via HTTPS (ngrok).

  Local service                Kaggle Notebook (ngrok)
  ─────────────────            ──────────────────────────────
  GeoChatWorkerClient    →     Worker 1: GeoChat-7B
                               GET  /health
                               POST /tools/analyze_image

  ChangeDetectionWorkerClient → Worker 2: VisTA + Prithvi
                               GET  /health
                               POST /tools/detect_change

  SAROpticalWorkerClient  →   Worker 3: CLASP + TerraFM
                               GET  /health
                               POST /tools/analyze_sar_optical

MOCK MODE vs REAL MODE:
  model_mode = "mock"  → returns local mock results, NO HTTP request sent
  model_mode = "real"  → sends HTTPS request to the configured ngrok URL

  This means the full architecture works without Kaggle being online.
  Only switch to real mode when a worker notebook is running.

WORKER URL CONFIGURATION:
  URLs are read from environment variables — never hardcoded:
    GEOCHAT_WORKER_URL
    CHANGE_DETECTION_WORKER_URL
    VISTA_WORKER_URL
    SAR_OPTICAL_WORKER_URL

  To update: change the URL in .env. No code changes required.

IMPORTANT — IMAGE PATHS vs URLS:
  Kaggle workers receive HTTP requests. They CANNOT access local file paths
  from your development machine. When model_mode="real":
    - image must be a publicly accessible URL or a signed S3/GCS URL
    - local paths (/path/to/image.tif) will cause worker errors
  The local service logs a warning when a local path is passed in real mode.
"""

import httpx
from typing import Any, Optional
from loguru import logger

from app.config import settings


# ─────────────────────────────────────────────────────────────────────────────
# Base Worker Client
# ─────────────────────────────────────────────────────────────────────────────

class RemoteWorkerClient:
    """
    Abstract base for all remote Kaggle GPU worker clients.

    Subclasses implement:
      - worker_url (property) → the specific ngrok URL from config
      - endpoint (property)   → e.g. "/tools/analyze_image"
      - _mock_result()        → returns a local mock result dict
      - call()                → builds the request body and calls _post()
    """

    @property
    def worker_url(self) -> str:
        raise NotImplementedError

    @property
    def endpoint(self) -> str:
        raise NotImplementedError

    @property
    def worker_name(self) -> str:
        """Human-readable name for logging."""
        return self.__class__.__name__

    def health_check(self) -> dict[str, Any]:
        """
        Check if the remote worker is reachable and healthy.

        Returns:
            dict with 'status' key. 'status'='ok' if healthy.
            Returns {'status': 'unavailable', 'error': ...} on failure.
        """
        if settings.model_mode != "real":
            return {"status": "mock", "worker": self.worker_name}

        if not self.worker_url:
            return {
                "status": "not_configured",
                "worker": self.worker_name,
                "error": f"Worker URL not set in environment",
            }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.worker_url}/health")
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as e:
            logger.warning(f"[{self.worker_name}] Health check failed (connection): {e}")
            return {"status": "unavailable", "error": str(e)}
        except httpx.TimeoutException:
            logger.warning(f"[{self.worker_name}] Health check timed out")
            return {"status": "unavailable", "error": "timeout"}
        except Exception as e:
            logger.warning(f"[{self.worker_name}] Health check error: {e}")
            return {"status": "unavailable", "error": str(e)}

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        """
        Send an HTTP POST request to the worker endpoint.

        Args:
            body: JSON-serializable request body

        Returns:
            Parsed JSON response from the worker

        Raises:
            RuntimeError on any HTTP/network failure with a structured message
        """
        url = f"{self.worker_url.rstrip('/')}{self.endpoint}"
        logger.info(f"[{self.worker_name}] POST {url}")
        logger.debug(f"[{self.worker_name}] Request body: {body}")

        try:
            req_headers = {"ngrok-skip-browser-warning": "true", "User-Agent": "SatQuery-AI-WorkerClient/1.0"}
            with httpx.Client(timeout=settings.worker_timeout_seconds, headers=req_headers) as client:
                response = client.post(url, json=body)
                response.raise_for_status()
                result = response.json()
                logger.info(f"[{self.worker_name}] Response received | status={result.get('status', '?')}")
                logger.debug(f"[{self.worker_name}] Response: {result}")
                return result

        except httpx.ConnectError as e:
            msg = (
                f"{self.worker_name} is unreachable at {self.worker_url}. "
                f"Check that the Kaggle notebook is running and ngrok is active. "
                f"Error: {e}"
            )
            logger.error(f"[{self.worker_name}] Connection failed: {e}")
            raise RuntimeError(msg) from e

        except httpx.TimeoutException:
            msg = (
                f"{self.worker_name} timed out after {settings.worker_timeout_seconds}s. "
                f"The GPU worker may be busy or the model is still loading."
            )
            logger.error(f"[{self.worker_name}] Timeout after {settings.worker_timeout_seconds}s")
            raise RuntimeError(msg)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                msg = f"{self.worker_name} endpoint not found: {self.endpoint} at {self.worker_url}. (HTTP 404)"
            else:
                msg = (
                    f"{self.worker_name} returned HTTP {e.response.status_code}: "
                    f"{e.response.text[:200]}"
                )
            logger.error(f"[{self.worker_name}] HTTP error: {e}")
            raise RuntimeError(msg) from e

        except Exception as e:
            logger.error(f"[{self.worker_name}] Unexpected error: {e}")
            raise RuntimeError(f"{self.worker_name} error: {e}") from e

    def _validate_image_for_real_mode(self, image: Optional[str]) -> None:
        """
        Log a warning if a local file path is passed in real mode.
        Remote workers cannot access local machine file paths.
        """
        if image and not image.startswith(("http://", "https://")):
            logger.warning(
                f"[{self.worker_name}] Real mode: image '{image}' appears to be a local "
                f"path. Remote workers require a public or signed URL. "
                f"The worker will receive this path as-is and may fail."
            )

    def _mock_result(self, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────────────
# Worker 1: GeoChat-7B → /tools/analyze_image
# ─────────────────────────────────────────────────────────────────────────────

class GeoChatWorkerClient(RemoteWorkerClient):
    """
    Client for the GeoChat Kaggle notebook worker.

    Remote API contract:
      POST /tools/analyze_image
      Request:  { "image_url": str|null, "query": str }
      Response: { "tool": "analyze_image", "status": "success",
                  "model": "GeoChat-7B", "mode": "mock"|"real",
                  "result": { "answer": str, "confidence": float|null } }
    """

    MODEL_ID = "MBZUAI/GeoChat-7B"

    @property
    def worker_url(self) -> str:
        return settings.geochat_worker_url

    @property
    def endpoint(self) -> str:
        return "/tools/analyze_image"

    @property
    def worker_name(self) -> str:
        return "GeoChatWorker"

    def call(self, image: Optional[str], query: str) -> dict[str, Any]:
        """
        Call analyze_image on the GeoChat worker.

        Args:
            image: Image path or URL (None if text-only)
            query: The question/analysis request

        Returns:
            dict: { "answer": str, "confidence": float|null, "mode": str, "model": str }
        """
        if settings.model_mode != "real":
            logger.debug(f"[GeoChatWorker] Mock mode — returning local mock")
            return self._mock_result(image=image, query=query)

        if not self.worker_url:
            raise RuntimeError(
                "GeoChatWorker URL not configured. "
                "Set GEOCHAT_WORKER_URL in .env to enable real inference."
            )

        self._validate_image_for_real_mode(image)

        body = {
            "image_url": image,
            "query": query,
        }

        raw = self._post(body)
        return self._parse_response(raw)

    def _parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize the worker response to the internal result dict format."""
        if raw.get("status") != "success":
            raise RuntimeError(
                f"GeoChat worker returned non-success status: {raw.get('status')} "
                f"— {raw.get('error', 'unknown error')}"
            )
        result = raw.get("result", {})
        return {
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence"),
            "mode": raw.get("mode", "real"),
            "model": raw.get("model", self.MODEL_ID),
        }

    def _mock_result(self, image: Optional[str] = None, query: str = "") -> dict[str, Any]:
        logger.debug(f"[GeoChatWorker] MOCK inference | image={image} | query={query}")
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
            "confidence": None,
            "mode": "mock",
            "model": self.MODEL_ID,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Worker 2: VisTA + Prithvi-EO-2.0-300M → /tools/detect_change
# ─────────────────────────────────────────────────────────────────────────────

class ChangeDetectionWorkerClient(RemoteWorkerClient):
    """
    Client for the Change Detection Kaggle notebook worker.
    The worker internally selects between VisTA and Prithvi-EO-2.0-300M
    based on the analysis_mode supplied by GPT-OSS.

    Remote API contract:
      POST /tools/detect_change
      Request:  { "image_t1_url": str|null, "image_t2_url": str|null,
                  "query": str, "analysis_mode": str|null }
      Response: { "tool": "detect_change", "status": "success",
                  "model": "like413/vista"|"ibm-nasa-geospatial/Prithvi-EO-2.0-300M",
                  "mode": "mock"|"real",
                  "result": { "answer": str, "confidence": float|null,
                               "change_mask": null|dict } }

    analysis_mode values:
      "question_change"        → VisTA (Change Detection QA & visual grounding)
      "multitemporal_analysis" → Prithvi-EO-2.0-300M pipeline
      None                     → worker defaults to VisTA
    """

    VISTA_MODEL_ID = "like413/vista"
    PRITHVI_MODEL_ID = "ibm-nasa-geospatial/Prithvi-EO-2.0-300M"

    @property
    def worker_url(self) -> str:
        return settings.change_detection_worker_url

    @property
    def endpoint(self) -> str:
        return "/tools/detect_change"

    @property
    def worker_name(self) -> str:
        return "ChangeDetectionWorker"

    def call(
        self,
        image_t1: Optional[str],
        image_t2: Optional[str],
        query: str,
        analysis_mode: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Call detect_change on the change detection worker.

        Args:
            image_t1: Before image path/URL
            image_t2: After image path/URL
            query: Change detection question
            analysis_mode: Optional mode set by GPT-OSS:
              'question_change'        → VisTA
              'multitemporal_analysis' → Prithvi-EO-2.0-300M
              None                     → worker defaults to VisTA

        Returns:
            dict: { "answer": str, "confidence": float|null, "change_mask": ...,
                    "mode": str, "model": str }
        """
        if settings.model_mode != "real":
            logger.debug(f"[ChangeDetectionWorker] Mock mode — returning local mock")
            return self._mock_result(
                image_t1=image_t1, image_t2=image_t2,
                query=query, analysis_mode=analysis_mode,
            )

        if not self.worker_url:
            raise RuntimeError(
                "ChangeDetectionWorker URL not configured. "
                "Set CHANGE_DETECTION_WORKER_URL in .env to enable real inference."
            )

        self._validate_image_for_real_mode(image_t1)
        self._validate_image_for_real_mode(image_t2)

        body = {
            "image_t1_url": image_t1,
            "image_t2_url": image_t2,
            "query": query,
            "analysis_mode": analysis_mode,
        }

        raw = self._post(body)
        return self._parse_response(raw)

    def _parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        if raw.get("status") != "success":
            raise RuntimeError(
                f"ChangeDetectionWorker returned non-success status: {raw.get('status')} "
                f"— {raw.get('error', 'unknown error')}"
            )
        result = raw.get("result", {})
        return {
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence"),
            "change_mask": result.get("change_mask"),
            "mode": raw.get("mode", "real"),
            "model": raw.get("model", self.VISTA_MODEL_ID),
        }

    def _mock_result(
        self,
        image_t1: Optional[str] = None,
        image_t2: Optional[str] = None,
        query: str = "",
        analysis_mode: Optional[str] = None,
    ) -> dict[str, Any]:
        # analysis_mode drives specialist selection in mock (mirrors the real worker)
        use_prithvi = analysis_mode == "multitemporal_analysis"

        if use_prithvi:
            model = self.PRITHVI_MODEL_ID
            answer = (
                "[MOCK — Prithvi-EO-2.0-300M] Multi-spectral change analysis: "
                "Processing HLS-format inputs across 6 spectral bands (Blue, Green, "
                "Red, NIR, SWIR-1, SWIR-2). Change detection segmentation identifies "
                "three primary change classes: "
                "(1) Flood inundation — new water coverage detected in low-lying areas "
                "(SWIR-1 decrease, NIR decrease), estimated extent ~340 hectares. "
                "(2) Vegetation recovery — NDVI increase in previously disturbed areas. "
                "(3) Bare soil exposure — likely infrastructure development. "
                f"(Query: '{query}')"
            )
        else:
            model = self.VISTA_MODEL_ID
            answer = (
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
            )

        logger.debug(f"[ChangeDetectionWorker] MOCK | t1={image_t1} | t2={image_t2} | model={model}")
        return {
            "answer": answer,
            "confidence": None,
            "change_mask": None,
            "mode": "mock",
            "model": model,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Worker 2A: VisTA → /tools/detect_change
# ─────────────────────────────────────────────────────────────────────────────

class VisTAWorkerClient(RemoteWorkerClient):
    """
    Client for the dedicated VisTA Kaggle notebook worker.
    Used for bi-temporal Change Detection Question Answering and Visual Grounding
    (analysis_mode='question_change').

    Remote API contract:
      POST /tools/detect_change
      Request:  {
                  "image_t1": str|null,
                  "image_t2": str|null,
                  "query": str,
                  "metadata_t1": dict|null,
                  "metadata_t2": dict|null,
                }
      Response: {
                  "tool": "detect_change",
                  "status": "success",
                  "model": "VisTA",
                  "mode": "mock"|"real",
                  "result": {
                    "answer": str,
                    "confidence": float|null,
                    "change_detected": bool|null,
                    "change_mask": dict|null
                  }
                }
    """

    VISTA_MODEL_ID = "like413/vista"

    @property
    def worker_url(self) -> str:
        return settings.vista_worker_url

    @property
    def endpoint(self) -> str:
        return "/tools/detect_change"

    @property
    def worker_name(self) -> str:
        return "VisTAWorker"

    def call(
        self,
        image_t1: Optional[str],
        image_t2: Optional[str],
        query: str,
        metadata_t1: Optional[dict[str, Any]] = None,
        metadata_t2: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Call detect_change on the VisTA remote worker.

        Args:
            image_t1: Before image path/URL (or None)
            image_t2: After image path/URL (or None)
            query: Change detection question
            metadata_t1: Optional metadata for image_t1
            metadata_t2: Optional metadata for image_t2

        Returns:
            dict: {
                "answer": str,
                "confidence": float|null,
                "change_mask": dict|null,
                "change_detected": bool|null,
                "mode": str,
                "model": str,
            }
        """
        if settings.model_mode != "real":
            logger.debug("[VisTAWorker] Mock mode — returning local mock")
            return self._mock_result(
                image_t1=image_t1,
                image_t2=image_t2,
                query=query,
                metadata_t1=metadata_t1,
                metadata_t2=metadata_t2,
            )

        if not self.worker_url:
            raise RuntimeError(
                "VisTAWorker URL not configured. "
                "Set VISTA_WORKER_URL in .env to enable real inference."
            )

        self._validate_image_for_real_mode(image_t1)
        self._validate_image_for_real_mode(image_t2)

        meta_t1 = metadata_t1.model_dump() if hasattr(metadata_t1, "model_dump") else metadata_t1
        meta_t2 = metadata_t2.model_dump() if hasattr(metadata_t2, "model_dump") else metadata_t2

        body = {
            "image_t1": image_t1,
            "image_t2": image_t2,
            "query": query,
            "metadata_t1": meta_t1,
            "metadata_t2": meta_t2,
        }

        raw = self._post(body)
        return self._parse_response(raw)

    def _parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        if raw.get("status") != "success":
            raise RuntimeError(
                f"VisTA worker returned non-success status: {raw.get('status')} "
                f"— {raw.get('error', 'unknown error')}"
            )
        result = raw.get("result", {})
        return {
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence"),
            "change_mask": result.get("change_mask"),
            "change_detected": result.get("change_detected"),
            "mode": raw.get("mode", "real"),
            "model": raw.get("model", self.VISTA_MODEL_ID),
        }

    def _mock_result(
        self,
        image_t1: Optional[str] = None,
        image_t2: Optional[str] = None,
        query: str = "",
        metadata_t1: Optional[dict[str, Any]] = None,
        metadata_t2: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        logger.debug(f"[VisTAWorker] MOCK inference | t1={image_t1} | t2={image_t2} | query={query}")
        return {
            "answer": (
                "[MOCK — VisTA] Bi-temporal change analysis: Comparison between the "
                "two observation periods reveals localized changes consistent with "
                "urban structural expansion and ground disturbance. "
                f"(Query: '{query}')"
            ),
            "confidence": None,
            "change_mask": None,
            "change_detected": True,
            "mode": "mock",
            "model": self.VISTA_MODEL_ID,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Worker 2B: Prithvi-EO-2.0-300M → /tools/analyze_multitemporal
# ─────────────────────────────────────────────────────────────────────────────

class PrithviWorkerClient(RemoteWorkerClient):
    """
    Client for the dedicated Prithvi-EO-2.0-300M Kaggle notebook worker.
    Used for 4-frame temporal analysis (analysis_mode='multitemporal_analysis').

    Remote API contract:
      POST /tools/analyze_multitemporal
      Request:  {
                  "image_t1": str|null,
                  "image_t2": str|null,
                  "image_t3": str|null,
                  "image_t4": str|null,
                  "query": str,
                  "metadata_t1": dict|null,
                  "metadata_t2": dict|null,
                  "metadata_t3": dict|null,
                  "metadata_t4": dict|null,
                }
      Response: {
                  "tool": "analyze_multitemporal",
                  "status": "success",
                  "model": "Prithvi-EO-2.0-300M",
                  "mode": "mock"|"real",
                  "result": {
                    "answer": str,
                    "change_detected": bool,
                    "confidence": float|null,
                    "change_percentage": float,
                    "temporal_frames": int,
                    "change_analysis": dict,
                    "model_output": dict
                  }
                }

    Scientific Note:
      Prithvi-EO-2.0-300M is a masked autoencoder foundation model, not a native
      semantic change detector. The worker performs temporal spectral-difference
      analysis after Prithvi processing/reconstruction.
    """

    MODEL_ID = "ibm-nasa-geospatial/Prithvi-EO-2.0-300M"

    @property
    def worker_url(self) -> str:
        return settings.prithvi_worker_url

    @property
    def endpoint(self) -> str:
        return "/tools/analyze_multitemporal"

    @property
    def worker_name(self) -> str:
        return "PrithviWorker"

    def call(
        self,
        image_t1: Optional[str],
        image_t2: Optional[str],
        image_t3: Optional[str] = None,
        image_t4: Optional[str] = None,
        query: str = "",
        metadata_t1: Optional[dict[str, Any]] = None,
        metadata_t2: Optional[dict[str, Any]] = None,
        metadata_t3: Optional[dict[str, Any]] = None,
        metadata_t4: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Call analyze_multitemporal on the Prithvi remote worker.

        Args:
            image_t1: First temporal frame image URL (or None)
            image_t2: Second temporal frame image URL (or None)
            image_t3: Third temporal frame image URL (or None)
            image_t4: Fourth temporal frame image URL (or None)
            query: Analysis question / description
            metadata_t1: Optional metadata for image_t1
            metadata_t2: Optional metadata for image_t2
            metadata_t3: Optional metadata for image_t3
            metadata_t4: Optional metadata for image_t4

        Returns:
            dict: {
                "answer": str,
                "change_detected": bool,
                "confidence": float|null,
                "change_percentage": float,
                "temporal_frames": int,
                "change_analysis": dict,
                "model_output": dict,
                "mode": str,
                "model": str,
            }
        """
        if settings.model_mode != "real":
            logger.debug("[PrithviWorker] Mock mode — returning local mock")
            return self._mock_result(
                image_t1=image_t1,
                image_t2=image_t2,
                image_t3=image_t3,
                image_t4=image_t4,
                query=query,
                metadata_t1=metadata_t1,
                metadata_t2=metadata_t2,
                metadata_t3=metadata_t3,
                metadata_t4=metadata_t4,
            )

        if not self.worker_url:
            raise RuntimeError(
                "PrithviWorker URL not configured. "
                "Set PRITHVI_WORKER_URL in .env to enable real inference."
            )

        self._validate_image_for_real_mode(image_t1)
        self._validate_image_for_real_mode(image_t2)
        self._validate_image_for_real_mode(image_t3)
        self._validate_image_for_real_mode(image_t4)

        meta_t1 = metadata_t1.model_dump() if hasattr(metadata_t1, "model_dump") else metadata_t1
        meta_t2 = metadata_t2.model_dump() if hasattr(metadata_t2, "model_dump") else metadata_t2
        meta_t3 = metadata_t3.model_dump() if hasattr(metadata_t3, "model_dump") else metadata_t3
        meta_t4 = metadata_t4.model_dump() if hasattr(metadata_t4, "model_dump") else metadata_t4

        body = {
            "image_t1": image_t1,
            "image_t2": image_t2,
            "image_t3": image_t3,
            "image_t4": image_t4,
            "query": query,
            "metadata_t1": meta_t1,
            "metadata_t2": meta_t2,
            "metadata_t3": meta_t3,
            "metadata_t4": meta_t4,
        }

        raw = self._post(body)
        return self._parse_response(raw)

    def _parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        if raw.get("status") != "success":
            raise RuntimeError(
                f"Prithvi worker returned non-success status: {raw.get('status')} "
                f"— {raw.get('error', 'unknown error')}"
            )
        result = raw.get("result", {})
        return {
            "answer": result.get("answer", ""),
            "change_detected": result.get("change_detected"),
            "confidence": result.get("confidence"),
            "change_percentage": result.get("change_percentage"),
            "temporal_frames": result.get("temporal_frames", 4),
            "change_analysis": result.get("change_analysis"),
            "model_output": result.get("model_output"),
            "mode": raw.get("mode", "real"),
            "model": raw.get("model", self.MODEL_ID),
        }

    def _mock_result(
        self,
        image_t1: Optional[str] = None,
        image_t2: Optional[str] = None,
        image_t3: Optional[str] = None,
        image_t4: Optional[str] = None,
        query: str = "",
        metadata_t1: Optional[dict[str, Any]] = None,
        metadata_t2: Optional[dict[str, Any]] = None,
        metadata_t3: Optional[dict[str, Any]] = None,
        metadata_t4: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        logger.debug(
            f"[PrithviWorker] MOCK inference | t1={image_t1} | t2={image_t2} | "
            f"t3={image_t3} | t4={image_t4} | query={query}"
        )
        return {
            "answer": (
                "[MOCK — Prithvi-EO-2.0-300M] Temporal analysis detected significant "
                "spectral differences across approximately 10.00% of the analyzed area "
                "between the first and latest observations. "
                f"(Query: '{query}')"
            ),
            "change_detected": True,
            "confidence": None,
            "change_percentage": 10.0,
            "temporal_frames": 4,
            "change_analysis": {
                "threshold": 0.5859819054603577,
                "changed_pixels": 25088,
                "total_pixels": 250880,
            },
            "model_output": {
                "original_shape": [1, 6, 4, 448, 560],
                "reconstruction_shape": [1, 6, 4, 448, 560],
                "mask_shape": [1, 6, 4, 448, 560],
                "temporal_coordinates": [
                    [
                        [2018.0, 26.0],
                        [2018.0, 106.0],
                        [2018.0, 201.0],
                        [2018.0, 266.0],
                    ]
                ],
                "location_coordinates": [
                    [-104.70301818847656, 28.715795516967773],
                ],
            },
            "mode": "mock",
            "model": self.MODEL_ID,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Worker 3: CLASP + TerraFM → /tools/analyze_sar_optical
# ─────────────────────────────────────────────────────────────────────────────

class SAROpticalWorkerClient(RemoteWorkerClient):
    """
    Client for the SAR+Optical Kaggle notebook worker.
    The worker internally selects between CLASP and TerraFM.

    Remote API contract:
      POST /tools/analyze_sar_optical
      Request:  { "sar_image_url": str|null, "optical_image_url": str|null,
                  "query": str, "model_hint": str|null }
      Response: { "tool": "analyze_sar_optical", "status": "success",
                  "model": "DarthReca/closp"|"mbzuai-oryx/TerraFM",
                  "mode": "mock"|"real",
                  "result": { "answer": str, "confidence": float|null } }
    """

    CLASP_MODEL_ID = "DarthReca/closp"
    TERRAFM_MODEL_ID = "mbzuai-oryx/TerraFM"

    @property
    def worker_url(self) -> str:
        return settings.sar_optical_worker_url

    @property
    def endpoint(self) -> str:
        return "/tools/analyze_sar_optical"

    @property
    def worker_name(self) -> str:
        return "SAROpticalWorker"

    def call(
        self,
        sar_image: Optional[str],
        optical_image: Optional[str],
        query: str,
        model_hint: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Call analyze_sar_optical on the SAR+optical worker.

        Args:
            sar_image: SAR image path/URL (e.g. Sentinel-1 GRD)
            optical_image: Optical image path/URL (e.g. Sentinel-2)
            query: Cross-modal analysis question
            model_hint: Optional preference ('clasp' or 'terrafm') for the worker
        """
        if settings.model_mode != "real":
            logger.debug(f"[SAROpticalWorker] Mock mode — returning local mock")
            return self._mock_result(
                sar_image=sar_image, optical_image=optical_image,
                query=query, model_hint=model_hint,
            )

        if not self.worker_url:
            raise RuntimeError(
                "SAROpticalWorker URL not configured. "
                "Set SAR_OPTICAL_WORKER_URL in .env to enable real inference."
            )

        self._validate_image_for_real_mode(sar_image)
        self._validate_image_for_real_mode(optical_image)

        body = {
            "sar_image_url": sar_image,
            "optical_image_url": optical_image,
            "query": query,
            "model_hint": model_hint,
        }

        raw = self._post(body)
        return self._parse_response(raw)

    def _parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        if raw.get("status") != "success":
            raise RuntimeError(
                f"SAROpticalWorker returned non-success status: {raw.get('status')} "
                f"— {raw.get('error', 'unknown error')}"
            )
        result = raw.get("result", {})
        return {
            "answer": result.get("answer", ""),
            "confidence": result.get("confidence"),
            "mode": raw.get("mode", "real"),
            "model": raw.get("model", self.CLASP_MODEL_ID),
        }

    def _mock_result(
        self,
        sar_image: Optional[str] = None,
        optical_image: Optional[str] = None,
        query: str = "",
        model_hint: Optional[str] = None,
    ) -> dict[str, Any]:
        use_terrafm = model_hint == "terrafm" or any(
            kw in query.lower() for kw in ["classify", "classification", "land cover", "terrain", "map"]
        )

        if use_terrafm:
            model = self.TERRAFM_MODEL_ID
            answer = (
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
                f"(Query: '{query}')"
            )
        else:
            model = self.CLASP_MODEL_ID
            answer = (
                "[MOCK — CLASP] Cross-modal SAR+optical fusion analysis: "
                "Aligning SAR (Sentinel-1 C-band, VV+VH polarisation) with "
                "optical (Sentinel-2 RGB+NIR) using contrastive cross-modal embeddings. "
                "Fusion results: Flooded regions are confirmed by both modalities — "
                "SAR shows increased backscatter in inundated areas while optical "
                "confirms turbid water appearance. "
                "Building damage assessment: 23 structures show anomalous SAR "
                "double-bounce signatures inconsistent with optical appearance, "
                "indicating potential roof collapse. "
                "Cloud-covered area in optical image is resolved using SAR data. "
                f"(Query: '{query}')"
            )

        logger.debug(f"[SAROpticalWorker] MOCK | sar={sar_image} | optical={optical_image} | model={model}")
        return {
            "answer": answer,
            "confidence": None,
            "mode": "mock",
            "model": model,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Worker 4: EarthDial-4B-MS → /analyze
# Replaces GeoChat as the semantic EO vision-language specialist.
# ─────────────────────────────────────────────────────────────────────────────

class EarthDialWorkerClient(RemoteWorkerClient):
    """
    Client for the EarthDial-4B-MS Kaggle notebook worker.

    EarthDial-4B-MS is the current semantic EO vision-language specialist,
    replacing GeoChat-7B. It runs on a remote Kaggle GPU and is exposed
    via an ngrok HTTPS tunnel.

    The local backend does NOT load EarthDial. It is a pure HTTP client.

    Remote API contract (EarthDial Kaggle worker):
      GET  /health
      POST /analyze
      Request:  { "image_url": str|null, "question": str }
      Response: { "answer": str, "model": str, "mode": "mock"|"real" }

    Configuration:
      EARTHDIAL_WORKER_URL=https://xxxxx.ngrok-free.app

    Do NOT place HF_TOKEN or NGROK_AUTHTOKEN here — those remain on Kaggle.
    """

    MODEL_ID = "MBZUAI/EarthDial-4B-MS"

    @property
    def worker_url(self) -> str:
        return settings.earthdial_worker_url

    @property
    def endpoint(self) -> str:
        return "/analyze"

    @property
    def worker_name(self) -> str:
        return "EarthDialWorker"

    def call(self, image: Optional[str], question: str) -> dict[str, Any]:
        """
        Call the EarthDial worker for single-image remote-sensing VQA.

        Args:
            image: Publicly accessible image URL (or None for text-only).
                   Local file paths will NOT work in real mode — the Kaggle
                   worker cannot access the local machine's filesystem.
            question: The natural-language question / analysis request.

        Returns:
            dict: { "answer": str, "confidence": float|null, "mode": str, "model": str }

        Image format notes:
          - JPEG / PNG: supported directly by the worker.
          - GeoTIFF: the worker handles model-specific preprocessing internally.
            Do NOT preprocess or reorder bands locally unless the worker
            explicitly requires a pre-converted RGB JPEG.
          - Multispectral / multi-band: do not silently drop or reorder bands.
            Pass the image URL as-is; the Kaggle EarthDial worker owns
            the band-handling logic.
        """
        if settings.model_mode != "real":
            logger.debug("[EarthDialWorker] Mock mode — returning local mock")
            return self._mock_result(image=image, question=question)

        if not self.worker_url:
            raise RuntimeError(
                "EarthDialWorker URL not configured. "
                "Set EARTHDIAL_WORKER_URL in .env to enable real inference."
            )

        self._validate_image_for_real_mode(image)

        body = {
            "image_url": image,
            "question": question,
        }

        raw = self._post(body)
        return self._parse_response(raw)

    def _parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalise the EarthDial worker response to the internal result format."""
        # The worker returns a flat dict (not nested under "result")
        # Contract: { "answer": str, "model": str, "mode": str }
        if not raw.get("answer"):
            raise RuntimeError(
                f"EarthDial worker returned an unexpected response: {raw}"
            )
        return {
            "answer": raw.get("answer", ""),
            "confidence": raw.get("confidence"),
            "mode": raw.get("mode", "real"),
            "model": raw.get("model", self.MODEL_ID),
        }

    def _mock_result(
        self,
        image: Optional[str] = None,
        question: str = "",
    ) -> dict[str, Any]:
        logger.debug(f"[EarthDialWorker] MOCK inference | image={image} | question={question}")
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
            "mode": "mock",
            "model": self.MODEL_ID,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Worker 5a: CLOSP → dedicated worker
# SAR+optical cross-modal embedding/similarity specialist.
# ─────────────────────────────────────────────────────────────────────────────

class CLOSPWorkerClient(RemoteWorkerClient):
    """
    Client for the dedicated CLOSP Kaggle notebook worker.

    CLOSP (Cross-modal Learning for SAR and Optical image Pairs) is a
    contrastive embedding model that aligns SAR and optical representations
    in a shared feature space.

    Primary capabilities:
      - Cross-modal SAR ↔ optical similarity / retrieval
      - Flood mapping (SAR penetrates cloud; optical gives colour context)
      - Building damage assessment (SAR double-bounce vs. optical appearance)
      - Structural change detection via cross-modal embedding distance

    CLOSP is an embedding/representation model.  It does NOT produce
    natural-language descriptions natively.  The worker translates its
    structured outputs (similarities, scores, embeddings) into a
    descriptive answer string.

    Remote API contract:
      GET  /health
      POST /analyze
      Request:  { "sar_image_url": str|null, "optical_image_url": str|null,
                  "query": str }
      Response: { "answer": str, "model": str, "mode": str,
                  "embeddings": dict|null, "similarity_score": float|null }

    Configuration:
      CLOSP_WORKER_URL=https://xxxxx.ngrok-free.app
    """

    MODEL_ID = "DarthReca/closp"

    @property
    def worker_url(self) -> str:
        return settings.closp_worker_url or settings.sar_optical_worker_url

    @property
    def endpoint(self) -> str:
        return "/tools/analyze_sar_optical"

    @property
    def legacy_endpoint(self) -> str:
        return "/analyze"

    @property
    def worker_name(self) -> str:
        return "CLOSPWorker"

    def call(
        self,
        sar_image: Optional[str],
        optical_image: Optional[str],
        query: str,
    ) -> dict[str, Any]:
        """
        Call the CLOSP worker for SAR+optical cross-modal analysis.

        Returns:
            dict with keys: answer, confidence, embeddings, similarity_score, mode, model
        """
        if settings.model_mode != "real":
            logger.debug("[CLOSPWorker] Mock mode — returning local mock")
            return self._mock_result(sar_image=sar_image, optical_image=optical_image, query=query)

        if not self.worker_url:
            raise RuntimeError(
                "CLOSPWorker URL not configured. "
                "Set CLOSP_WORKER_URL in .env to enable real inference."
            )

        self._validate_image_for_real_mode(sar_image)
        self._validate_image_for_real_mode(optical_image)

        body = {
            "sar_image_url": sar_image,
            "optical_image_url": optical_image,
            "query": query,
            "model_hint": "closp",
        }

        try:
            raw = self._post(body)
        except RuntimeError as e:
            if "HTTP 404" in str(e) or "endpoint not found" in str(e):
                logger.info(f"[CLOSPWorker] {self.endpoint} returned 404, checking legacy endpoint {self.legacy_endpoint}")
                legacy_url = f"{self.worker_url.rstrip('/')}{self.legacy_endpoint}"
                try:
                    req_headers = {"ngrok-skip-browser-warning": "true", "User-Agent": "SatQuery-AI-WorkerClient/1.0"}
                    with httpx.Client(timeout=settings.worker_timeout_seconds, headers=req_headers) as client:
                        resp = client.post(legacy_url, json=body)
                        resp.raise_for_status()
                        raw = resp.json()
                except Exception:
                    raise e
            else:
                raise
        return self._parse_response(raw)

    def _parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        answer = raw.get("answer")
        similarity = raw.get("cross_modal_similarity") or raw.get("similarity_score")
        if not answer:
            if similarity is not None:
                answer = (
                    f"CLOSP cross-modal analysis evaluated Sentinel-1 SAR (VV/VH) and "
                    f"Sentinel-2 optical imagery with alignment score of {float(similarity):.3f}."
                )
            else:
                answer = "CLOSP cross-modal analysis completed on Sentinel-1 SAR / Sentinel-2 optical imagery."
        return {
            "answer": answer,
            "confidence": raw.get("confidence"),
            "embeddings": raw.get("embeddings") or ({"sar": raw.get("sar"), "optical": raw.get("optical")} if raw.get("sar") else None),
            "similarity_score": similarity,
            "mode": raw.get("mode", "real"),
            "model": raw.get("model", self.MODEL_ID),
        }

    def _mock_result(
        self,
        sar_image: Optional[str] = None,
        optical_image: Optional[str] = None,
        query: str = "",
    ) -> dict[str, Any]:
        logger.debug(f"[CLOSPWorker] MOCK | sar={sar_image} | optical={optical_image} | query={query}")
        return {
            "answer": (
                "[MOCK — CLOSP] Cross-modal SAR+optical embedding analysis: "
                "Contrastive alignment of SAR (Sentinel-1 C-band, VV+VH) and "
                "optical (Sentinel-2 RGB+NIR) in shared embedding space. "
                "Cross-modal similarity score: 0.87 (high alignment). "
                "Flood mapping: SAR backscatter decrease in water-covered areas "
                "confirmed by optical turbidity signature — estimated inundation "
                "extent ~280 hectares. "
                "Building damage: 19 structures exhibit SAR double-bounce anomalies "
                "inconsistent with optical roof appearance (potential structural damage). "
                "Cloud-obscured optical areas resolved via SAR. "
                f"(Query: '{query}')"
            ),
            "confidence": None,
            "embeddings": None,
            "similarity_score": 0.87,
            "mode": "mock",
            "model": self.MODEL_ID,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Worker 5b: TerraFM → dedicated worker
# SAR+optical multisensor foundation model specialist.
# ─────────────────────────────────────────────────────────────────────────────

class TerraFMWorkerClient(RemoteWorkerClient):
    """
    Client for the dedicated TerraFM Kaggle notebook worker.

    TerraFM (mbzuai-oryx/TerraFM) is a large geospatial foundation model
    that handles multiple input modalities including SAR and optical.

    Primary capabilities:
      - Multi-sensor scene classification (SAR + optical fusion)
      - Terrain / land-cover mapping with multi-spectral input
      - Complex scene understanding across sensor modalities
      - Multi-temporal and multi-source data fusion

    TerraFM is preferred when the task requires broad semantic understanding
    or scene-level classification rather than cross-modal similarity.

    Remote API contract:
      GET  /health
      POST /analyze
      Request:  { "sar_image_url": str|null, "optical_image_url": str|null,
                  "query": str }
      Response: { "answer": str, "model": str, "mode": str,
                  "classifications": dict|null }

    Configuration:
      TERRAFM_WORKER_URL=https://xxxxx.ngrok-free.app
    """

    MODEL_ID = "mbzuai-oryx/TerraFM"

    @property
    def worker_url(self) -> str:
        return settings.terrafm_worker_url

    @property
    def endpoint(self) -> str:
        return "/analyze"

    @property
    def worker_name(self) -> str:
        return "TerraFMWorker"

    def call(
        self,
        sar_image: Optional[str],
        optical_image: Optional[str],
        query: str,
    ) -> dict[str, Any]:
        """
        Call the TerraFM worker for SAR+optical multi-sensor analysis.

        Returns:
            dict with keys: answer, confidence, classifications, mode, model
        """
        if settings.model_mode != "real":
            logger.debug("[TerraFMWorker] Mock mode — returning local mock")
            return self._mock_result(sar_image=sar_image, optical_image=optical_image, query=query)

        if not self.worker_url:
            raise RuntimeError(
                "TerraFMWorker URL not configured. "
                "Set TERRAFM_WORKER_URL in .env to enable real inference."
            )

        self._validate_image_for_real_mode(sar_image)
        self._validate_image_for_real_mode(optical_image)

        body = {
            "sar_image_url": sar_image,
            "optical_image_url": optical_image,
            "query": query,
        }

        raw = self._post(body)
        return self._parse_response(raw)

    def _parse_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        if not raw.get("answer"):
            raise RuntimeError(
                f"TerraFM worker returned an unexpected response: {raw}"
            )
        return {
            "answer": raw.get("answer", ""),
            "confidence": raw.get("confidence"),
            "classifications": raw.get("classifications"),
            "mode": raw.get("mode", "real"),
            "model": raw.get("model", self.MODEL_ID),
        }

    def _mock_result(
        self,
        sar_image: Optional[str] = None,
        optical_image: Optional[str] = None,
        query: str = "",
    ) -> dict[str, Any]:
        logger.debug(f"[TerraFMWorker] MOCK | sar={sar_image} | optical={optical_image} | query={query}")
        return {
            "answer": (
                "[MOCK — TerraFM] Multimodal terrain analysis (SAR + optical fusion): "
                "Foundation model processing of Sentinel-1 SAR and Sentinel-2 optical. "
                "Scene classification results: "
                "- Urban fabric (high-density): 34.2% of scene "
                "- Vegetation (mixed forest/shrubland): 28.7% "
                "- Agricultural land: 19.1% "
                "- Water bodies: 11.3% "
                "- Bare soil/construction sites: 6.7% "
                "SAR coherence indicates stable urban structures (no decorrelation). "
                "No evidence of flood events in the current observation period. "
                f"(Query: '{query}')"
            ),
            "confidence": None,
            "classifications": {
                "urban": 0.342,
                "vegetation": 0.287,
                "agriculture": 0.191,
                "water": 0.113,
                "bare_soil": 0.067,
            },
            "mode": "mock",
            "model": self.MODEL_ID,
        }
