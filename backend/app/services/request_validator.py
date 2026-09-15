from app.schemas.analysis_request import AnalysisRequest
from app.models.registry import MODEL_REGISTRY
from app.dataset.registry import DATASET_REGISTRY


class RequestValidator:

    def validate(self, request: AnalysisRequest):

        model_id = request.model_selection.model

        if model_id not in MODEL_REGISTRY:
            raise ValueError(
                f"Unknown model: {model_id}"
            )

        for dataset_id in request.data_requirements.datasets:

            if dataset_id.lower() not in DATASET_REGISTRY:
                raise ValueError(
                    f"Unknown dataset: {dataset_id}"
                )

        return True