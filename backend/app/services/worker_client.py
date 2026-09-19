import logging
import httpx
from app.config import settings
from app.schemas.normalized_result import NormalizedResult

logger = logging.getLogger(__name__)


class WorkerClient:
    """
    Handles calling an external EO specialist worker.
    """

    async def execute(self, query: str, model_id: str, dataset_ids: list[str], analysis_type: str) -> NormalizedResult:
        mode = (settings.MODEL_MODE or "mock").lower()

        if mode == "worker" and settings.PRITHVI_WORKER_URL:
            try:
                logger.info(f"Dispatching query to worker URL: {settings.PRITHVI_WORKER_URL}")
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{settings.PRITHVI_WORKER_URL.rstrip('/')}/analyze",
                        json={
                            "query": query,
                            "model_id": model_id,
                            "dataset_ids": dataset_ids,
                            "analysis_type": analysis_type,
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        # If worker returns normalized structure
                        return NormalizedResult.model_validate(data)
                    else:
                        logger.warning(f"Worker returned status {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Worker execution failed: {e}")
                raise RuntimeError(f"Remote worker unavailable: {e}") from e

            raise RuntimeError(f"Remote worker returned status {resp.status_code}")

        raise RuntimeError("Remote worker mode is disabled; use the live Planetary Computer adapter")
