import warnings
from typing import Any, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    GROQ_API_KEY: Optional[str] = ""
    GROQ_MODEL: Optional[str] = "openai/gpt-oss-120b"
    LLM_PROVIDER: str = "groq"
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MAX_TOKENS: int = 2048
    LLM_ENABLED: bool = True

    # EO Execution Modes: "live" | "worker" | "mock"
    EO_EXECUTION_MODE: str = "live"
    MODEL_MODE: Optional[str] = None  # Deprecated in favor of EO_EXECUTION_MODE

    PRITHVI_WORKER_URL: Optional[str] = ""
    EARTHDIAL_WORKER_URL: Optional[str] = ""
    GEOCHAT_WORKER_URL: Optional[str] = ""
    TERRAFM_WORKER_URL: Optional[str] = ""
    CLOSP_WORKER_URL: Optional[str] = ""
    SAR_OPTICAL_WORKER_URL: Optional[str] = ""
    VISTA_WORKER_URL: Optional[str] = ""
    CHANGE_DETECTION_WORKER_URL: Optional[str] = ""
    AI_SERVICE_URL: Optional[str] = "http://localhost:8000"
    WORKER_TIMEOUT_SECONDS: int = 120

    ALLOW_MOCK_FALLBACK: bool = False
    PC_SUBSCRIPTION_KEY: Optional[str] = ""
    COPERNICUS_CLIENT_ID: Optional[str] = ""
    COPERNICUS_CLIENT_SECRET: Optional[str] = ""
    COPERNICUS_SH_BASE_URL: str = "https://sh.dataspace.copernicus.eu"
    COPERNICUS_TOKEN_URL: str = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    IMAGE_OUTPUT_DIR: str = "app/static/generated"
    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = 8000
    CLERK_SECRET_KEY: Optional[str] = ""
    CLERK_PUBLISHABLE_KEY: Optional[str] = ""
    CLERK_JWKS_URL: Optional[str] = ""
    DATABASE_URL: str = "sqlite:///./satquery.db"

    @model_validator(mode="before")
    @classmethod
    def handle_deprecated_model_mode(cls, data: Any) -> Any:
        if isinstance(data, dict):
            model_mode = data.get("MODEL_MODE")
            eo_mode = data.get("EO_EXECUTION_MODE")
            if model_mode is not None:
                warnings.warn(
                    "MODEL_MODE is deprecated. Use EO_EXECUTION_MODE instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                if not eo_mode:
                    data["EO_EXECUTION_MODE"] = model_mode
            if not data.get("MODEL_MODE"):
                data["MODEL_MODE"] = data.get("EO_EXECUTION_MODE", "live")
        return data

    class Config:
        env_file = (".env", "backend/.env", "backend/ai-service/.env", "ai-service/.env")
        extra = "ignore"

settings = Settings()