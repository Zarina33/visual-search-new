#!/usr/bin/env python3
"""
Полное тестирование всей системы визуального поиска.

Проверяет:
1. Инфраструктуру (Docker, базы данных)
2. CLIP модель
3. API endpoints
4. Webhooks
5. Производительность
"""
import asyncio
import sys
from pathlib import Path
import httpx
import time
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.config import settings
from app.db.postgres import get_session, get_products_count
from app.db.qdrant import QdrantManager
from app.models.clip_model import CLIPEmbedder


API_URL = "http://localhost:8000"
TEST_IMAGES_DIR = Path(__file__).parent.parent / "test_images"


class SystemTester:
    """Тестер всей системы."""
    
    def __init__(self):
        self.results = {
            "infrastructure": {},
            "clip_model": {},
            "api": {},
            "webhooks": {},
            "performance": {}
        }
        self.all_passed = True
    
    def mark_test(self, category: str, test_name: str, passed: bool, details: str = ""):
        """Отметить результат теста."""
        self.results[category][test_name] = {
            "passed": passed,
            "details": details
        }
        
        if not passed:
            self.all_passed = False
        
        status = "✅" if passed else "❌"
        logger.info(f"{status} {category}.{test_name}: {details}")
    
    async def test_infrastructure(self):
        """Тест инфраструктуры."""
        print("\n" + "=" * 70)
        print("🏗️  ТЕСТ 1: ИНФРАСТРУКТУРА")
        print("=" * 70)
        
        # PostgreSQL
        try:
            async with get_session() as session:
                count = await get_products_count(session)
                self.mark_test("infrastructure", "postgresql", True, f"{count} products in database")
        except Exception as e:
            self.mark_test("infrastructure", "postgresql", False, str(e))
        
        # Qdrant
        try:
            qdrant = QdrantManager()
            info = await qdrant.get_collection_info()
            count = info.get("vectors_count", 0)
            self.mark_test("infrastructure", "qdrant", True, f"{count} vectors in collection")
        except Exception as e:
            self.mark_test("infrastructure", "qdrant", False, str(e))
    
    async def test_clip_model(self):
        """Тест CLIP модели."""
        print("\n" + "=" * 70)
        print("🧠 ТЕСТ 2: CLIP МОДЕЛЬ")
        print("=" * 70)
        
        try:
            embedder = CLIPEmbedder()
            
            # Тест текстового эмбеддинга
            text_emb = embedder.encode_text("test product")
            self.mark_test("clip_model", "text_embedding", True, f"shape: {text_emb.shape}")
            
            # Тест изображения
            test_image = TEST_IMAGES_DIR / "red_square.jpg"
            if test_image.exists():
                img_emb = await embedder.generate_embedding(str(test_image))
                self.mark_test("clip_model", "image_embedding", True, f"shape: {img_emb.shape}")
            else:
                self.mark_test("clip_model", "image_embedding", False, "Test image not found")
            
        except Exception as e:
            self.mark_test("clip_model", "initialization", False, str(e))
    
    async def test_api_endpoints(self):
        """Тест API endpoints."""
        print("\n" + "=" * 70)
        print("🔌 ТЕСТ 3: API ENDPOINTS")
        print("=" * 70)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Health check
            try:
                response = await client.get(f"{API_URL}/api/v1/health")
                passed = response.status_code == 200
                self.mark_test("api", "health_check", passed, f"status: {response.status_code}")
            except Exception as e:
                self.mark_test("api", "health_check", False, str(e))
            
            # Text search
            try:
                response = await client.post(
                    f"{API_URL}/api/v1/search/by-text",
                    json={"query": "product", "limit": 5}
                )
                passed = response.status_code == 200
                if passed:
                    data = response.json()
                    self.mark_test("api", "text_search", True, f"{data['results_count']} results in {data['query_time_ms']}ms")
                else:
                    self.mark_test("api", "text_search", False, f"status: {response.status_code}")
            except Exception as e:
                self.mark_test("api", "text_search", False, str(e))
            
            # Image search
            try:
                test_image = TEST_IMAGES_DIR / "blue_square.jpg"
                if test_image.exists():
                    with open(test_image, 'rb') as f:
                        files = {'image': ('test.jpg', f, 'image/jpeg')}
                        response = await client.post(
                            f"{API_URL}/api/v1/search/by-image",
                            files=files,
                            params={'limit': 5}
                        )
                    
                    passed = response.status_code == 200
                    if passed:
                        data = response.json()
                        self.mark_test("api", "image_search", True, f"{data['results_count']} results in {data['query_time_ms']}ms")
                    else:
                        self.mark_test("api", "image_search", False, f"status: {response.status_code}")
                else:
                    self.mark_test("api", "image_search", False, "Test image not found")
            except Exception as e:
                self.mark_test("api", "image_search", False, str(e))
            
            # Metrics
            try:
                response = await client.get(f"{API_URL}/api/v1/metrics")
                passed = response.status_code == 200 and "visual_search" in response.text
                self.mark_test("api", "metrics", passed, f"status: {response.status_code}")
            except Exception as e:
                self.mark_test("api", "metrics", False, str(e))
    
    async def test_webhooks(self):
        """Тест webhooks."""
        print("\n" + "=" * 70)
        print("🔗 ТЕСТ 4: WEBHOOKS")
        print("=" * 70)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Webhook health
            try:
                response = await client.get(f"{API_URL}/api/v1/webhooks/health")
                passed = response.status_code == 200
                self.mark_test("webhooks", "health", passed, f"status: {response.status_code}")
            except Exception as e:
                self.mark_test("webhooks", "health", False, str(e))
            
            # Test webhook endpoint
            try:
                webhook_data = {
                    "event_type": "product.created",
                    "event_id": "system_test_001",
                    "timestamp": "2025-11-12T10:00:00Z",
                    "data": {
                        "product_id": "test_system",
                        "title": "System Test Product",
                        "category": "test"
                    }
                }
                
                response = await client.post(
                    f"{API_URL}/api/v1/webhooks/test",
                    json=webhook_data
                )
                
                passed = response.status_code == 200
                if passed:
                    data = response.json()
                    self.mark_test("webhooks", "test_endpoint", True, f"task_id: {data.get('task_id', 'N/A')}")
                else:
                    self.mark_test("webhooks", "test_endpoint", False, f"status: {response.status_code}")
            except Exception as e:
                self.mark_test("webhooks", "test_endpoint", False, str(e))
    
    async def test_performance(self):
        """Тест производительности."""
        print("\n" + "=" * 70)
        print("⚡ ТЕСТ 5: ПРОИЗВОДИТЕЛЬНОСТЬ")
        print("=" * 70)
        
        test_image = TEST_IMAGES_DIR / "green_square.jpg"
        if not test_image.exists():
            self.mark_test("performance", "search_speed", False, "Test image not found")
            return
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Тест скорости поиска (10 запросов)
            times = []
            
            for i in range(10):
                try:
                    start = time.time()
                    
                    with open(test_image, 'rb') as f:
                        files = {'image': ('test.jpg', f, 'image/jpeg')}
                        response = await client.post(
                            f"{API_URL}/api/v1/search/by-image",
                            files=files,
                            params={'limit': 10}
                        )
                    
                    elapsed = time.time() - start
                    
                    if response.status_code == 200:
                        times.append(elapsed)
                    
                except Exception as e:
                    logger.warning(f"Performance test iteration {i+1} failed: {e}")
            
            if times:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                
                passed = avg_time < 2.0  # Должно быть быстрее 2 секунд
                
                self.mark_test(
                    "performance",
                    "search_speed",
                    passed,
                    f"avg: {avg_time:.3f}s, min: {min_time:.3f}s, max: {max_time:.3f}s"
                )
            else:
                self.mark_test("performance", "search_speed", False, "No successful requests")
    
    def print_summary(self):
        """Вывести итоговую сводку."""
        print("\n" + "=" * 70)
        print("📊 ИТОГОВАЯ СВОДКА")
        print("=" * 70)
        
        total_tests = 0
        passed_tests = 0
        
        for category, tests in self.results.items():
            print(f"\n{category.upper()}:")
            for test_name, result in tests.items():
                total_tests += 1
                if result["passed"]:
                    passed_tests += 1
                
                status = "✅" if result["passed"] else "❌"
                print(f"  {status} {test_name}: {result['details']}")
        
        print("\n" + "=" * 70)
        print(f"ВСЕГО ТЕСТОВ: {total_tests}")
        print(f"ПРОЙДЕНО: {passed_tests}")
        print(f"ПРОВАЛЕНО: {total_tests - passed_tests}")
        print(f"ПРОЦЕНТ УСПЕХА: {(passed_tests/total_tests*100):.1f}%")
        print("=" * 70)
        
        if self.all_passed:
            print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! СИСТЕМА РАБОТАЕТ ОТЛИЧНО!")
        else:
            print("\n⚠️  НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ. ПРОВЕРЬТЕ ДЕТАЛИ ВЫШЕ.")
        
        print()


async def main():
    """Главная функция."""
    print("\n" + "=" * 70)
    print("  🧪 ПОЛНОЕ ТЕСТИРОВАНИЕ СИСТЕМЫ ВИЗУАЛЬНОГО ПОИСКА")
    print("=" * 70)
    
    tester = SystemTester()
    
    try:
        await tester.test_infrastructure()
        await tester.test_clip_model()
        await tester.test_api_endpoints()
        await tester.test_webhooks()
        await tester.test_performance()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Тестирование прервано пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    finally:
        tester.print_summary()
    
    # Вернуть код выхода
    sys.exit(0 if tester.all_passed else 1)


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, format="<level>{message}</level>", level="INFO")
    
    asyncio.run(main())

