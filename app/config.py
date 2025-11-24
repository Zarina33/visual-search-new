"""
Configuration module using pydantic-settings for environment variable validation.
"""
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application Settings
    app_name: str = Field(default="visual-search-project", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # API Settings
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=4, description="Number of API workers")
    
    # PostgreSQL Settings
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_db: str = Field(default="visual_search", description="PostgreSQL database name")
    postgres_user: str = Field(default="postgres", description="PostgreSQL user")
    postgres_password: str = Field(default="postgres", description="PostgreSQL password")
    
    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL (sync)."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def async_database_url(self) -> str:
        """Construct async PostgreSQL connection URL (asyncpg)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    # Redis Settings
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    
    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    # Qdrant Settings
    qdrant_host: str = Field(default="localhost", description="Qdrant host")
    qdrant_port: int = Field(default=6333, description="Qdrant HTTP port")
    qdrant_grpc_port: int = Field(default=6334, description="Qdrant gRPC port")
    qdrant_collection_name: str = Field(
        default="product_embeddings", 
        description="Qdrant collection name"
    )
    qdrant_vector_size: int = Field(default=512, description="Vector embedding size")
    
    # CLIP Model Settings
    clip_model_name: str = Field(
        default="openai/clip-vit-base-patch32",
        description="CLIP model name from HuggingFace"
    )
    clip_device: str = Field(default="cpu", description="Device for CLIP model (cpu/cuda)")
    clip_batch_size: int = Field(default=32, description="Batch size for CLIP processing")
    
    @field_validator("clip_device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        """Validate device setting."""
        if v not in ["cpu", "cuda"]:
            raise ValueError("clip_device must be 'cpu' or 'cuda'")
        return v
    
    # Celery Settings
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        description="Celery broker URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2",
        description="Celery result backend URL"
    )
    celery_task_track_started: bool = Field(
        default=True,
        description="Track when tasks are started"
    )
    celery_task_time_limit: int = Field(
        default=3600,
        description="Task time limit in seconds"
    )
    
    # Image Processing Settings
    max_image_size: int = Field(default=1024, description="Maximum image dimension")
    allowed_image_formats: str = Field(
        default="jpg,jpeg,png,webp",
        description="Allowed image formats (comma-separated)"
    )
    image_quality: int = Field(default=85, description="Image compression quality")
    
    @property
    def allowed_formats_list(self) -> List[str]:
        """Get list of allowed image formats."""
        return [fmt.strip().lower() for fmt in self.allowed_image_formats.split(",")]
    
    @field_validator("image_quality")
    @classmethod
    def validate_image_quality(cls, v: int) -> int:
        """Validate image quality is between 1 and 100."""
        if not 1 <= v <= 100:
            raise ValueError("image_quality must be between 1 and 100")
        return v
    
    # Search Settings
    default_search_limit: int = Field(default=20, description="Default search results limit")
    max_search_limit: int = Field(default=100, description="Maximum search results limit")
    similarity_threshold: float = Field(
        default=0.5,
        description="Minimum similarity threshold for search results"
    )
    
    @field_validator("similarity_threshold")
    @classmethod
    def validate_similarity_threshold(cls, v: float) -> float:
        """Validate similarity threshold is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
        return v
    
    # Retry Settings
    max_retries: int = Field(default=3, description="Maximum number of retries")
    retry_delay: int = Field(default=1, description="Initial retry delay in seconds")
    retry_backoff: int = Field(default=2, description="Retry backoff multiplier")
    
    # BakaiMarket CDN Settings
    bakai_cdn_api_url: str = Field(
        default="https://api-cdn.bakai.store",
        description="BakaiMarket CDN API URL"
    )
    bakai_cdn_access_key: str = Field(default="", description="BakaiMarket CDN access key")
    bakai_cdn_secret_key: str = Field(default="", description="BakaiMarket CDN secret key")
    
    # Webhook Settings
    webhook_secret: str = Field(
        default="",
        description="Secret key for webhook signature validation (HMAC-SHA256)"
    )


# Global settings instance
settings = Settings()

