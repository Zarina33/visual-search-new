"""
Health check endpoints.
"""
from fastapi import APIRouter, status
from typing import Dict, Any
from sqlalchemy import select, func
from loguru import logger

from app.config import settings
from app.db.postgres import get_session, Product
from app.db.qdrant import QdrantManager
from app.utils.metrics import update_active_products, update_qdrant_vectors, set_api_health

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint.
    
    Returns:
        Simple health status
    """
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/health/detailed", status_code=status.HTTP_200_OK)
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check with database connections and metrics update.
    
    Проверяет:
    - PostgreSQL подключение и количество продуктов
    - Qdrant подключение и количество векторов
    - Обновляет Prometheus метрики
    
    Returns:
        Детальный статус здоровья системы
    """
    health_status = {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "components": {},
    }
    
    all_healthy = True
    
    # Check PostgreSQL
    try:
        async with get_session() as session:
            count_result = await session.execute(select(func.count(Product.id)))
            products_count = count_result.scalar()
            
            health_status["components"]["postgresql"] = {
                "status": "healthy",
                "products_count": products_count
            }
            
            # Update metrics
            update_active_products(products_count)
            
            logger.debug(f"PostgreSQL health check: {products_count} products")
            
    except Exception as e:
        health_status["components"]["postgresql"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        all_healthy = False
        logger.error(f"PostgreSQL health check failed: {e}")
    
    # Check Qdrant
    try:
        qdrant_manager = QdrantManager(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            collection_name=settings.qdrant_collection_name
        )
        
        info = await qdrant_manager.get_collection_info()
        vectors_count = info.get("points_count", 0)
        
        health_status["components"]["qdrant"] = {
            "status": "healthy",
            "vectors_count": vectors_count,
            "collection": info.get("name")
        }
        
        # Update metrics
        update_qdrant_vectors(vectors_count)
        
        logger.debug(f"Qdrant health check: {vectors_count} vectors")
        
    except Exception as e:
        health_status["components"]["qdrant"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        all_healthy = False
        logger.error(f"Qdrant health check failed: {e}")
    
    # Set overall health status
    if not all_healthy:
        health_status["status"] = "degraded"
    
    # Update API health metric
    set_api_health(all_healthy)
    
    return health_status

