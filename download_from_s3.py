"""
Скрипт для скачивания изображений из S3-совместимого хранилища BakaiMarket.
Работает автономно, не требует PostgreSQL.

Использование:
    python download_from_s3.py
"""
import sys
from pathlib import Path
import os

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    from tqdm import tqdm
except ImportError:
    print("\n❌ Установите: pip install boto3 tqdm")
    sys.exit(1)

# ============================================================================
# НАСТРОЙКИ S3
# ============================================================================
S3_ENDPOINT = "https://api-cdn.bakai.store"
S3_ACCESS_KEY = "wusYFtZQAnO2FK0U41Ne"
S3_SECRET_KEY = "oINBcpQXXrTUcG1LNE5eDUErrPzBfdDN11SiFOpc"
S3_BUCKET = "product-images"  # Имя bucket с изображениями

OUTPUT_DIR = Path("./cdn_images")
# ============================================================================


def create_s3_client():
    """Создать S3 клиент."""
    try:
        client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name='us-east-1',  # Обычно не важно для MinIO
        )
        return client
    except Exception as e:
        print(f"\n❌ Ошибка создания S3 клиента: {e}")
        sys.exit(1)


def list_all_objects(s3_client, bucket):
    """Получить список всех объектов в bucket."""
    print(f"\n📦 Получение списка файлов из bucket '{bucket}'...")
    
    all_objects = []
    continuation_token = None
    
    try:
        while True:
            if continuation_token:
                response = s3_client.list_objects_v2(
                    Bucket=bucket,
                    MaxKeys=1000,
                    ContinuationToken=continuation_token
                )
            else:
                response = s3_client.list_objects_v2(
                    Bucket=bucket,
                    MaxKeys=1000
                )
            
            if 'Contents' in response:
                objects = response['Contents']
                all_objects.extend(objects)
                print(f"   Найдено: {len(all_objects)} файлов...", end='\r')
            
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
            else:
                break
        
        print(f"\n✅ Всего файлов: {len(all_objects)}")
        return all_objects
        
    except ClientError as e:
        print(f"\n❌ Ошибка доступа к bucket: {e}")
        return []
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        return []


def download_file(s3_client, bucket, key, local_path):
    """Скачать один файл."""
    try:
        s3_client.download_file(bucket, key, str(local_path))
        return True
    except:
        return False


def main():
    """Главная функция."""
    print("\n" + "=" * 70)
    print("  📥 ЗАГРУЗКА ИЗОБРАЖЕНИЙ ИЗ S3 STORAGE")
    print("=" * 70)
    print(f"\n📁 Папка: {OUTPUT_DIR.absolute()}")
    print(f"🪣 Bucket: {S3_BUCKET}")
    print(f"🌐 Endpoint: {S3_ENDPOINT}")
    
    # Создать папку
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Создать S3 клиент
    print("\n🔌 Подключение к S3...")
    s3_client = create_s3_client()
    
    # Тест подключения
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET)
        print("✅ Подключение успешно")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"\n❌ Bucket '{S3_BUCKET}' не найден")
        elif error_code == '403':
            print(f"\n❌ Нет доступа к bucket '{S3_BUCKET}'")
            print("💡 Проверьте access key и secret key")
        else:
            print(f"\n❌ Ошибка: {e}")
        return
    except Exception as e:
        print(f"\n❌ Ошибка подключения: {e}")
        return
    
    # Получить список файлов
    objects = list_all_objects(s3_client, S3_BUCKET)
    
    if not objects:
        print("\n❌ Нет файлов для загрузки")
        return
    
    # Фильтруем только изображения и берем главные (первое изображение товара)
    print("\n🔍 Фильтрация изображений...")
    products_seen = set()
    to_download = []
    
    for obj in objects:
        key = obj['Key']
        
        # Пропустить если не изображение
        if not key.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            continue
        
        # Извлечь ID товара (первая часть пути)
        parts = key.split('/')
        if len(parts) >= 2:
            product_id = parts[0]
        else:
            product_id = Path(key).stem
        
        # Брать только первое изображение каждого товара
        if product_id not in products_seen:
            products_seen.add(product_id)
            
            # Определить локальный путь
            filename = f"{product_id}.jpg"
            local_path = OUTPUT_DIR / filename
            
            # Пропустить если уже есть
            if not local_path.exists():
                to_download.append({
                    'key': key,
                    'path': local_path
                })
    
    print(f"✅ Уникальных товаров: {len(products_seen)}")
    print(f"📥 К загрузке: {len(to_download)}")
    print(f"⏭️  Уже есть: {len(products_seen) - len(to_download)}")
    
    if not to_download:
        print("\n✅ Все изображения уже загружены!")
        return
    
    # Скачать файлы
    print(f"\n🚀 Начинаю загрузку...\n")
    downloaded = 0
    failed = 0
    
    with tqdm(total=len(to_download), desc="Загрузка", unit="img") as pbar:
        for item in to_download:
            success = download_file(s3_client, S3_BUCKET, item['key'], item['path'])
            if success:
                downloaded += 1
            else:
                failed += 1
            
            pbar.update(1)
            pbar.set_postfix({'OK': downloaded, 'ERR': failed})
    
    # Итоги
    print("\n" + "=" * 70)
    print("📊 ИТОГИ")
    print("=" * 70)
    print(f"\n✅ Загружено: {downloaded}/{len(to_download)}")
    if failed > 0:
        print(f"❌ Ошибок: {failed}")
    
    # Размер
    files = list(OUTPUT_DIR.glob("*.jpg"))
    if files:
        total_size = sum(f.stat().st_size for f in files)
        if total_size > 1024**3:
            size_str = f"{total_size / 1024**3:.2f} GB"
        elif total_size > 1024**2:
            size_str = f"{total_size / 1024**2:.2f} MB"
        else:
            size_str = f"{total_size / 1024:.2f} KB"
        
        print(f"\n📁 Папка: {OUTPUT_DIR.absolute()}")
        print(f"💾 Размер: {size_str}")
        print(f"📊 Файлов: {len(files)}")
    
    print("\n💡 Дальше можно проиндексировать эти изображения в Qdrant")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано. Запустите снова для продолжения")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()




