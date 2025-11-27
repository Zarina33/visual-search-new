#!/usr/bin/env python3
"""
Скачивание изображений из S3 в локальную папку и индексация.
НЕ удаляет файлы после обработки.

Использование:
    python scripts/download_and_index_local.py --limit 100  # тест
    python scripts/download_and_index_local.py              # все
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Tuple, Optional
from tqdm import tqdm
import time
from PIL import Image
import io

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.utils.bakai_s3_client import BakaiS3Client
from app.models.clip_model import CLIPEmbedder, CLIPModel
from app.db.qdrant import QdrantManager
from app.db import get_session, create_product
from app.config import settings

# Настройки
LOCAL_STORAGE = Path.home() / "product-images"  # Локальное хранилище
BASE_URL = "http://localhost/images"  # Base URL для nginx
BUCKET_NAME = "product-images"
BATCH_SIZE = 32
MIN_IMAGE_SIZE = 50


def extract_product_id(s3_key: str) -> str:
    """Извлечь ID товара из пути."""
    parts = s3_key.split('/')
    if len(parts) >= 2:
        return parts[0]
    return "unknown"


def is_main_image(s3_key: str) -> bool:
    """Проверить что это главное изображение."""
    filename = Path(s3_key).stem
    return filename.endswith('_1')


def validate_and_save_image(
    image_data: bytes,
    product_id: str,
    filename: str
) -> Optional[Path]:
    """Валидировать и сохранить изображение."""
    try:
        # Проверка размера файла
        if len(image_data) < 1000 or len(image_data) > 20 * 1024 * 1024:
            logger.warning(f"Неверный размер файла для {product_id}/{filename}: {len(image_data)} байт")
            return None
        
        # Открыть изображение
        try:
            img = Image.open(io.BytesIO(image_data))
            # Проверить что изображение не повреждено
            img.verify()
            # После verify() нужно переоткрыть
            img = Image.open(io.BytesIO(image_data))
        except Exception as e:
            logger.warning(f"Поврежденное изображение {product_id}/{filename}: {e}")
            return None
        
        # Проверка размеров изображения
        if img.size[0] < MIN_IMAGE_SIZE or img.size[1] < MIN_IMAGE_SIZE:
            logger.warning(f"Изображение слишком маленькое {product_id}/{filename}: {img.size}")
            return None
        
        # Проверка формата
        if img.format not in ['JPEG', 'PNG', 'WEBP', 'BMP']:
            logger.warning(f"Неподдерживаемый формат {product_id}/{filename}: {img.format}")
            return None
        
        # Конвертировать в RGB
        if img.mode != 'RGB':
            try:
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode in ('RGBA', 'LA'):
                    rgb_img.paste(img, mask=img.split()[-1])
                else:
                    rgb_img.paste(img)
                img = rgb_img
            except Exception as e:
                logger.warning(f"Ошибка конвертации в RGB {product_id}/{filename}: {e}")
                return None
        
        # Создать путь
        product_dir = LOCAL_STORAGE / product_id
        product_dir.mkdir(parents=True, exist_ok=True)
        
        save_path = product_dir / f"{filename}.jpg"
        
        # Сохранить с проверкой
        try:
            img.save(save_path, 'JPEG', quality=85, optimize=True)
            
            # Проверить что файл действительно сохранился и можно открыть
            test_img = Image.open(save_path)
            test_img.verify()
            test_img.close()
            
        except Exception as e:
            logger.warning(f"Ошибка сохранения {product_id}/{filename}: {e}")
            if save_path.exists():
                save_path.unlink()  # Удалить поврежденный файл
            return None
        
        return save_path
        
    except Exception as e:
        logger.error(f"Ошибка обработки изображения {product_id}/{filename}: {e}")
        return None


async def download_all_images(s3_client: BakaiS3Client, limit: Optional[int] = None):
    """
    Скачать все изображения из S3 в локальную папку.
    
    Returns:
        List[(product_id, local_path)]
    """
    print("\n" + "=" * 70)
    print("📥 СКАЧИВАНИЕ ИЗОБРАЖЕНИЙ ИЗ S3")
    print("=" * 70)
    
    # Получить список файлов
    print("\n📋 Получение списка файлов...")
    all_objects = []
    continuation_token = None
    
    while True:
        if continuation_token:
            response = s3_client.s3_client.list_objects_v2(
                Bucket=BUCKET_NAME,
                ContinuationToken=continuation_token,
                MaxKeys=1000
            )
        else:
            response = s3_client.s3_client.list_objects_v2(
                Bucket=BUCKET_NAME,
                MaxKeys=1000
            )
        
        objects = response.get('Contents', [])
        all_objects.extend(objects)
        
        print(f"   Найдено файлов: {len(all_objects)}...", end='\r')
        
        if not response.get('IsTruncated'):
            break
        
        continuation_token = response.get('NextContinuationToken')
    
    print(f"\n✅ Всего файлов в S3: {len(all_objects)}")
    
    # Подготовить все изображения для скачивания
    all_images = []
    for obj in all_objects:
        key = obj['Key']
        product_id = extract_product_id(key)
        all_images.append({
            'product_id': product_id,
            'key': key,
            'size': obj['Size']
        })
    
    print(f"✅ Изображений для обработки: {len(all_images)}")
    
    if limit:
        all_images = all_images[:limit]
        print(f"⚠️  Ограничение: обработка {limit} изображений")
    
    # Скачать изображения
    print("\n📥 Скачивание и сохранение изображений...")
    LOCAL_STORAGE.mkdir(parents=True, exist_ok=True)
    
    downloaded = []
    skipped = 0
    failed_validation = 0
    failed_download = 0
    
    for img in tqdm(all_images, desc="Downloading", unit="img"):
        product_id = img['product_id']
        key = img['key']
        filename = Path(key).stem
        
        # Проверить что файл уже не скачан
        expected_path = LOCAL_STORAGE / product_id / f"{filename}.jpg"
        if expected_path.exists():
            # Проверить что существующий файл валиден
            try:
                test_img = Image.open(expected_path)
                test_img.verify()
                test_img.close()
                downloaded.append((product_id, expected_path))
                skipped += 1
                continue
            except Exception:
                # Файл поврежден, удалить и скачать заново
                logger.warning(f"Существующий файл поврежден, переcкачиваем: {expected_path}")
                expected_path.unlink()
        
        try:
            # Скачать из S3
            response = s3_client.s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
            image_data = response['Body'].read()
            
            # Сохранить с валидацией
            local_path = validate_and_save_image(image_data, product_id, filename)
            
            if local_path:
                downloaded.append((product_id, local_path))
            else:
                failed_validation += 1
            
        except Exception as e:
            logger.warning(f"Ошибка скачивания {key}: {e}")
            failed_download += 1
            continue
    
    print(f"\n✅ Скачано и проверено: {len(downloaded)}")
    if skipped > 0:
        print(f"⏭️  Пропущено (уже есть): {skipped}")
    if failed_validation > 0:
        print(f"⚠️  Не прошли валидацию: {failed_validation}")
    if failed_download > 0:
        print(f"❌ Ошибки скачивания: {failed_download}")
    
    return downloaded


async def generate_embeddings(
    embedder: CLIPEmbedder,
    images: List[Tuple[str, Path]]
) -> List[Tuple[str, list]]:
    """Генерировать эмбеддинги из локальных файлов."""
    print("\n" + "=" * 70)
    print("🧠 ГЕНЕРАЦИЯ ЭМБЕДДИНГОВ")
    print("=" * 70)
    
    embeddings = []
    
    for i in tqdm(range(0, len(images), BATCH_SIZE), desc="CLIP", unit="batch"):
        batch = images[i:i + BATCH_SIZE]
        
        # Подготовить пути для batch
        batch_paths = [str(img_path) for _, img_path in batch]
        batch_ids = [product_id for product_id, _ in batch]
        
        try:
            # Генерировать эмбеддинги батчем
            batch_embeddings = await embedder.generate_embeddings_batch(batch_paths)
            
            # Добавить результаты
            for product_id, embedding in zip(batch_ids, batch_embeddings):
                if embedding is not None:
                    embeddings.append((product_id, embedding.tolist()))
        except Exception as e:
            logger.error(f"Ошибка batch эмбеддинга: {e}")
            # Fallback: обработать по одному
            for product_id, img_path in batch:
                try:
                    embedding = await embedder.generate_embedding(str(img_path))
                    if embedding is not None:
                        embeddings.append((product_id, embedding.tolist()))
                except Exception as e2:
                    logger.error(f"Ошибка эмбеддинга {product_id}: {e2}")
                    continue
    
    print(f"\n✅ Сгенерировано эмбеддингов: {len(embeddings)}")
    return embeddings


async def save_to_databases(
    images: List[Tuple[str, Path]],
    embeddings: List[Tuple[str, list]]
):
    """Сохранить в PostgreSQL и Qdrant."""
    print("\n" + "=" * 70)
    print("💾 СОХРАНЕНИЕ В БАЗЫ ДАННЫХ")
    print("=" * 70)
    
    # Создать словарь эмбеддингов
    embeddings_dict = {pid: emb for pid, emb in embeddings}
    
    # Подготовить данные
    products_data = []
    qdrant_data = []
    seen_products = set()  # Дедупликация
    
    for product_id, img_path in images:
        if product_id not in embeddings_dict:
            continue
        
        # Пропустить если уже обработан
        if product_id in seen_products:
            continue
        seen_products.add(product_id)
        
        # Локальный URL
        relative_path = img_path.relative_to(LOCAL_STORAGE)
        #local_url = f"{BASE_URL}/{relative_path}"
        local_url = f"/images/{relative_path}"
        # Данные товара
        product_data = {
            "external_id": f"bakai_{product_id}",
            "title": f"Product {product_id}",
            "description": f"BakaiMarket product ID: {product_id}",
            "category": "bakai",
            "price": None,
            "currency": None,
            "image_url": local_url,
            "product_metadata": {
                "source": "s3",
                "product_id": product_id,
                "local_path": str(img_path)
            }
        }
        
        products_data.append(product_data)
        
        # Данные для Qdrant
        qdrant_data.append({
            "id": f"bakai_{product_id}",
            "vector": embeddings_dict[product_id],
            "payload": {
                "external_id": f"bakai_{product_id}",
                "original_id": product_id
            }
        })
    
    # Сохранить в PostgreSQL
    print("\n💾 Сохранение в PostgreSQL...")
    saved = 0
    skipped = 0
    
    from sqlalchemy import select
    from app.db.postgres import Product, get_product_by_external_id
    
    for product_data in tqdm(products_data, desc="PostgreSQL", unit="товар"):
        try:
            # Создать отдельную сессию для каждого товара
            async with get_session() as session:
                # Проверить существует ли уже
                existing = await get_product_by_external_id(session, product_data['external_id'])
                if existing:
                    skipped += 1
                    continue
                
                await create_product(session, product_data)
                saved += 1
        except Exception as e:
            # Ignore duplicates
            if 'duplicate key' in str(e).lower():
                skipped += 1
    
    print(f"✅ PostgreSQL: {saved}/{len(products_data)}")
    if skipped > 0:
        print(f"⏭️  Пропущено (дубликаты): {skipped}")
    
    # Сохранить в Qdrant
    print("\n💾 Сохранение в Qdrant...")
    qdrant = QdrantManager()  # Автоматически подключается в __init__
    
    for i in tqdm(range(0, len(qdrant_data), 1000), desc="Qdrant", unit="batch"):
        batch = qdrant_data[i:i+1000]
        
        # Разделить на отдельные списки
        product_ids = [item['id'] for item in batch]
        vectors = [item['vector'] for item in batch]
        payloads = [item['payload'] for item in batch]
        
        await qdrant.upsert_vectors(product_ids, vectors, payloads)
    
    print(f"✅ Qdrant: {len(qdrant_data)} векторов")


async def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Скачать и проиндексировать изображения")
    parser.add_argument("--limit", type=int, help="Лимит товаров")
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("🚀 СКАЧИВАНИЕ И ИНДЕКСАЦИЯ ИЗОБРАЖЕНИЙ")
    print("=" * 70)
    print(f"\n📁 Локальное хранилище: {LOCAL_STORAGE}")
    print(f"🔗 Base URL: {BASE_URL}")
    print(f"📦 S3 Bucket: {BUCKET_NAME}")
    
    start_time = time.time()
    
    # Инициализация
    print("\n⚙️  Инициализация...")
    s3_client = BakaiS3Client()
    embedder = CLIPEmbedder(device=settings.clip_device)
    print("✅ Готово")
    
    # 1. Скачать изображения
    images = await download_all_images(s3_client, limit=args.limit)
    
    if not images:
        print("\n❌ Нет изображений для обработки")
        return
    
    # 2. Генерировать эмбеддинги
    embeddings = await generate_embeddings(embedder, images)
    
    if not embeddings:
        print("\n❌ Не удалось создать эмбеддинги")
        return
    
    # 3. Сохранить в БД
    await save_to_databases(images, embeddings)
    
    # Итоги
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("📊 ИТОГИ")
    print("=" * 70)
    print(f"\n✅ Обработано товаров: {len(images)}")
    print(f"🧠 Создано эмбеддингов: {len(embeddings)}")
    print(f"⏱️  Время: {elapsed:.2f} сек ({elapsed/60:.2f} мин)")
    if len(images) > 0:
        print(f"📈 Скорость: {len(images)/elapsed:.2f} товаров/сек")
    
    print(f"\n📁 Изображения сохранены в: {LOCAL_STORAGE}")
    print(f"💾 Размер папки: ", end="")
    
    # Подсчитать размер и количество файлов
    all_files = list(LOCAL_STORAGE.rglob("*.jpg"))
    if all_files:
        total_size = sum(f.stat().st_size for f in all_files)
        if total_size > 1024**3:
            print(f"{total_size / 1024**3:.2f} GB")
        else:
            print(f"{total_size / 1024**2:.2f} MB")
        print(f"📊 Всего файлов: {len(all_files)}")
    else:
        print("0 MB")
    
    # Статистика качества
    success_rate = (len(embeddings) / len(images) * 100) if len(images) > 0 else 0
    print(f"\n✨ Успешность обработки: {success_rate:.1f}%")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

