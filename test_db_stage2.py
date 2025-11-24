"""
Тестовый скрипт для проверки работы БД (Этап 2)
"""
import asyncio
from app.db.postgres import (
    get_session,
    create_product,
    get_product_by_external_id,
    get_products,
    delete_product
)
from app.db.qdrant import QdrantManager
from app.config import settings

async def test_postgresql():
    """Тест PostgreSQL операций"""
    print("\n🧪 Тестирование PostgreSQL...")
    
    async with get_session() as session:
        # 1. Создание продукта
        product_data = {
            "external_id": "test_prod_001",
            "title": "Test Product",
            "description": "This is a test product",
            "category": "electronics",
            "price": 99.99,
            "currency": "USD",
            "image_url": "/home/user/Desktop/BakaiMarket/clip/images/car1.jpeg"
        }
        
        print("  ➡️  Создание продукта...")
        product = await create_product(session, product_data)
        print(f"  ✅ Продукт создан: ID={product.id}, external_id={product.external_id}")
        
        # 2. Чтение продукта
        print("  ➡️  Чтение продукта...")
        found = await get_product_by_external_id(session, "test_prod_001")
        if found:
            print(f"  ✅ Продукт найден: {found.title}")
        else:
            print("  ❌ Продукт не найден!")
            
        # 3. Список продуктов
        print("  ➡️  Получение списка продуктов...")
        products = await get_products(session, limit=10)
        print(f"  ✅ Найдено продуктов: {len(products)}")
        
        # 4. Удаление тестового продукта
        print("  ➡️  Удаление тестового продукта...")
        deleted = await delete_product(session, product.id)
        print(f"  ✅ Продукт удалён: {deleted}")

async def test_qdrant():
    """Тест Qdrant операций"""
    print("\n🧪 Тестирование Qdrant...")
    
    manager = QdrantManager(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name=settings.qdrant_collection_name
    )
    
    # 1. Проверка существования коллекции
    print("  ➡️  Проверка коллекции...")
    exists = await manager.collection_exists()
    print(f"  ✅ Коллекция существует: {exists}")
    
    # 2. Информация о коллекции
    print("  ➡️  Получение информации...")
    info = await manager.get_collection_info()
    print(f"  ✅ Векторов в коллекции: {info.get('points_count', 0)}")
    
    # 3. Добавление тестового вектора
    print("  ➡️  Добавление тестового вектора...")
    test_vector = [0.1] * 512  # Фейковый вектор 512 размерности
    result = await manager.upsert_vectors(
        product_ids=["test_vector_001"],
        vectors=[test_vector],
        payloads=[{"title": "Test Vector"}]
    )
    print(f"  ✅ Вектор добавлен: {result}")
    
    # 4. Поиск похожих
    print("  ➡️  Поиск похожих векторов...")
    query_vector = [0.1] * 512
    results = await manager.search_similar(query_vector, top_k=5)
    print(f"  ✅ Найдено результатов: {len(results)}")
    if results:
        print(f"     Первый результат: score={results[0].get('score', 0):.4f}")
    
    # 5. Удаление тестового вектора
    print("  ➡️  Удаление тестового вектора...")
    deleted = await manager.delete_vectors(["test_vector_001"])
    print(f"  ✅ Вектор удалён: {deleted}")

async def main():
    print("=" * 50)
    print("  ТЕСТИРОВАНИЕ ЭТАПА 2: Базы данных")
    print("=" * 50)
    
    try:
        await test_postgresql()
        await test_qdrant()
        
        print("\n" + "=" * 50)
        print("  🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())