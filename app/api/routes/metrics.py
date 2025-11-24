"""
Prometheus metrics endpoint.
"""
from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from loguru import logger

from app.utils.metrics import get_metrics_summary

router = APIRouter(tags=["monitoring"])


@router.get("/metrics")
async def get_metrics() -> Response:
    """
    Prometheus metrics endpoint.
    
    Возвращает метрики в формате Prometheus для scraping.
    
    Returns:
        Response с метриками в формате Prometheus
    """
    logger.debug("Metrics endpoint called")
    
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@router.get("/metrics/summary")
async def get_metrics_summary_endpoint() -> dict:
    """
    Получить сводку основных метрик в JSON формате.
    
    Returns:
        Словарь с основными метриками
    """
    logger.debug("Metrics summary endpoint called")
    
    summary = get_metrics_summary()
    
    return {
        "status": "ok",
        "metrics": summary
    }

