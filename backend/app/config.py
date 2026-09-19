from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GROQ_API_KEY: Optional[str] = ""
    GROQ_MODEL: Optional[str] = "openai/gpt-oss-120b"
    LLM_PROVIDER: str = "groq"
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MAX_TOKENS: int = 2048
    MODEL_MODE: str = "live"
    PRITHVI_WORKER_URL: Optional[str] = ""
    ALLOW_MOCK_FALLBACK: bool = False
    PC_SUBSCRIPTION_KEY: Optional[str] = ""
    IMAGE_OUTPUT_DIR: str = "app/static/generated"
    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = 8000
    CLERK_SECRET_KEY: Optional[str] = ""
    CLERK_PUBLISHABLE_KEY: Optional[str] = ""
    CLERK_JWKS_URL: Optional[str] = ""
    DATABASE_URL: str = "sqlite:///./satquery.db"

    class Config:
        env_file = (".env", "backend/.env")
        extra = "ignore"

settings = Settings()