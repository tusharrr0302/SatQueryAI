import json

from app.agent.groq_client import GroqClient
from app.schemas.analysis_request import AnalysisRequest

class ModelDatasetSelector:
    def __init__(self):
        self.groq_client = GroqClient()

    def select(self, query: str) -> dict:

        prompt = f"""
You are the dataset and EO model selector for SatQuery AI.

Your ONLY job is to select:
1. dataset(s)
2. EO model
3. analysis type

You MUST select only from the provided registries.

DATASETS:
{json.dumps(DATASET_REGISTRY, indent=2)}

MODELS:
{json.dumps(MODEL_REGISTRY, indent=2)}

USER QUERY:
{query}

Return ONLY valid JSON in this format:

{{
    "dataset_ids": [],
    "model_id": "",
    "analysis_type": "",
    "reason": ""
}}
"""

        response = self.groq.create_analysis_request(prompt, schema=AnalysisRequest.schema())

        return json.loads(response)