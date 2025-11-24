#!/usr/bin/env python3
"""
Скрипт для тестирования подключения к BakaiMarket S3 storage.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.utils.bakai_s3_client import BakaiS3Client
from app.config import settings


def test_connection():
    """Test connection to S3."""
    print("\n" + "=" * 70)
    print("🔍 ТЕСТ 1: Подключение к BakaiMarket S3")
    print("=" * 70)
    
    client = BakaiS3Client()
    
    print(f"\n📋 Настройки:")
    print(f"   Endpoint: {client.endpoint_url}")
    print(f"   Access Key: {client.access_key[:10]}..." if client.access_key else "   Access Key: NOT SET")
    print(f"   Secret Key: {client.secret_key[:10]}..." if client.secret_key else "   Secret Key: NOT SET")
    
    success = client.test_connection()
    
    if success:
        print("\n✅ Подключение успешно!")
        return True
    else:
        print("\n❌ Ошибка подключения!")
        return False


def test_list_buckets():
    """Test listing buckets."""
    print("\n" + "=" * 70)
    print("📦 ТЕСТ 2: Список buckets (контейнеров)")
    print("=" * 70)
    
    client = BakaiS3Client()
    
    try:
        buckets = client.list_buckets()
        
        print(f"\n✅ Найдено buckets: {len(buckets)}")
        
        if buckets:
            print("\n📋 Доступные buckets:")
            for i, bucket in enumerate(buckets, 1):
                print(f"   {i}. {bucket}")
            
            return True, buckets
        else:
            print("\n⚠️  Buckets не найдены или нет доступа")
            return False, []
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        logger.exception("Failed to list buckets")
        return False, []


def test_list_objects(bucket_name: str):
    """Test listing objects in a bucket."""
    print("\n" + "=" * 70)
    print(f"📄 ТЕСТ 3: Список объектов в bucket '{bucket_name}'")
    print("=" * 70)
    
    client = BakaiS3Client()
    
    try:
        objects = client.list_objects(bucket_name, max_keys=10)
        
        print(f"\n✅ Найдено объектов: {len(objects)}")
        
        if objects:
            print("\n📋 Первые объекты:")
            for i, obj in enumerate(objects[:5], 1):
                key = obj.get('Key', 'N/A')
                size = obj.get('Size', 0)
                modified = obj.get('LastModified', 'N/A')
                
                print(f"\n   {i}. {key}")
                print(f"      Size: {size} bytes ({size / 1024:.2f} KB)")
                print(f"      Modified: {modified}")
            
            return True, objects
        else:
            print("\n⚠️  Объекты не найдены")
            return False, []
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        logger.exception(f"Failed to list objects in {bucket_name}")
        return False, []


def test_download_file(bucket_name: str, object_key: str):
    """Test downloading a file."""
    print("\n" + "=" * 70)
    print(f"⬇️  ТЕСТ 4: Скачивание файла")
    print("=" * 70)
    
    client = BakaiS3Client()
    
    try:
        local_path = f"/tmp/bakai_test_{Path(object_key).name}"
        
        print(f"\n📥 Скачивание:")
        print(f"   Bucket: {bucket_name}")
        print(f"   Key: {object_key}")
        print(f"   Local: {local_path}")
        
        success = client.download_file(bucket_name, object_key, local_path)
        
        if success:
            # Check file exists
            if Path(local_path).exists():
                file_size = Path(local_path).stat().st_size
                print(f"\n✅ Файл скачан успешно!")
                print(f"   Размер: {file_size} bytes ({file_size / 1024:.2f} KB)")
                return True
            else:
                print(f"\n❌ Файл не найден после скачивания")
                return False
        else:
            print(f"\n❌ Ошибка скачивания")
            return False
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        logger.exception("Failed to download file")
        return False


def test_presigned_url(bucket_name: str, object_key: str):
    """Test generating presigned URL."""
    print("\n" + "=" * 70)
    print(f"🔗 ТЕСТ 5: Генерация presigned URL")
    print("=" * 70)
    
    client = BakaiS3Client()
    
    try:
        url = client.generate_presigned_url(bucket_name, object_key, expiration=3600)
        
        if url:
            print(f"\n✅ Presigned URL сгенерирован!")
            print(f"\n   URL: {url[:100]}...")
            print(f"\n   Срок действия: 1 час")
            print(f"\n💡 Этот URL можно использовать для прямого доступа к файлу")
            return True
        else:
            print(f"\n❌ Не удалось сгенерировать URL")
            return False
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        logger.exception("Failed to generate presigned URL")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  🚀 ТЕСТИРОВАНИЕ BAKAI MARKET S3 STORAGE")
    print("=" * 70)
    
    results = []
    
    # Test 1: Connection
    result1 = test_connection()
    results.append(("Подключение", result1))
    
    if not result1:
        print("\n❌ Подключение не удалось. Проверьте credentials в .env")
        return
    
    # Test 2: List buckets
    result2, buckets = test_list_buckets()
    results.append(("Список buckets", result2))
    
    if not buckets:
        print("\n⚠️  Нет доступных buckets. Свяжитесь с командой BakaiMarket.")
        print("\nВозможно нужно:")
        print("  1. Активировать доступ к buckets")
        print("  2. Узнать правильное имя bucket")
        print("  3. Настроить права доступа")
        return
    
    # Test 3: List objects in first bucket
    bucket_name = buckets[0]
    result3, objects = test_list_objects(bucket_name)
    results.append(("Список объектов", result3))
    
    # Test 4: Download file (if objects exist)
    if objects:
        object_key = objects[0]['Key']
        result4 = test_download_file(bucket_name, object_key)
        results.append(("Скачивание файла", result4))
        
        # Test 5: Presigned URL
        result5 = test_presigned_url(bucket_name, object_key)
        results.append(("Presigned URL", result5))
    
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
        print("\n📝 Следующие шаги:")
        print("  1. Изучить структуру данных в buckets")
        print("  2. Найти bucket с изображениями товаров")
        print("  3. Создать скрипт синхронизации")
    else:
        print("\n⚠️  Некоторые тесты не прошли")
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<level>{message}</level>",
        level="ERROR"  # Only show errors
    )
    
    main()

