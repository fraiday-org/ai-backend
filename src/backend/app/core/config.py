from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "AI Service Backend"
    VERSION: str = "0.0.1"

    MONGODB_URI: str
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_DEFAULT_QUEUE: Optional[str] = "chat_workflow"
    CELERY_EVENTS_QUEUE: Optional[str] = "events"

    SLACK_AI_SERVICE_URL: str
    SLACK_AI_TOKEN: str
    SLACK_AI_SERVICE_WORKFLOW_ID: str
    AI_SERVICE_URL: Optional[str]
    ENCRYPTION_KEY: str
    ADMIN_API_KEY: str

    AWS_BEDROCK_ACCESS_KEY_ID: Optional[str] = None
    AWS_BEDROCK_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_BEDROCK_REGION: Optional[str] = None
    AWS_BEDROCK_RUNTIME: Optional[str] = "bedrock-runtime"

    # Redis configurations
    REDIS_HOST: Optional[str] = None
    REDIS_PORT: Optional[int] = None
    REDIS_DB: Optional[int] = None
    REDIS_PASSWORD: Optional[str] = None
    
    # Feature flags
    ENABLE_CLIENT_CHANNEL_ROUTING: bool = False
    ENABLE_CONFIGURABLE_WORKFLOWS: bool = False

    def get_redis_url(self) -> str:
        """Generate Redis URL from components if CELERY_BROKER_URL is not provided"""
        if self.REDIS_PASSWORD:
            return f"rediss://default:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()
