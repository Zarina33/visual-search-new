#!/usr/bin/env python3
"""
Скрипт для тестирования подключения к BakaiMarket CDN API.

Проверяет:
1. Подключение к API
2. Получение списка товаров
3. Получение конкретного товара
4. Структуру данных
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.utils.bakai_cdn_client import BakaiCDNClient
from app.config import settings


async def test_connection():
    """Test connection to BakaiMarket API."""
    print("\n" + "=" * 70)
    print("🔍 ТЕСТ 1: Подключение к BakaiMarket API")
    print("=" * 70)
    
    client = BakaiCDNClient()
    
    print(f"\n📋 Настройки:")
    print(f"   API URL: {client.api_url}")
    print(f"   Access Key: {client.access_key[:10]}..." if client.access_key else "   Access Key: NOT SET")
    print(f"   Secret Key: {client.secret_key[:10]}..." if client.secret_key else "   Secret Key: NOT SET")
    
    success = await client.test_connection()
    
    if success:
        print("\n✅ Подключение успешно!")
        return True
    else:
        print("\n❌ Ошибка подключения!")
        return False


async def test_get_products():
    """Test fetching products list."""
    print("\n" + "=" * 70)
    print("📦 ТЕСТ 2: Получение списка товаров")
    print("=" * 70)
    
    client = BakaiCDNClient()
    
    try:
        # Fetch first 5 products
        products = await client.get_products(limit=5, offset=0)
        
        print(f"\n✅ Получено товаров: {len(products)}")
        
        if products:
            print("\n📊 Пример товара:")
            product = products[0]
            
            # Display product info
            print(f"\n   ID: {product.get('id', 'N/A')}")
            print(f"   Title: {product.get('title', 'N/A')}")
            print(f"   Category: {product.get('category', 'N/A')}")
            print(f"   Price: {product.get('price', 'N/A')} {product.get('currency', '')}")
            print(f"   Image URL: {product.get('image_url', 'N/A')}")
            
            # Show all available fields
            print(f"\n   Доступные поля:")
            for key in product.keys():
                print(f"      - {key}")
            
            return True, products
        else:
            print("\n⚠️  Товары не найдены")
            return False, []
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        logger.exception("Failed to fetch products")
        return False, []


async def test_get_product_by_id(product_id: str):
    """Test fetching single product."""
    print("\n" + "=" * 70)
    print(f"🔍 ТЕСТ 3: Получение товара по ID: {product_id}")
    print("=" * 70)
    
    client = BakaiCDNClient()
    
    try:
        product = await client.get_product_by_id(product_id)
        
        if product:
            print(f"\n✅ Товар найден!")
            print(f"\n   ID: {product.get('id', 'N/A')}")
            print(f"   Title: {product.get('title', 'N/A')}")
            print(f"   Description: {product.get('description', 'N/A')[:100]}...")
            print(f"   Category: {product.get('category', 'N/A')}")
            print(f"   Price: {product.get('price', 'N/A')} {product.get('currency', '')}")
            print(f"   Image URL: {product.get('image_url', 'N/A')}")
            return True
        else:
            print(f"\n⚠️  Товар не найден")
            return False
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        logger.exception(f"Failed to fetch product {product_id}")
        return False


async def test_pagination():
    """Test pagination."""
    print("\n" + "=" * 70)
    print("📄 ТЕСТ 4: Пагинация")
    print("=" * 70)
    
    client = BakaiCDNClient()
    
    try:
        # Fetch first page
        page1 = await client.get_products(limit=10, offset=0)
        print(f"\n   Страница 1: {len(page1)} товаров")
        
        # Fetch second page
        page2 = await client.get_products(limit=10, offset=10)
        print(f"   Страница 2: {len(page2)} товаров")
        
        # Check if products are different
        if page1 and page2:
            page1_ids = {p.get('id') for p in page1}
            page2_ids = {p.get('id') for p in page2}
            
            if page1_ids.intersection(page2_ids):
                print("\n⚠️  Предупреждение: найдены дубликаты между страницами")
            else:
                print("\n✅ Пагинация работает корректно")
            
            return True
        else:
            print("\n⚠️  Недостаточно товаров для теста пагинации")
            return False
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        logger.exception("Failed to test pagination")
        return False


async def test_get_all_products():
    """Test fetching all products."""
    print("\n" + "=" * 70)
    print("📦 ТЕСТ 5: Получение всех товаров (первые 50)")
    print("=" * 70)
    
    client = BakaiCDNClient()
    
    try:
        # Fetch max 50 products for testing
        all_products = await client.get_all_products(batch_size=10, max_products=50)
        
        print(f"\n✅ Всего получено: {len(all_products)} товаров")
        
        # Show categories distribution
        if all_products:
            categories = {}
            for product in all_products:
                cat = product.get('category', 'Unknown')
                categories[cat] = categories.get(cat, 0) + 1
            
            print(f"\n📊 Распределение по категориям:")
            for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                print(f"   {cat}: {count}")
            
            return True
        else:
            print("\n⚠️  Товары не найдены")
            return False
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        logger.exception("Failed to fetch all products")
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  🚀 ТЕСТИРОВАНИЕ BAKAI MARKET CDN API")
    print("=" * 70)
    
    results = []
    
    # Test 1: Connection
    result1 = await test_connection()
    results.append(("Подключение", result1))
    
    if not result1:
        print("\n❌ Подключение не удалось. Проверьте credentials в .env")
        return
    
    # Test 2: Get products
    result2, products = await test_get_products()
    results.append(("Получение списка товаров", result2))
    
    # Test 3: Get product by ID (if we have products)
    if products:
        product_id = products[0].get('id')
        if product_id:
            result3 = await test_get_product_by_id(product_id)
            results.append(("Получение товара по ID", result3))
    
    # Test 4: Pagination
    result4 = await test_pagination()
    results.append(("Пагинация", result4))
    
    # Test 5: Get all products
    result5 = await test_get_all_products()
    results.append(("Получение всех товаров", result5))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 70)
    
    for test_name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {test_name}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\n📈 Пройдено: {passed}/{total} тестов")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print("\n⚠️  Некоторые тесты не прошли")
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<level>{message}</level>",
        level="ERROR"  # Only show errors, not debug messages
    )
    
    asyncio.run(main())

