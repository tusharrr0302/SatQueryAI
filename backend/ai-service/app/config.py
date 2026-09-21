"""
app/config.py
─────────────────────────────────────────────────────────────────────────────
Central configuration module.

pydantic-settings reads all values from:
  1. Environment variables (highest priority)
  2. A .env file in the project root

This means you never need to hard-code API keys or URLs.
Simply set them in your .env file and they are automatically available here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    All runtime configuration for the SatQuery AI service.
    Every field maps 1-to-1 to an environment variable.
    """

    # ── LLM Orchestrator ──────────────────────────────────────────────────────
    llm_provider: str = Field(default="groq", description="LLM provider name")
    llm_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Base URL for the OpenAI-compatible API",
    )
    llm_api_key: str = Field(
        default="",
        description="API key for the LLM provider (set in .env, never commit)",
    )
    llm_model: str = Field(
        default="moonshotai/kimi-k2-instruct",
        description="Model name as the provider expects it",
    )
    llm_max_tokens: int = Field(
        default=2048,
        description="Maximum tokens for LLM responses",
    )

    # ── Specialist Models (mock vs real) ──────────────────────────────────────
    # Controls whether specialist tools use local mocks or real remote workers.
    # "mock"  → no GPU required, safe for local development
    # "real"  → sends requests to Kaggle GPU workers via ngrok URLs below
    model_mode: str = Field(
        default="mock",
        description="'mock' for development, 'real' for actual GPU inference",
    )

    # ── Remote Kaggle GPU Worker URLs ─────────────────────────────────────────
    # Each specialist capability runs on its own independent Kaggle notebook.
    # These URLs are the ngrok tunnels that expose those notebooks.
    #
    # Worker 1: EarthDial-4B-MS → analyze_image  (replaces GeoChat)
    earthdial_worker_url: str = Field(
        default="",
        description="EARTHDIAL_WORKER_URL — ngrok URL for the EarthDial-4B-MS Kaggle notebook",
    )

    # Worker 1 (legacy): GeoChat-7B — retained for backward compatibility / tests
    geochat_worker_url: str = Field(
        default="",
        description="GEOCHAT_WORKER_URL — ngrok URL for the GeoChat Kaggle notebook (legacy)",
    )

    # Worker 2: VisTA + Prithvi-EO-2.0-300M → detect_change
    change_detection_worker_url: str = Field(
        default="",
        description="CHANGE_DETECTION_WORKER_URL — ngrok URL for the change detection Kaggle notebook",
    )

    # VisTA Worker: VisTA (Change Detection QA & Visual Grounding) → detect_change
    vista_worker_url: str = Field(
        default="",
        description="VISTA_WORKER_URL — ngrok URL for the VisTA Kaggle worker notebook",
    )

    # Prithvi Worker: Prithvi-EO-2.0-300M (Multitemporal Analysis) → analyze_multitemporal
    prithvi_worker_url: str = Field(
        default="",
        description="PRITHVI_WORKER_URL — ngrok URL for the Prithvi Kaggle worker notebook",
    )

    # Worker 3a: CLOSP → analyze_sar_optical (embedding/cross-modal similarity specialist)
    closp_worker_url: str = Field(
        default="",
        description="CLOSP_WORKER_URL — ngrok URL for the CLOSP Kaggle worker notebook",
    )

    # Worker 3b: TerraFM → analyze_sar_optical (multisensor foundation model specialist)
    terrafm_worker_url: str = Field(
        default="",
        description="TERRAFM_WORKER_URL — ngrok URL for the TerraFM Kaggle worker notebook",
    )

    # Worker 3 (legacy): CLOSP + TerraFM combined — retained for backward compatibility
    sar_optical_worker_url: str = Field(
        default="",
        description="SAR_OPTICAL_WORKER_URL — ngrok URL for the combined SAR+optical Kaggle notebook (legacy)",
    )

    # How long to wait for a remote worker to respond (seconds)
    worker_timeout_seconds: int = Field(
        default=120,
        description="WORKER_TIMEOUT_SECONDS — HTTP timeout for remote GPU worker calls",
    )

    # ── Copernicus Data Space Ecosystem ───────────────────────────────────────
    # Used for Sentinel-1 (SAR) and Sentinel-2 (optical) data.
    # Register at: https://dataspace.copernicus.eu/
    # OData catalogue: https://catalogue.dataspace.copernicus.eu/odata/v1
    # Token endpoint:  https://identity.dataspace.copernicus.eu/auth/realms/CDSE/
    #                  protocol/openid-connect/token
    copernicus_user: str = Field(
        default="",
        description="COPERNICUS_USER — Copernicus Data Space username (email)",
    )
    copernicus_password: str = Field(
        default="",
        description="COPERNICUS_PASSWORD — Copernicus Data Space password",
    )

    # ── USGS M2M API ──────────────────────────────────────────────────────────
    # Used for Landsat 8/9 data.
    # Register at: https://ers.cr.usgs.gov/register
    # API docs:    https://m2m.cr.usgs.gov/api/docs/json/
    usgs_username: str = Field(
        default="",
        description="USGS_USERNAME — USGS EarthExplorer account username",
    )
    usgs_token: str = Field(
        default="",
        description="USGS_TOKEN — USGS M2M application token (from EarthExplorer profile)",
    )

    # ── NASA CMR API ──────────────────────────────────────────────────────────
    # Used for VIIRS / MODIS data.
    # Public API — no authentication required for most collections.
    # API docs: https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html
    nasa_cmr_base_url: str = Field(
        default="https://cmr.earthdata.nasa.gov/search",
        description="NASA_CMR_BASE_URL — Common Metadata Repository search endpoint",
    )

    # ── FastAPI Service ────────────────────────────────────────────────────────
    service_host: str = Field(default="0.0.0.0")
    service_port: int = Field(default=8000)

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="DEBUG")

    # pydantic-settings config:
    # env_file tells it to look for a .env file relative to where the app runs
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore any extra env vars we didn't define
    )


# Create a single global settings instance.
# Import this anywhere in the codebase:
#   from app.config import settings
settings = Settings()
