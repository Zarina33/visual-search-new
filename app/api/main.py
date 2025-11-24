"""
Main FastAPI application.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.api.routes import search, health, products, metrics
from app.models.clip_model import CLIPEmbedder
from app.db.qdrant import QdrantManager
from app.middleware.logging import LoggingMiddleware
from app.utils.logger import setup_logging
from app.utils.metrics import set_clip_model_status, set_api_health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    
    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown").
    """
    # Startup
    logger.info("=" * 60)
    logger.info("Starting Visual Search API...")
    logger.info("=" * 60)
    
    try:
        # Инициализация CLIP embedder
        logger.info("Initializing CLIP embedder...")
        search.clip_embedder = CLIPEmbedder(device="auto")
        logger.success(f"✅ CLIP embedder initialized (device={search.clip_embedder.device})")
        
        # Обновить метрику загрузки модели
        set_clip_model_status(loaded=True)
        
        # Инициализация Qdrant manager
        logger.info("Initializing Qdrant manager...")
        search.qdrant_manager = QdrantManager(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            collection_name=settings.qdrant_collection_name
        )
        
        # Проверка коллекции
        if await search.qdrant_manager.collection_exists():
            info = await search.qdrant_manager.get_collection_info()
            logger.success(f"✅ Qdrant connected: {info['points_count']} vectors in collection")
        else:
            logger.warning("⚠️  Qdrant collection does not exist. Please run load_demo_products.py first.")
        
        # Установить API как здоровый
        set_api_health(healthy=True)
        
        logger.info("=" * 60)
        logger.success("✅ Startup complete! API is ready.")
        logger.info(f"📊 Metrics available at: http://{settings.api_host}:{settings.api_port}/api/v1/metrics")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        set_api_health(healthy=False)
        set_clip_model_status(loaded=False)
        raise
    
    # Yield control to the application
    yield
    
    # Shutdown
    logger.info("Shutting down Visual Search API...")
    
    # Обновить метрики
    set_api_health(healthy=False)
    set_clip_model_status(loaded=False)
    
    # Cleanup if needed
    if search.qdrant_manager:
        search.qdrant_manager.close()
    
    logger.info("✅ Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    # Настроить логирование перед созданием приложения
    setup_logging()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        description="Visual Search API using CLIP embeddings",
        lifespan=lifespan,
    )
    
    # Add logging middleware (должен быть первым для логирования всех запросов)
    app.add_middleware(LoggingMiddleware)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(search.router, tags=["search"])
    app.include_router(products.router, prefix="/api/v1", tags=["products"])
    app.include_router(metrics.router, prefix="/api/v1", tags=["monitoring"])
    
    # Import and include webhooks router
    from app.api.routes import webhooks
    app.include_router(webhooks.router, tags=["webhooks"])
    
    return app


app = create_app()

