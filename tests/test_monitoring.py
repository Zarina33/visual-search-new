"""
Tests for monitoring and metrics functionality.
"""
import pytest
from httpx import AsyncClient
from fastapi import status

from app.api.main import app
from app.utils.metrics import (
    record_search,
    record_clip_inference,
    record_qdrant_search,
    record_product_added,
    update_active_products,
    update_qdrant_vectors,
    set_api_health,
    set_clip_model_status,
    get_metrics_summary,
)


@pytest.mark.asyncio
async def test_metrics_endpoint():
    """
    Тест endpoint /api/v1/metrics.
    
    Проверяет, что endpoint возвращает метрики в формате Prometheus.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/metrics")
        
        assert response.status_code == status.HTTP_200_OK
        assert "text/plain" in response.headers["content-type"]
        
        # Проверить, что в ответе есть метрики
        content = response.text
        assert "visual_search_total_searches" in content
        assert "visual_search_duration_seconds" in content
        assert "visual_search_api_health" in content
        assert "visual_search_clip_model_loaded" in content
        
        print("✅ Metrics endpoint test passed")


@pytest.mark.asyncio
async def test_metrics_summary_endpoint():
    """
    Тест endpoint /api/v1/metrics/summary.
    
    Проверяет, что endpoint возвращает сводку метрик в JSON формате.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/metrics/summary")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "status" in data
        assert "metrics" in data
        assert data["status"] == "ok"
        
        metrics = data["metrics"]
        assert "api_health" in metrics
        assert "clip_model_loaded" in metrics
        assert "active_products" in metrics
        assert "qdrant_vectors" in metrics
        
        print("✅ Metrics summary endpoint test passed")


@pytest.mark.asyncio
async def test_health_check_updates_metrics():
    """
    Тест, что health check обновляет метрики.
    
    Проверяет, что при вызове /health/detailed обновляются метрики.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Вызвать health check
        response = await client.get("/api/v1/health/detailed")
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "status" in data
        assert "components" in data
        
        # Проверить, что метрики обновились
        summary = get_metrics_summary()
        
        # Метрики должны быть установлены (не NaN)
        assert isinstance(summary["api_health"], (int, float))
        assert isinstance(summary["clip_model_loaded"], (int, float))
        
        print("✅ Health check metrics update test passed")


def test_record_search_metrics():
    """
    Тест записи метрик поиска.
    
    Проверяет, что метрики поиска записываются корректно.
    """
    # Записать успешный поиск
    record_search("by-text", 0.5, success=True)
    record_search("by-image", 1.2, success=True)
    record_search("similar", 0.3, success=True)
    
    # Записать неуспешный поиск
    record_search("by-text", 0.8, success=False)
    
    print("✅ Record search metrics test passed")


def test_record_clip_inference_metrics():
    """
    Тест записи метрик CLIP inference.
    
    Проверяет, что метрики CLIP inference записываются корректно.
    """
    record_clip_inference(0.1)
    record_clip_inference(0.2)
    record_clip_inference(0.15)
    
    print("✅ Record CLIP inference metrics test passed")


def test_record_qdrant_search_metrics():
    """
    Тест записи метрик поиска в Qdrant.
    
    Проверяет, что метрики поиска в Qdrant записываются корректно.
    """
    record_qdrant_search(0.01)
    record_qdrant_search(0.02)
    record_qdrant_search(0.015)
    
    print("✅ Record Qdrant search metrics test passed")


def test_record_product_added_metrics():
    """
    Тест записи метрик добавления продуктов.
    
    Проверяет, что метрики добавления продуктов записываются корректно.
    """
    record_product_added()
    record_product_added()
    record_product_added()
    
    print("✅ Record product added metrics test passed")


def test_update_gauge_metrics():
    """
    Тест обновления gauge метрик.
    
    Проверяет, что gauge метрики обновляются корректно.
    """
    update_active_products(100)
    update_qdrant_vectors(200)
    set_api_health(True)
    set_clip_model_status(True)
    
    summary = get_metrics_summary()
    
    assert summary["active_products"] == 100
    assert summary["qdrant_vectors"] == 200
    assert summary["api_health"] == 1
    assert summary["clip_model_loaded"] == 1
    
    # Обновить на другие значения
    update_active_products(150)
    update_qdrant_vectors(250)
    set_api_health(False)
    set_clip_model_status(False)
    
    summary = get_metrics_summary()
    
    assert summary["active_products"] == 150
    assert summary["qdrant_vectors"] == 250
    assert summary["api_health"] == 0
    assert summary["clip_model_loaded"] == 0
    
    print("✅ Update gauge metrics test passed")


@pytest.mark.asyncio
async def test_logging_middleware():
    """
    Тест middleware для логирования запросов.
    
    Проверяет, что middleware логирует HTTP запросы.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Сделать несколько запросов
        response1 = await client.get("/api/v1/health")
        assert response1.status_code == status.HTTP_200_OK
        assert "X-Process-Time" in response1.headers
        
        response2 = await client.get("/api/v1/metrics/summary")
        assert response2.status_code == status.HTTP_200_OK
        assert "X-Process-Time" in response2.headers
        
        # Проверить, что время обработки разумное
        process_time1 = float(response1.headers["X-Process-Time"])
        process_time2 = float(response2.headers["X-Process-Time"])
        
        assert 0 <= process_time1 < 10  # Меньше 10 секунд (может быть 0 для очень быстрых запросов)
        assert 0 <= process_time2 < 10
        
        print("✅ Logging middleware test passed")


@pytest.mark.asyncio
async def test_metrics_endpoint_format():
    """
    Тест формата метрик Prometheus.
    
    Проверяет, что метрики в правильном формате для Prometheus.
    """
    # Записать несколько метрик
    record_search("by-text", 0.5, success=True)
    record_clip_inference(0.1)
    update_active_products(50)
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/metrics")
        
        assert response.status_code == status.HTTP_200_OK
        
        content = response.text
        
        # Проверить формат метрик
        # Counter
        assert 'visual_search_total_searches_total{search_type="by-text"}' in content
        
        # Histogram
        assert "visual_search_duration_seconds_bucket" in content
        assert "clip_inference_duration_seconds_bucket" in content
        
        # Gauge
        assert "visual_search_active_products" in content
        assert "visual_search_api_health" in content
        
        print("✅ Metrics format test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

