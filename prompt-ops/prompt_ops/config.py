from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # API
    api_key: str = ""                          # PROMPT_OPS_API_KEY or OPENROUTER_API_KEY
    base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "meta-llama/llama-3.3-8b-instruct:free"
    judge_model: str = "google/gemini-2.0-flash-001"

    # Database
    db_url: str = f"sqlite:///{Path.home()}/.prompt-ops/data.db"

    # Evaluation
    auto_evaluate: bool = True
    evaluation_sample_rate: float = 1.0       # 0.1 = evaluate 10% of calls

    # Optimization
    auto_promote_threshold: float = 0.85
    auto_retire_threshold: float = 0.40

    # Temperature
    temp_min: float = 0.0
    temp_max: float = 1.5
    temp_step: float = 0.3
    temp_trials: int = 3

    # Cost routing
    cost_routing_enabled: bool = False
    quality_threshold: float = 0.7

    # Alerting
    latency_threshold_ms: float = 2000.0
    error_rate_threshold: float = 0.05
    cost_threshold_usd: float = 10.0
    anomaly_z_score: float = 2.0

    model_config = SettingsConfigDict(
        env_prefix="PROMPT_OPS_",
        env_file=".env",
        extra="ignore"
    )

settings = Settings()

MODEL_TIERS = {
    "free":    ["meta-llama/llama-3.3-8b-instruct:free", "google/gemma-3-4b-it:free"],
    "cheap":   ["google/gemini-2.0-flash-001", "openai/gpt-4o-mini"],
    "mid":     ["anthropic/claude-3.5-haiku", "google/gemini-2.0-flash-thinking-exp"],
    "premium": ["openai/gpt-4o", "anthropic/claude-sonnet-4", "google/gemini-2.5-pro-preview"],
}
