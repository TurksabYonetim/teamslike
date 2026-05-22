from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = Field(default="TeamsLike API")
    app_env: str = Field(default="development")
    app_debug: bool = Field(default=True)
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8800)

    database_url: str
    database_echo: bool = False

    redis_url: str
    redis_key_prefix: str = "teamslike"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 14

    jitsi_public_url: str
    jitsi_jwt_app_id: str
    jitsi_jwt_app_secret: str
    jitsi_jwt_algorithm: str = "HS256"
    jitsi_jwt_token_ttl_minutes: int = 120
    jitsi_domain: str = "meet.jitsi"

    chatwoot_base_url: str
    chatwoot_user_api_token: str
    chatwoot_account_id: int = 1

    cors_allowed_origins: str = Field(default="")

    log_format: str = Field(default="json")
    log_level: str = Field(default="INFO")

    sentry_dsn: str = Field(default="")
    sentry_environment: str = Field(default="production")
    sentry_traces_sample_rate: float = Field(default=0.0)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
