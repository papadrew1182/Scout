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
    # Soft cap the cost dashboard uses to decide whether to paint a
    # warning. Set to 0 to disable the warning entirely (dashboard
    # still renders the numbers). Operators override via env.
    ai_weekly_soft_cap_usd: float = 5.0

    # Tier 5 F18 — anomaly scan tuning. Suppression window is the
    # number of days to silence a repeat of the same (anomaly_type,
    # signature) for a family. Threshold overrides let operators
    # tune noise levels without a code deploy.
    anomaly_suppression_days: int = 5
    anomaly_min_significance: float = 0.4
    anomaly_max_per_tick: int = 5

    # Tier 5 F18 — scheduler advisory-lock key. Any int fits in a
    # bigint. Picked out of the Scout product namespace so we don't
    # collide with application-level advisory locks.
    scheduler_advisory_lock_key: int = 0x5C0A7_11CC  # "Scout tick"

    # Tier 5 F19 — remote MCP toggle. When false, only the stdio
    # server is available and the /mcp HTTP endpoints 404.
    mcp_remote_enabled: bool = False
    # QA hardening: minimum per-token rate limit so one runaway
    # client can't peg the DB through /mcp/tools/call. Window is a
    # rolling minute. Set to 0 to disable (not recommended).
    mcp_remote_rate_limit_per_minute: int = 60

    # Tier 5 F20 — memory injection budget. At most N active
    # memories are included in any single prompt build, and each is
    # truncated to this many characters. Keeps the prompt budget
    # bounded no matter how many memories a family accumulates.
    memory_inject_max_items: int = 12
    memory_inject_max_chars_per_item: int = 240

    # Supabase Storage — used by the attachments service.
    # Keys read from SCOUT_SUPABASE_URL, SCOUT_SUPABASE_SERVICE_ROLE_KEY,
    # SCOUT_SUPABASE_STORAGE_BUCKET. All default to "" / "attachments" so
    # the server starts cleanly without them; upload endpoints return 501
    # when supabase_url is unset.
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "attachments"

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
