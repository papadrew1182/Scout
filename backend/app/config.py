import logging

from pydantic_settings import BaseSettings

logger = logging.getLogger("scout.config")


class Settings(BaseSettings):
    database_url: str = "postgresql://scout:scout@localhost:5432/scout"
    echo_sql: bool = False

    # AI provider
    anthropic_api_key: str = ""
    ai_chat_model: str = "claude-sonnet-4-20250514"
    ai_summary_model: str = "claude-sonnet-4-20250514"
    ai_classification_model: str = "claude-haiku-4-20250414"
    ai_max_tokens: int = 2048
    ai_temperature: float = 0.3
    ai_request_timeout: int = 60
    ai_max_requests_per_minute: int = 30

    cors_origins: str = "http://localhost:8081,http://localhost:19006"

    # Feature flags
    enable_ai: bool = True
    enable_meal_generation: bool = True
    enable_parent_action_inbox: bool = True

    model_config = {"env_prefix": "SCOUT_"}

    @property
    def ai_available(self) -> bool:
        return self.enable_ai and bool(self.anthropic_api_key)


settings = Settings()


def validate_startup() -> list[str]:
    """Validate critical settings at startup. Returns list of warnings."""
    warnings: list[str] = []
    if not settings.database_url:
        raise RuntimeError("SCOUT_DATABASE_URL is required")
    if not settings.anthropic_api_key:
        warnings.append("SCOUT_ANTHROPIC_API_KEY not set; AI features disabled")
    if not settings.enable_ai:
        warnings.append("AI features disabled via SCOUT_ENABLE_AI=false")
    if not settings.enable_meal_generation:
        warnings.append("Meal generation disabled via SCOUT_ENABLE_MEAL_GENERATION=false")
    return warnings
