"""Application settings and configuration."""
import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Timezone
    tz: str = Field(default="America/Mexico_City", env="TZ")
    
    # Database URLs
    db_url: str = Field(
        default="postgresql+asyncpg://newsbot:newsbot@localhost:5432/newsbot",
        env="DB_URL"
    )
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    opensearch_url: str = Field(default="http://localhost:9200", env="OPENSEARCH_URL")
    
    # WordPress integration
    wp_base_url: str = Field(default="https://windworldwire.com", env="WP_BASE_URL")
    wp_user: str = Field(default="api_user", env="WP_USER")
    wp_app_password: str = Field(default="", env="WP_APP_PASSWORD")
    
    # Facebook integration
    fb_page_id: str = Field(default="", env="FB_PAGE_ID")
    fb_page_token: str = Field(default="", env="FB_PAGE_TOKEN")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Service configuration
    service_host: str = Field(default="0.0.0.0", env="SERVICE_HOST")
    service_port: Optional[int] = Field(default=None, env="SERVICE_PORT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Additional settings for backward compatibility
    app_name: str = "NewsBot"
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Permite campos extra del .env que no están en el modelo


@lru_cache()
def get_settings() -> Settings:
    """Get settings singleton."""
    return Settings()


# Global settings instance for backward compatibility
settings = get_settings()