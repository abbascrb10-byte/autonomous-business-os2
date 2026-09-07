import os
from typing import Optional
from pydantic import model_validator
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
    CORS_ALLOWED_ORIGINS: str = ""
    SECRET_KEY: str = "dev_secret_key_change_in_production"
    ADMIN_API_KEY: Optional[str] = None

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

    # AI Providers (Default: Ollama local open-weight model)
    AI_PROVIDER: str = "ollama"  # ollama | gemini | openai | anthropic | mock
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # Optional cloud LLM providers
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Search Integration (Tavily Free Tier)
    TAVILY_API_KEY: Optional[str] = None

    # Demand Sources
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None
    TWITTER_BEARER_TOKEN: Optional[str] = None

    # Primary Real Commerce Integrations
    # eBay Browse API & Partner Network
    EBAY_CLIENT_ID: Optional[str] = None
    EBAY_CLIENT_SECRET: Optional[str] = None
    EBAY_CAMPAIGN_ID: Optional[str] = None
    EBAY_API_BASE_URL: str = "https://api.ebay.com"

    # Etsy Open API v3
    ETSY_API_KEY: Optional[str] = None
    ETSY_SHOP_ID: Optional[str] = None

    # Optional Commerce Integration: Amazon
    AMAZON_ASSOCIATE_TAG: Optional[str] = None
    AMAZON_ACCESS_KEY: Optional[str] = None
    AMAZON_SECRET_KEY: Optional[str] = None
    AMAZON_REGION: str = "us-east-1"

    # Outreach
    OUTREACH_PROVIDER: str = "local_approval"  # local_approval | mock | sendgrid | twilio
    OUTREACH_API_KEY: Optional[str] = None

    # Tracking
    BASE_TRACKING_URL: str = "http://localhost:8000/api/v1/tracking/click"

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.APP_ENV == "production":
            if not self.ADMIN_API_KEY:
                raise ValueError("ADMIN_API_KEY must be configured in production")
            if self.SECRET_KEY == "dev_secret_key_change_in_production":
                raise ValueError("SECRET_KEY must be changed in production")
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
        return self

settings = Settings()
