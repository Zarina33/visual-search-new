#!/usr/bin/env python3
"""
Скрипт для тестирования мониторинга и метрик.

Выполняет несколько запросов к API и проверяет метрики.
"""
import asyncio
import httpx
import time
from pathlib import Path
from loguru import logger


API_BASE_URL = "http://localhost:8000"


async def test_metrics_endpoint():
    """Тест metrics endpoint."""
    print("\n" + "=" * 60)
    print("📊 Тестирование Metrics Endpoint")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/api/v1/metrics")
            
            if response.status_code == 200:
                print("✅ Metrics endpoint доступен")
                print(f"   Content-Type: {response.headers.get('content-type')}")
                
                # Проверить наличие ключевых метрик
                content = response.text
                metrics_found = []
                
                if "visual_search_total_searches" in content:
                    metrics_found.append("total_searches")
                if "visual_search_duration_seconds" in content:
                    metrics_found.append("duration")
                if "clip_inference_duration_seconds" in content:
                    metrics_found.append("clip_inference")
                if "visual_search_api_health" in content:
                    metrics_found.append("api_health")
                if "visual_search_clip_model_loaded" in content:
                    metrics_found.append("clip_model")
                
                print(f"   Найдено метрик: {', '.join(metrics_found)}")
                
                return True
            else:
                print(f"❌ Ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False


async def test_metrics_summary():
    """Тест metrics summary endpoint."""
    print("\n" + "=" * 60)
    print("📈 Тестирование Metrics Summary")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/api/v1/metrics/summary")
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Metrics summary доступен")
                print(f"   Status: {data.get('status')}")
                
                metrics = data.get('metrics', {})
                print("\n   Текущие метрики:")
                print(f"   • API Health: {metrics.get('api_health')}")
                print(f"   • CLIP Model: {metrics.get('clip_model_loaded')}")
                print(f"   • Products: {metrics.get('active_products')}")
                print(f"   • Vectors: {metrics.get('qdrant_vectors')}")
                
                return True
            else:
                print(f"❌ Ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            return False


async def test_health_checks():
    """Тест health check endpoints."""
    print("\n" + "=" * 60)
    print("🏥 Тестирование Health Checks")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        # Basic health check
        try:
            response = await client.get(f"{API_BASE_URL}/api/v1/health")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Basic health: {data.get('status')}")
            else:
                print(f"❌ Basic health failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        # Detailed health check
        try:
            response = await client.get(f"{API_BASE_URL}/api/v1/health/detailed")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Detailed health: {data.get('status')}")
                
                components = data.get('components', {})
                for name, info in components.items():
                    status = info.get('status') if isinstance(info, dict) else info
                    print(f"   • {name}: {status}")
                
                return True
            else:
                print(f"❌ Detailed health failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False


async def test_search_with_metrics():
    """Тест поиска с проверкой метрик."""
    print("\n" + "=" * 60)
    print("🔍 Тестирование Search с метриками")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Выполнить текстовый поиск
        try:
            print("\n1️⃣  Текстовый поиск...")
            start_time = time.time()
            
            response = await client.post(
                f"{API_BASE_URL}/api/v1/search/by-text",
                json={
                    "query": "красный диван",
                    "limit": 5,
                    "min_similarity": 0.0
                }
            )
            
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Успешно: {data.get('results_count')} результатов")
                print(f"   ⏱️  Время: {duration:.3f}s")
                print(f"   📊 Query time: {data.get('query_time_ms')}ms")
                
                # Проверить заголовок X-Process-Time
                process_time = response.headers.get('X-Process-Time')
                if process_time:
                    print(f"   🔧 Process time: {process_time}s")
            else:
                print(f"   ❌ Ошибка: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
        
        # Небольшая пауза
        await asyncio.sleep(0.5)
        
        # Проверить обновление метрик
        try:
            print("\n2️⃣  Проверка обновления метрик...")
            response = await client.get(f"{API_BASE_URL}/api/v1/metrics")
            
            if response.status_code == 200:
                content = response.text
                
                # Найти метрику total_searches
                if 'visual_search_total_searches_total{search_type="by-text"}' in content:
                    print("   ✅ Метрика total_searches обновлена")
                
                # Найти метрику duration
                if "visual_search_duration_seconds" in content:
                    print("   ✅ Метрика duration записана")
                
                # Найти метрику clip_inference
                if "clip_inference_duration_seconds" in content:
                    print("   ✅ Метрика clip_inference записана")
                    
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")


async def test_logging_middleware():
    """Тест logging middleware."""
    print("\n" + "=" * 60)
    print("📝 Тестирование Logging Middleware")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        try:
            # Сделать несколько запросов
            requests = [
                ("GET", "/api/v1/health"),
                ("GET", "/api/v1/metrics/summary"),
                ("GET", "/api/v1/health/detailed"),
            ]
            
            for method, path in requests:
                response = await client.request(method, f"{API_BASE_URL}{path}")
                
                # Проверить заголовок X-Process-Time
                process_time = response.headers.get('X-Process-Time')
                
                if process_time:
                    print(f"✅ {method} {path}")
                    print(f"   Status: {response.status_code}")
                    print(f"   Process time: {process_time}s")
                else:
                    print(f"⚠️  {method} {path} - нет заголовка X-Process-Time")
                
                await asyncio.sleep(0.2)
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False


async def main():
    """Главная функция."""
    print("\n" + "=" * 70)
    print("  🚀 ТЕСТИРОВАНИЕ СИСТЕМЫ МОНИТОРИНГА")
    print("=" * 70)
    print(f"\n📡 API URL: {API_BASE_URL}")
    
    # Проверить доступность API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/api/v1/health", timeout=5.0)
            if response.status_code != 200:
                print("\n❌ API недоступен. Убедитесь, что сервер запущен:")
                print("   poetry run uvicorn app.api.main:app --reload")
                return
    except Exception as e:
        print(f"\n❌ Не удалось подключиться к API: {e}")
        print("   Убедитесь, что сервер запущен:")
        print("   poetry run uvicorn app.api.main:app --reload")
        return
    
    print("✅ API доступен\n")
    
    # Запустить тесты
    results = []
    
    results.append(await test_health_checks())
    results.append(await test_metrics_endpoint())
    results.append(await test_metrics_summary())
    results.append(await test_logging_middleware())
    results.append(await test_search_with_metrics())
    
    # Итоговый отчёт
    print("\n" + "=" * 70)
    print("  📊 ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 70)
    
    passed = sum(1 for r in results if r)
    total = len(results)
    
    print(f"\n✅ Пройдено тестов: {passed}/{total}")
    
    if passed == total:
        print("🎉 Все тесты прошли успешно!")
    else:
        print("⚠️  Некоторые тесты не прошли. Проверьте логи выше.")
    
    print("\n" + "=" * 70)
    print("💡 Полезные команды:")
    print("=" * 70)
    print("  • Metrics:          curl http://localhost:8000/api/v1/metrics")
    print("  • Metrics summary:  curl http://localhost:8000/api/v1/metrics/summary")
    print("  • Health:           curl http://localhost:8000/api/v1/health")
    print("  • Health detailed:  curl http://localhost:8000/api/v1/health/detailed")
    print("  • Logs:             tail -f logs/app_*.log")
    print("  • Error logs:       tail -f logs/errors_*.log")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

