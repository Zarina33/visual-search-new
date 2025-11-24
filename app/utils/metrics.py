"""
Prometheus metrics for visual search system.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from loguru import logger
from typing import Optional

# Counters
total_searches = Counter(
    'visual_search_total_searches',
    'Total number of search requests',
    ['search_type']  # by-image, by-text, similar
)

search_errors = Counter(
    'visual_search_errors_total',
    'Total number of search errors',
    ['error_type']
)

products_added = Counter(
    'visual_search_products_added_total',
    'Total number of products added'
)

# Histograms
search_duration = Histogram(
    'visual_search_duration_seconds',
    'Search request duration in seconds',
    ['search_type'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

clip_inference_duration = Histogram(
    'clip_inference_duration_seconds',
    'CLIP model inference duration',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)

qdrant_search_duration = Histogram(
    'qdrant_search_duration_seconds',
    'Qdrant vector search duration',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5]
)

# Gauges
active_products = Gauge(
    'visual_search_active_products',
    'Number of active products in database'
)

qdrant_vectors = Gauge(
    'visual_search_qdrant_vectors',
    'Number of vectors in Qdrant collection'
)

api_health = Gauge(
    'visual_search_api_health',
    'API health status (1=healthy, 0=unhealthy)'
)

clip_model_loaded = Gauge(
    'visual_search_clip_model_loaded',
    'CLIP model loaded status (1=loaded, 0=not loaded)'
)


def record_search(search_type: str, duration: float, success: bool = True) -> None:
    """
    Записать метрики поиска.
    
    Args:
        search_type: Тип поиска (by-image, by-text, similar)
        duration: Длительность в секундах
        success: Успешность запроса
    """
    total_searches.labels(search_type=search_type).inc()
    search_duration.labels(search_type=search_type).observe(duration)
    
    if not success:
        search_errors.labels(error_type=search_type).inc()
        logger.warning(f"Search failed: type={search_type}, duration={duration:.3f}s")
    else:
        logger.debug(f"Search recorded: type={search_type}, duration={duration:.3f}s")


def record_clip_inference(duration: float) -> None:
    """
    Записать время CLIP inference.
    
    Args:
        duration: Длительность в секундах
    """
    clip_inference_duration.observe(duration)
    logger.debug(f"CLIP inference: {duration:.3f}s")


def record_qdrant_search(duration: float) -> None:
    """
    Записать время поиска в Qdrant.
    
    Args:
        duration: Длительность в секундах
    """
    qdrant_search_duration.observe(duration)
    logger.debug(f"Qdrant search: {duration:.3f}s")


def record_product_added() -> None:
    """Записать добавление нового продукта."""
    products_added.inc()
    logger.debug("Product added metric incremented")


def update_active_products(count: int) -> None:
    """
    Обновить количество активных продуктов.
    
    Args:
        count: Количество продуктов
    """
    active_products.set(count)
    logger.debug(f"Active products updated: {count}")


def update_qdrant_vectors(count: int) -> None:
    """
    Обновить количество векторов в Qdrant.
    
    Args:
        count: Количество векторов
    """
    qdrant_vectors.set(count)
    logger.debug(f"Qdrant vectors updated: {count}")


def set_api_health(healthy: bool) -> None:
    """
    Установить статус здоровья API.
    
    Args:
        healthy: True если API здоров
    """
    api_health.set(1 if healthy else 0)
    logger.debug(f"API health set to: {'healthy' if healthy else 'unhealthy'}")


def set_clip_model_status(loaded: bool) -> None:
    """
    Установить статус загрузки CLIP модели.
    
    Args:
        loaded: True если модель загружена
    """
    clip_model_loaded.set(1 if loaded else 0)
    logger.debug(f"CLIP model status: {'loaded' if loaded else 'not loaded'}")


async def update_system_metrics(
    postgres_session=None,
    qdrant_manager=None
) -> None:
    """
    Обновить системные метрики (products, vectors).
    
    Вызывается периодически для обновления gauge метрик.
    
    Args:
        postgres_session: Сессия PostgreSQL
        qdrant_manager: Менеджер Qdrant
    """
    try:
        # Обновить количество продуктов
        if postgres_session:
            from sqlalchemy import select, func
            from app.db.postgres import Product
            
            count_result = await postgres_session.execute(select(func.count(Product.id)))
            products_count = count_result.scalar()
            update_active_products(products_count)
        
        # Обновить количество векторов
        if qdrant_manager:
            info = await qdrant_manager.get_collection_info()
            vectors_count = info.get("points_count", 0)
            update_qdrant_vectors(vectors_count)
        
        logger.debug("System metrics updated successfully")
        
    except Exception as e:
        logger.error(f"Failed to update system metrics: {e}")


def get_metrics_summary() -> dict:
    """
    Получить сводку текущих метрик.
    
    Returns:
        Словарь с основными метриками
    """
    return {
        "api_health": api_health._value.get(),
        "clip_model_loaded": clip_model_loaded._value.get(),
        "active_products": active_products._value.get(),
        "qdrant_vectors": qdrant_vectors._value.get(),
    }

