#!/usr/bin/env python3
"""Исследование структуры данных CDN API"""
import asyncio
import httpx
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings

async def main():
    print("\n" + "=" * 70)
    print("🔍 ИССЛЕДОВАНИЕ CDN API")
    print("=" * 70)
    
    url = settings.bakai_cdn_api_url
    headers = {
        "X-Access-Key": settings.bakai_cdn_access_key,
        "X-Secret-Key": settings.bakai_cdn_secret_key
    }
    
    print(f"\n🌐 URL: {url}")
    print(f"🔑 Access Key: {settings.bakai_cdn_access_key[:10]}...")
    
    async with httpx.AsyncClient() as client:
        # 1. Получить первые 5 товаров
        print("\n" + "=" * 70)
        print("📦 ЗАПРОС: Первые 5 товаров")
        print("=" * 70)
        
        try:
            response = await client.get(
                f"{url}/products",
                headers=headers,
                params={"limit": 5, "offset": 0},
                timeout=30.0
            )
            
            print(f"\n📊 Статус код: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"\n📋 Ключи ответа: {list(data.keys())}")
                
                products = data.get("products", [])
                print(f"📦 Количество товаров: {len(products)}")
                
                if products:
                    print("\n" + "=" * 70)
                    print("📦 СТРУКТУРА ПЕРВОГО ТОВАРА:")
                    print("=" * 70)
                    print(json.dumps(products[0], indent=2, ensure_ascii=False))
                    
                    print("\n" + "=" * 70)
                    print("📊 ПОЛЯ ТОВАРА:")
                    print("=" * 70)
                    for key, value in products[0].items():
                        value_type = type(value).__name__
                        value_preview = str(value)[:50] if value else "None"
                        print(f"  • {key:20} ({value_type:10}): {value_preview}")
                    
                    # Показать еще несколько товаров
                    if len(products) > 1:
                        print("\n" + "=" * 70)
                        print("📦 СПИСОК ТОВАРОВ (ID, название, изображение):")
                        print("=" * 70)
                        for i, p in enumerate(products, 1):
                            product_id = p.get('id', 'N/A')
                            name = p.get('name', 'N/A')
                            image = p.get('image_url', 'N/A')
                            print(f"\n{i}. ID: {product_id}")
                            print(f"   Название: {name[:60]}")
                            print(f"   Изображение: {image[:80]}")
                
                # Проверить pagination
                print("\n" + "=" * 70)
                print("📊 ИНФОРМАЦИЯ О ПАГИНАЦИИ:")
                print("=" * 70)
                total = data.get('total', 'N/A')
                page = data.get('page', 'N/A')
                limit = data.get('limit', 'N/A')
                print(f"  • Total: {total}")
                print(f"  • Page: {page}")
                print(f"  • Limit: {limit}")
                
            else:
                print(f"\n❌ Ошибка: {response.status_code}")
                print(response.text[:500])
                
        except Exception as e:
            print(f"\n❌ Ошибка запроса: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
