#!/usr/bin/env python3
"""
Скрипт для изучения структуры bucket product-images.
"""
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.utils.bakai_s3_client import BakaiS3Client


def explore_product_images():
    """Explore product-images bucket structure."""
    print("\n" + "=" * 70)
    print("🔍 ИЗУЧЕНИЕ BUCKET: product-images")
    print("=" * 70)
    
    client = BakaiS3Client()
    bucket_name = "product-images"
    
    # Get all objects (or first 1000)
    print("\n📦 Получение списка объектов...")
    objects = client.list_objects(bucket_name, max_keys=1000)
    
    if not objects:
        print("❌ Объекты не найдены")
        return
    
    print(f"✅ Найдено объектов: {len(objects)}")
    
    # Analyze structure
    print("\n" + "=" * 70)
    print("📊 АНАЛИЗ СТРУКТУРЫ")
    print("=" * 70)
    
    # Group by folder
    folders = defaultdict(int)
    file_types = defaultdict(int)
    total_size = 0
    
    for obj in objects:
        key = obj['Key']
        size = obj.get('Size', 0)
        
        # Extract folder (first part before /)
        parts = key.split('/')
        if len(parts) > 1:
            folder = parts[0]
            folders[folder] += 1
        
        # Extract file extension
        ext = Path(key).suffix.lower()
        if ext:
            file_types[ext] += 1
        
        total_size += size
    
    # Display statistics
    print(f"\n📁 Папки (первые 20):")
    for folder, count in sorted(folders.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"   {folder}/: {count} файлов")
    
    print(f"\n📄 Типы файлов:")
    for ext, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
        print(f"   {ext}: {count} файлов")
    
    print(f"\n💾 Общий размер: {total_size / (1024*1024):.2f} MB")
    print(f"📊 Средний размер файла: {total_size / len(objects) / 1024:.2f} KB")
    
    # Show examples
    print("\n" + "=" * 70)
    print("📋 ПРИМЕРЫ ФАЙЛОВ (первые 10)")
    print("=" * 70)
    
    for i, obj in enumerate(objects[:10], 1):
        key = obj['Key']
        size = obj.get('Size', 0)
        modified = obj.get('LastModified')
        
        print(f"\n{i}. {key}")
        print(f"   Размер: {size / 1024:.2f} KB")
        print(f"   Изменен: {modified}")
    
    # Check if there are more objects
    if len(objects) == 1000:
        print("\n⚠️  Показаны только первые 1000 объектов")
        print("   Возможно их больше")
    
    # Download sample image
    print("\n" + "=" * 70)
    print("📥 СКАЧИВАНИЕ ПРИМЕРА")
    print("=" * 70)
    
    if objects:
        sample_key = objects[0]['Key']
        local_path = f"/tmp/sample_product_image{Path(sample_key).suffix}"
        
        print(f"\n📥 Скачивание: {sample_key}")
        success = client.download_file(bucket_name, sample_key, local_path)
        
        if success:
            print(f"✅ Сохранено: {local_path}")
            print(f"\n💡 Откройте файл чтобы посмотреть:")
            print(f"   xdg-open {local_path}")
        else:
            print("❌ Ошибка скачивания")
    
    print("\n" + "=" * 70)
    print("📝 ВЫВОДЫ")
    print("=" * 70)
    
    print(f"\n✅ В bucket 'product-images' найдено {len(objects)} изображений")
    print(f"✅ Файлы организованы по папкам: {len(folders)} папок")
    print(f"✅ Можем скачивать изображения")
    
    print("\n📋 Следующие шаги:")
    print("   1. Получить метаданные товаров (ID, название, категория, цена)")
    print("   2. Сопоставить изображения с товарами")
    print("   3. Создать скрипт синхронизации")
    
    print("=" * 70 + "\n")


def main():
    """Run exploration."""
    explore_product_images()


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<level>{message}</level>",
        level="ERROR"
    )
    
    main()

