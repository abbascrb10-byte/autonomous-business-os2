import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "GPIE Professional v1"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "dev_secret_key_change_in_production"

    # Database
    POSTGRES_USER: str = "gpie"
    POSTGRES_PASSWORD: str = "gpie_password"
    POSTGRES_DB: str = "gpie_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://gpie:gpie_password@localhost:5432/gpie_db"
    SYNC_DATABASE_URL: str = "postgresql://gpie:gpie_password@localhost:5432/gpie_db"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI Provider
    AI_PROVIDER: str = "openai"  # openai | anthropic | gemini | mock
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # Merchant Credentials
    AMAZON_ASSOCIATE_TAG: Optional[str] = None
    AMAZON_ACCESS_KEY: Optional[str] = None
    AMAZON_SECRET_KEY: Optional[str] = None
    AMAZON_REGION: str = "us-east-1"

    EBAY_CLIENT_ID: Optional[str] = None
    EBAY_CLIENT_SECRET: Optional[str] = None
    EBAY_CAMPAIGN_ID: Optional[str] = None

    # Outreach
    OUTREACH_PROVIDER: str = "local_approval"  # local_approval | mock | sendgrid | twilio
    OUTREACH_API_KEY: Optional[str] = None

    # Tracking
    BASE_TRACKING_URL: str = "http://localhost:8000/api/v1/tracking/click"

settings = Settings()
