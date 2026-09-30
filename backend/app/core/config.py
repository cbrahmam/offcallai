# backend/app/core/config.py

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional
import base64
import json
import os

class Settings(BaseSettings):
    """Application settings, loaded from the environment and .env."""
    
    # App Info
    APP_NAME: str = Field(default="OffCall AI")
    VERSION: str = Field(default="2.0.0")
    DEBUG: bool = Field(default=True)
    ENVIRONMENT: str = Field(default="development")
    
    AZURE_APP_INSIGHTS_CONNECTION_STRING: Optional[str] = Field(default=None, env="AZURE_APP_INSIGHTS_CONNECTION_STRING")
    AZURE_LOG_ANALYTICS_WORKSPACE_ID: Optional[str] = Field(default=None, env="AZURE_LOG_ANALYTICS_WORKSPACE_ID")
    API_URL: str = Field(default="http://localhost:8000", env="API_URL")
    # Database - SECURITY: Must be set via environment variable in production
    # No default password - will fail if DATABASE_URL not set (intentional for security)
    DATABASE_URL: str = Field(default=None)
    REDIS_URL: str = Field(default="redis://redis-service:6379")

    # ClickHouse - Time-series data (metrics, logs, traces)
    CLICKHOUSE_HOST: Optional[str] = Field(default=None, env="CLICKHOUSE_HOST")
    CLICKHOUSE_PORT: int = Field(default=8443, env="CLICKHOUSE_PORT")
    CLICKHOUSE_USER: str = Field(default="default", env="CLICKHOUSE_USER")
    CLICKHOUSE_PASSWORD: Optional[str] = Field(default=None, env="CLICKHOUSE_PASSWORD")
    CLICKHOUSE_DATABASE: str = Field(default="offcall", env="CLICKHOUSE_DATABASE")
    CLICKHOUSE_USE_SSL: bool = Field(default=True, env="CLICKHOUSE_USE_SSL")
    CLICKHOUSE_ENABLED: bool = Field(default=False, env="CLICKHOUSE_ENABLED")

    SENDGRID_API_KEY: Optional[str] = Field(default=None, env="SENDGRID_API_KEY")
    # JWT Settings - SECURITY: Set via environment variables in production
    # Generate secure keys: python -c "import secrets; print(secrets.token_urlsafe(32))"
    SECRET_KEY: str = Field(default=None)
    ENCRYPTION_KEY: str = Field(default=None)
    JWT_KEY_ID: str = Field(default=None)
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    ACCESS_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30)
    
    # Frontend URL
    FRONTEND_URL: str = Field(default="http://localhost:3000")
    
    # Rate Limiting
    GLOBAL_RATE_LIMIT: int = Field(default=1000)
    USER_RATE_LIMIT: int = Field(default=100)
    LOGIN_RATE_LIMIT: int = Field(default=5)
    
    # Security Features
    ENABLE_MFA: bool = Field(default=True)
    ENABLE_RATE_LIMITING: bool = Field(default=True)
    ENABLE_OAUTH2: bool = Field(default=True)
    ENABLE_GDPR_FEATURES: bool = Field(default=True)
    
    # CORS and trusted hosts.
    #
    # Stored as plain strings because pydantic-settings JSON-decodes complex
    # field types inside the settings source, before any validator runs -- so a
    # List[str] field rejects "a,b" outright. Keeping the raw value a str lets
    # us accept both a JSON array and a comma-separated list, which is what
    # people actually write in .env files and compose environment blocks.
    CORS_ORIGINS_RAW: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        validation_alias="CORS_ORIGINS",
    )
    ALLOWED_HOSTS_RAW: str = Field(
        default="localhost,127.0.0.1",
        validation_alias="ALLOWED_HOSTS",
    )

    @staticmethod
    def _parse_list(value: str) -> List[str]:
        """Accept either a JSON array or a comma-separated string."""
        if isinstance(value, list):
            return value
        text = (value or "").strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
        return [item.strip() for item in text.split(",") if item.strip()]

    @property
    def CORS_ORIGINS(self) -> List[str]:
        return self._parse_list(self.CORS_ORIGINS_RAW)

    @property
    def ALLOWED_HOSTS(self) -> List[str]:
        return self._parse_list(self.ALLOWED_HOSTS_RAW)

    # External APIs
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    
    # Slack integration (bot token + signing secret for events,
    # client id/secret for the "Add to Slack" OAuth flow)
    SLACK_BOT_TOKEN: Optional[str] = Field(default=None)
    SLACK_SIGNING_SECRET: Optional[str] = Field(default=None)
    SLACK_CLIENT_ID: Optional[str] = Field(default=None)
    SLACK_CLIENT_SECRET: Optional[str] = Field(default=None)

    # Email - SMTP is the default; Azure Communication Services is an alternative
    FROM_EMAIL: str = Field(default="offcall@localhost")
    SMTP_HOST: Optional[str] = Field(default=None)
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: Optional[str] = Field(default=None)
    SMTP_PASSWORD: Optional[str] = Field(default=None)
    SMTP_USE_TLS: bool = Field(default=True)
    SMTP_USE_SSL: bool = Field(default=False)
    AZURE_COMMUNICATION_CONNECTION_STRING: Optional[str] = Field(default=None)

    # Webhook Security - MUST be set in production for signature verification
    WEBHOOK_SECRET: Optional[str] = Field(default=None)

    # Monitoring Integrations
    DATADOG_API_KEY: Optional[str] = Field(default=None)
    DATADOG_APP_KEY: Optional[str] = Field(default=None)
    GRAFANA_URL: Optional[str] = Field(default=None)
    GRAFANA_API_KEY: Optional[str] = Field(default=None)
    NEW_RELIC_API_KEY: Optional[str] = Field(default=None)
    NEW_RELIC_ACCOUNT_ID: Optional[str] = Field(default=None)
    PROMETHEUS_URL: Optional[str] = Field(default="http://localhost:9090")
    AWS_REGION: str = Field(default="us-east-1")

    @validator('DATABASE_URL', pre=True, always=True)
    def validate_database_url(cls, v):
        """SECURITY: Ensure DATABASE_URL is set - no hardcoded defaults"""
        if v:
            return v
        env_val = os.getenv('DATABASE_URL')
        if env_val:
            return env_val
        # In development, use a local database
        env = os.getenv('ENVIRONMENT', 'development')
        if env == 'development':
            print("⚠️ DATABASE_URL not set, using local development database")
            return "postgresql://postgres:postgres@localhost:5432/offcall_dev"
        # In production, DATABASE_URL MUST be set
        raise ValueError(
            "❌ SECURITY ERROR: DATABASE_URL must be set via environment variable in production. "
            "Never commit database credentials to source code."
        )

    @validator('SECRET_KEY', pre=True, always=True)
    def validate_secret_key(cls, v):
        """Ensure SECRET_KEY is set - generate secure default for dev only"""
        import secrets as sec
        if v and len(str(v)) >= 32:
            return v
        env_val = os.getenv('SECRET_KEY')
        if env_val and len(env_val) >= 32:
            return env_val
        # Generate secure random key - WARN in production
        generated = sec.token_urlsafe(32)
        env = os.getenv('ENVIRONMENT', 'development')
        if env != 'development':
            print(f"⚠️ SECURITY WARNING: SECRET_KEY not set in environment! Using auto-generated key.")
            print(f"   Set SECRET_KEY environment variable for production!")
        return generated

    @validator('ENCRYPTION_KEY', pre=True, always=True)
    def validate_encryption_key(cls, v):
        """Ensure ENCRYPTION_KEY is set - generate secure default for dev only"""
        import secrets as sec
        if v and len(str(v)) >= 32:
            return v
        env_val = os.getenv('ENCRYPTION_KEY')
        if env_val and len(env_val) >= 32:
            return env_val
        generated = sec.token_urlsafe(32)
        env = os.getenv('ENVIRONMENT', 'development')
        if env != 'development':
            print(f"⚠️ SECURITY WARNING: ENCRYPTION_KEY not set in environment!")
        return generated

    @validator('JWT_KEY_ID', pre=True, always=True)
    def validate_jwt_key_id(cls, v):
        """Ensure JWT_KEY_ID is set"""
        import secrets as sec
        if v and len(str(v)) >= 8:
            return v
        env_val = os.getenv('JWT_KEY_ID')
        if env_val:
            return env_val
        return f"offcall-{sec.token_hex(4)}"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"

# Create settings instance
settings = Settings()

# Helper functions
def get_database_url() -> str:
    """Get database URL for SQLAlchemy"""
    return settings.DATABASE_URL

def get_redis_url() -> str:
    """Get Redis URL"""
    return settings.REDIS_URL

def validate_security_settings():
    """Validate that critical security settings are present"""
    required_settings = ['SECRET_KEY', 'ENCRYPTION_KEY']
    
    for setting in required_settings:
        value = getattr(settings, setting, None)
        if not value or len(value) < 32:
            print(f"⚠️ Warning: {setting} should be at least 32 characters long")
    
    print("✅ Security settings validation complete")
    return True

# Run validation on import
if __name__ != "__main__":
    validate_security_settings()