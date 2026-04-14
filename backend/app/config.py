import logging

from pydantic_settings import BaseSettings

logger = logging.getLogger("scout.config")


class Settings(BaseSettings):
    database_url: str = "postgresql://scout:scout@localhost:5432/scout"
    echo_sql: bool = False
    environment: str = "development"  # "development" or "production"

    # AI provider
    anthropic_api_key: str = ""
    ai_chat_model: str = "claude-sonnet-4-20250514"
    ai_summary_model: str = "claude-sonnet-4-20250514"
    # Default the classification model to the same sonnet version that
    # the chat path uses. A prior default (claude-haiku-4-20250414) was
    # a fabricated model id that returned 404 from Anthropic, which
    # silently forced every classification caller (off-track insight,
    # weekly retro narrative) into the template fallback. Operators who
    # want to optimize cost can set SCOUT_AI_CLASSIFICATION_MODEL to a
    # real haiku variant the account has access to.
    ai_classification_model: str = "claude-sonnet-4-20250514"
    ai_max_tokens: int = 2048
    ai_temperature: float = 0.3
    ai_request_timeout: int = 60
    ai_max_requests_per_minute: int = 30

    # Audio transcription (voice input). When unset, the transcribe
    # endpoint returns 501 and the frontend hides the mic button.
    # Provider options: "groq" (default, cheap Whisper) or "openai".
    transcribe_provider: str = "groq"
    transcribe_api_key: str = ""
    transcribe_model: str = "whisper-large-v3"
    transcribe_max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB

    cors_origins: str = "http://localhost:8081,http://localhost:19006"

    # Auth
    auth_required: bool = False  # When True, bearer token required on all protected routes
    session_ttl_hours: int = 72
    enable_bootstrap: bool = True  # When True, POST /api/auth/bootstrap available (disable in prod)

    # Feature flags
    enable_ai: bool = True
    enable_meal_generation: bool = True
    enable_parent_action_inbox: bool = True

    model_config = {"env_prefix": "SCOUT_"}

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def ai_available(self) -> bool:
        return self.enable_ai and bool(self.anthropic_api_key)

    @property
    def transcribe_available(self) -> bool:
        return bool(self.transcribe_api_key)


settings = Settings()


def validate_startup() -> list[str]:
    """Validate settings at startup. Raises on unsafe production config."""
    warnings: list[str] = []
    if not settings.database_url:
        raise RuntimeError("SCOUT_DATABASE_URL is required")

    # Production fail-closed
    if settings.is_production:
        if not settings.auth_required:
            raise RuntimeError("FATAL: SCOUT_AUTH_REQUIRED must be true in production")
        all_local = all(
            "localhost" in o or "127.0.0.1" in o
            for o in settings.cors_origins.split(",")
        )
        if all_local:
            raise RuntimeError("FATAL: SCOUT_CORS_ORIGINS contains only localhost in production")
        if settings.enable_bootstrap:
            warnings.append("WARNING: Bootstrap enabled in production. Set SCOUT_ENABLE_BOOTSTRAP=false.")

    # Development warnings
    if not settings.auth_required:
        warnings.append("SCOUT_AUTH_REQUIRED=false; legacy member_id fallback enabled (dev only)")
    if not settings.anthropic_api_key:
        warnings.append("SCOUT_ANTHROPIC_API_KEY not set; AI features disabled")
    if not settings.enable_ai:
        warnings.append("AI features disabled via SCOUT_ENABLE_AI=false")
    if not settings.enable_meal_generation:
        warnings.append("Meal generation disabled via SCOUT_ENABLE_MEAL_GENERATION=false")
    return warnings
