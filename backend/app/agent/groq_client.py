from groq import Groq
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GROQ_API_KEY: str
    GROQ_MODEL: str

    class Config:
        env_file = ".env"


settings = Settings()


class GroqClient:

    def __init__(self):
        self.client = Groq(
            api_key=settings.GROQ_API_KEY
        )

    def create_analysis_request(
        self,
        prompt: str,
        schema: dict,
        models: dict,
        datasets: dict
    ):
        system_prompt = f"""
You are SatQuery AI's remote sensing query analysis engine.

Convert the user's request into the provided AnalysisRequest schema.

You MUST select models and datasets ONLY from these registries.

AVAILABLE MODELS:
{models}

AVAILABLE DATASETS:
{datasets}

Never invent a model ID or dataset ID.

If the task requires temporal/multispectral analysis, prefer
prithvi-eo-2.0.

If the task requires single-image VQA, captioning, or grounding,
prefer geochat-7b.

If the task requires optical + SAR analysis, consider terrafm
or closp.

Return only the structured AnalysisRequest.
"""

        response = self.client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": schema
            },
            temperature=0
        )

        return response.choices[0].message.content

def request_tool_call(self, analysis_request: dict, tools: list):

    response = self.client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": """
You are the execution planner for SatQuery AI.

You are given a validated AnalysisRequest.

Use the execute_remote_sensing_analysis tool
to execute the requested remote sensing analysis.

Do not invent models or datasets.
Use exactly the model and datasets provided
in the AnalysisRequest.
"""
            },
            {
                "role": "user",
                "content": str(analysis_request)
            }
        ],
        tools=tools,
        tool_choice="required",
        temperature=0
    )

    return response.choices[0].message