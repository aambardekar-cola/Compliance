"""Application configuration loaded from environment variables."""
import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:5173"

    # Descope
    descope_project_id: str = ""
    descope_management_key: str = ""

    # Database
    db_secret_arn: str = ""
    db_proxy_endpoint: str = ""
    database_url: str = "sqlite+aiosqlite:///local_test.db"

    # AWS
    aws_region: str = "us-east-2"

    # Amazon Bedrock
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"

    # S3
    documents_bucket: str = ""
    reports_bucket: str = ""

    # SES
    ses_from_email: str = "compliance@collabrios.com"
    ses_reply_to_email: str = "support@collabrios.com"

    # SQS
    analysis_queue_url: str = ""
    communication_queue_url: str = ""

    # GitLab (admin-configured)
    gitlab_url: str = "https://gitlab.com"
    gitlab_token: str = ""
    gitlab_project_ids: str = ""

    # Jira Cloud (admin-configured)
    jira_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def gitlab_project_id_list(self) -> list[int]:
        if not self.gitlab_project_ids:
            return []
        return [int(pid.strip()) for pid in self.gitlab_project_ids.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
