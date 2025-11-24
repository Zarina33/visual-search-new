"""
Скрипт для тестирования API визуального поиска.

Тестирует все endpoints:
- POST /api/v1/search/by-text
- POST /api/v1/search/by-image
- GET /api/v1/search/similar/{product_id}
"""
import asyncio
import httpx
from pathlib import Path
from loguru import logger

# API base URL
API_BASE_URL = "http://localhost:8000"


async def test_text_search():
    """Тест текстового поиска."""
    print("\n" + "=" * 70)
    print("🔍 ТЕСТ 1: Поиск по тексту")
    print("=" * 70)
    
    async with httpx.AsyncClient() as client:
        # Тест 1: Поиск машин
        print("\n📝 Запрос: 'автомобиль'")
        response = await client.post(
            f"{API_BASE_URL}/api/v1/search/by-text",
            json={
                "query": "автомобиль",
                "limit": 5,
                "min_similarity": 0.0
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Статус: {response.status_code}")
            print(f"⏱️  Время: {data['query_time_ms']}ms")
            print(f"📊 Результатов: {data['results_count']}")
            
            for i, result in enumerate(data['results'][:3], 1):
                print(f"\n   {i}. {result['title']}")
                print(f"      Category: {result['category']}")
                print(f"      Price: {result['price']} {result['currency']}")
                print(f"      Similarity: {result['similarity_score']:.4f}")
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(response.text)
        
        # Тест 2: Поиск мебели
        print("\n📝 Запрос: 'диван'")
        response = await client.post(
            f"{API_BASE_URL}/api/v1/search/by-text",
            json={
                "query": "диван",
                "limit": 5,
                "min_similarity": 0.0
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Статус: {response.status_code}")
            print(f"⏱️  Время: {data['query_time_ms']}ms")
            print(f"📊 Результатов: {data['results_count']}")
            
            for i, result in enumerate(data['results'][:3], 1):
                print(f"\n   {i}. {result['title']}")
                print(f"      Category: {result['category']}")
                print(f"      Similarity: {result['similarity_score']:.4f}")
        else:
            print(f"❌ Ошибка: {response.status_code}")


async def test_image_search():
    """Тест поиска по изображению."""
    print("\n" + "=" * 70)
    print("🖼️  ТЕСТ 2: Поиск по изображению")
    print("=" * 70)
    
    # Путь к тестовому изображению
    test_image = Path("/home/user/Desktop/BakaiMarket/clip/images/car1.jpeg")
    
    if not test_image.exists():
        print(f"❌ Тестовое изображение не найдено: {test_image}")
        return
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"\n📸 Загружаем изображение: {test_image.name}")
        
        with open(test_image, "rb") as f:
            files = {"image": (test_image.name, f, "image/jpeg")}
            response = await client.post(
                f"{API_BASE_URL}/api/v1/search/by-image",
                files=files,
                params={
                    "limit": 5,
                    "min_similarity": 0.0
                }
            )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Статус: {response.status_code}")
            print(f"⏱️  Время: {data['query_time_ms']}ms")
            print(f"📊 Результатов: {data['results_count']}")
            
            for i, result in enumerate(data['results'][:5], 1):
                print(f"\n   {i}. {result['title']}")
                print(f"      Category: {result['category']}")
                print(f"      Price: {result['price']} {result['currency']}")
                print(f"      Similarity: {result['similarity_score']:.4f}")
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(response.text)


async def test_similar_products():
    """Тест поиска похожих товаров."""
    print("\n" + "=" * 70)
    print("🔄 ТЕСТ 3: Поиск похожих товаров")
    print("=" * 70)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Сначала получим список товаров
        print("\n📝 Получаем список товаров...")
        
        # Используем текстовый поиск для получения ID товара
        response = await client.post(
            f"{API_BASE_URL}/api/v1/search/by-text",
            json={
                "query": "car",
                "limit": 1,
                "min_similarity": 0.0
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data['results_count'] > 0:
                product_id = data['results'][0]['external_id']
                product_title = data['results'][0]['title']
                
                print(f"✅ Найден товар: {product_title} (ID: {product_id})")
                print(f"\n🔍 Ищем похожие товары...")
                
                # Поиск похожих
                response = await client.get(
                    f"{API_BASE_URL}/api/v1/search/similar/{product_id}",
                    params={"limit": 5}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Статус: {response.status_code}")
                    print(f"⏱️  Время: {data['query_time_ms']}ms")
                    print(f"📊 Результатов: {data['results_count']}")
                    
                    for i, result in enumerate(data['results'], 1):
                        print(f"\n   {i}. {result['title']}")
                        print(f"      Category: {result['category']}")
                        print(f"      Similarity: {result['similarity_score']:.4f}")
                else:
                    print(f"❌ Ошибка: {response.status_code}")
                    print(response.text)
            else:
                print("❌ Товары не найдены")
        else:
            print(f"❌ Ошибка при получении списка товаров: {response.status_code}")


async def test_health():
    """Тест health endpoint."""
    print("\n" + "=" * 70)
    print("❤️  ТЕСТ 0: Health Check")
    print("=" * 70)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/api/v1/health")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API работает")
            print(f"   Service: {data['service']}")
            print(f"   Version: {data['version']}")
            print(f"   Status: {data['status']}")
        else:
            print(f"❌ API не отвечает: {response.status_code}")


async def main():
    """Запуск всех тестов."""
    print("\n" + "=" * 70)
    print("  🚀 ТЕСТИРОВАНИЕ API ВИЗУАЛЬНОГО ПОИСКА")
    print("=" * 70)
    print(f"\n🌐 API URL: {API_BASE_URL}")
    
    try:
        # Проверка доступности API
        await test_health()
        
        # Тесты поиска
        await test_text_search()
        await test_image_search()
        await test_similar_products()
        
        print("\n" + "=" * 70)
        print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
        print("=" * 70 + "\n")
        
    except httpx.ConnectError:
        print("\n❌ Не удалось подключиться к API!")
        print("   Убедитесь что сервер запущен:")
        print("   poetry run uvicorn app.api.main:app --host 0.0.0.0 --port 8000")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)


if __name__ == "__main__":
    # Настройка логирования
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<level>{message}</level>",
        level="ERROR"
    )
    
    asyncio.run(main())

