#!/usr/bin/env python3
"""Исследование S3 хранилища BakaiMarket"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.utils.bakai_s3_client import BakaiS3Client

def main():
    print("\n" + "=" * 70)
    print("🔍 ИССЛЕДОВАНИЕ S3 ХРАНИЛИЩА")
    print("=" * 70)
    
    client = BakaiS3Client()
    
    # 1. Список buckets
    print("\n📦 ДОСТУПНЫЕ BUCKETS:")
    print("=" * 70)
    buckets = client.list_buckets()
    for i, bucket in enumerate(buckets, 1):
        print(f"  {i}. {bucket}")
    
    if not buckets:
        print("❌ Нет доступных buckets")
        return
    
    # 2. Список файлов в первом bucket
    print("\n" + "=" * 70)
    print(f"📄 ФАЙЛЫ В BUCKET: {buckets[0]}")
    print("=" * 70)
    
    objects = client.list_objects(buckets[0], max_keys=10)
    
    if objects:
        print(f"\n✅ Найдено файлов: {len(objects)} (показано первые 10)")
        print("\nПримеры файлов:")
        for i, obj in enumerate(objects[:5], 1):
            key = obj.get('Key', '')
            size = obj.get('Size', 0)
            size_mb = size / (1024 * 1024)
            print(f"\n{i}. Файл: {key}")
            print(f"   Размер: {size_mb:.2f} MB")
        
        # Структура путей
        print("\n" + "=" * 70)
        print("📊 СТРУКТУРА ПУТЕЙ:")
        print("=" * 70)
        
        paths = [obj['Key'] for obj in objects]
        # Извлечь ID продуктов
        product_ids = set()
        for path in paths:
            parts = path.split('/')
            if len(parts) >= 2:
                product_ids.add(parts[0])
        
        print(f"\n✅ Найдено уникальных product_id: {len(product_ids)}")
        print(f"   Примеры ID: {list(product_ids)[:10]}")
        
        # Проверить product-images bucket
        if 'product-images' in buckets:
            print("\n" + "=" * 70)
            print("📦 BUCKET: product-images")
            print("=" * 70)
            
            img_objects = client.list_objects('product-images', max_keys=100)
            print(f"\n✅ Файлов: {len(img_objects)}")
            
            # Показать структуру
            if img_objects:
                print("\nПримеры путей:")
                for obj in img_objects[:5]:
                    print(f"  • {obj['Key']}")
    else:
        print("❌ Нет файлов")
    
    print("\n" + "=" * 70 + "\n")

if __name__ == "__main__":
    main()
