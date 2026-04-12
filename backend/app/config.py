from pydantic_settings import BaseSettings


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

    model_config = {"env_prefix": "SCOUT_"}


settings = Settings()
