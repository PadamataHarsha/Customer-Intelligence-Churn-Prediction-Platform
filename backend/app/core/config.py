"""Application configuration and settings."""

from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with strict validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "sqlite:///./local.db"
    TURSO_DATABASE_URL: str | None = None
    TURSO_AUTH_TOKEN: str | None = None

    JWT_SECRET_KEY: str = "dev-insecure-secret-key-change-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    CORS_ORIGINS: str = "http://localhost:5173"

    ARTIFACT_STORE: Literal["local", "database"] = "local"
    ARTIFACT_LOCAL_DIR: str = "./artifacts"

    RISK_THRESHOLD_MEDIUM: float = 0.30
    RISK_THRESHOLD_HIGH: float = 0.60
    SENTRY_DSN: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list of strings."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @field_validator("RISK_THRESHOLD_MEDIUM", "RISK_THRESHOLD_HIGH")
    @classmethod
    def validate_risk_thresholds(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("Risk thresholds must be between 0.0 and 1.0")
        return v

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Enforce production security requirements."""
        if self.ENVIRONMENT == "production":
            if (
                not self.JWT_SECRET_KEY
                or len(self.JWT_SECRET_KEY) < 32
                or "dev-insecure" in self.JWT_SECRET_KEY
            ):
                raise ValueError(
                    "Production requires a strong JWT_SECRET_KEY of at least 32 characters."
                )

            origins = self.cors_origins_list
            if "*" in origins or not origins:
                raise ValueError("Production CORS_ORIGINS must not be wildcard ('*') or empty.")

        if self.RISK_THRESHOLD_MEDIUM >= self.RISK_THRESHOLD_HIGH:
            raise ValueError("RISK_THRESHOLD_MEDIUM must be strictly less than RISK_THRESHOLD_HIGH")

        return self


settings = Settings()
