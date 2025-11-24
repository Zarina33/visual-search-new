#!/usr/bin/env python3
"""
Скрипт для синхронизации изображений товаров из BakaiMarket S3.

Загружает изображения, генерирует CLIP эмбеддинги и индексирует в Qdrant.
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from tqdm import tqdm
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.utils.bakai_s3_client import BakaiS3Client
from app.models.clip_model import CLIPEmbedder
from app.db.qdrant import QdrantManager
from app.db import get_session, create_product
from app.config import settings


# Настройки
BUCKET_NAME = "product-images"
STORAGE_PATH = Path("/tmp/bakai_products")  # Временное хранилище
BATCH_SIZE = 32  # Размер batch для CLIP


def extract_product_id(object_key: str) -> str:
    """
    Извлечь ID товара из пути к файлу.
    
    Примеры:
        1/000101141_1.jpg -> 1
        100/970043.jpg -> 100
        1000/1207843254-17.jpg -> 1000
    
    Args:
        object_key: Путь к файлу в S3
        
    Returns:
        ID товара (номер папки)
    """
    parts = object_key.split('/')
    if len(parts) >= 2:
        return parts[0]  # Первая часть - это ID товара
    return "unknown"


def is_main_image(object_key: str) -> bool:
    """
    Проверить является ли изображение главным (первым).
    
    Берем только первое фото каждого товара (_1.jpg или без суффикса).
    
    Args:
        object_key: Путь к файлу в S3
        
    Returns:
        True если это главное изображение
    """
    filename = Path(object_key).stem
    
    # Если есть _1 в конце - это первое фото
    if filename.endswith('_1'):
        return True
    
    # Если нет суффикса _N - тоже берем
    if not any(filename.endswith(f'_{i}') for i in range(2, 10)):
        return True
    
    return False


async def get_all_product_images(
    s3_client: BakaiS3Client,
    max_products: int = None
) -> List[Dict]:
    """
    Получить список всех изображений товаров из S3.
    
    Args:
        s3_client: S3 клиент
        max_products: Максимальное количество товаров (None = все)
        
    Returns:
        Список словарей с информацией об изображениях
    """
    logger.info(f"📦 Получение списка изображений из bucket '{BUCKET_NAME}'...")
    
    all_objects = []
    continuation_token = None
    
    # Получаем все объекты с пагинацией
    while True:
        try:
            if continuation_token:
                response = s3_client.s3_client.list_objects_v2(
                    Bucket=BUCKET_NAME,
                    MaxKeys=1000,
                    ContinuationToken=continuation_token
                )
            else:
                response = s3_client.s3_client.list_objects_v2(
                    Bucket=BUCKET_NAME,
                    MaxKeys=1000
                )
            
            objects = response.get('Contents', [])
            all_objects.extend(objects)
            
            logger.info(f"   Получено: {len(all_objects)} объектов...")
            
            # Проверяем есть ли еще страницы
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
            else:
                break
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения объектов: {e}")
            break
    
    logger.success(f"✅ Всего найдено: {len(all_objects)} изображений")
    
    # Фильтруем - берем только главные изображения
    main_images = []
    products_seen = set()
    
    for obj in all_objects:
        key = obj['Key']
        product_id = extract_product_id(key)
        
        # Берем только первое изображение каждого товара
        if product_id not in products_seen and is_main_image(key):
            main_images.append({
                'product_id': product_id,
                'key': key,
                'size': obj.get('Size', 0),
                'modified': obj.get('LastModified')
            })
            products_seen.add(product_id)
            
            # Ограничение по количеству
            if max_products and len(main_images) >= max_products:
                break
    
    logger.success(f"✅ Отобрано главных изображений: {len(main_images)} (уникальных товаров)")
    
    return main_images


async def download_images(
    s3_client: BakaiS3Client,
    images: List[Dict]
) -> List[Tuple[str, str]]:
    """
    Скачать изображения из S3.
    
    Args:
        s3_client: S3 клиент
        images: Список изображений для скачивания
        
    Returns:
        Список кортежей (product_id, local_path)
    """
    logger.info(f"📥 Скачивание {len(images)} изображений...")
    
    # Создать директорию для хранения
    STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    
    downloaded = []
    
    for img in tqdm(images, desc="Скачивание"):
        product_id = img['product_id']
        key = img['key']
        
        # Локальный путь
        filename = Path(key).name
        local_path = STORAGE_PATH / f"{product_id}_{filename}"
        
        # Скачать
        success = s3_client.download_file(BUCKET_NAME, key, str(local_path))
        
        if success:
            downloaded.append((product_id, str(local_path)))
        else:
            logger.warning(f"⚠️  Не удалось скачать: {key}")
    
    logger.success(f"✅ Скачано: {len(downloaded)}/{len(images)} изображений")
    
    return downloaded


async def generate_embeddings(
    embedder: CLIPEmbedder,
    images: List[Tuple[str, str]]
) -> List[Tuple[str, List[float]]]:
    """
    Генерировать CLIP эмбеддинги для изображений.
    
    Args:
        embedder: CLIP embedder
        images: Список кортежей (product_id, image_path)
        
    Returns:
        Список кортежей (product_id, embedding)
    """
    logger.info(f"🧠 Генерация CLIP эмбеддингов для {len(images)} изображений...")
    
    embeddings = []
    
    # Обработка батчами
    for i in tqdm(range(0, len(images), BATCH_SIZE), desc="CLIP обработка"):
        batch = images[i:i + BATCH_SIZE]
        
        batch_paths = [img[1] for img in batch]
        batch_ids = [img[0] for img in batch]
        
        try:
            # Генерация эмбеддингов батчем
            batch_embeddings = await embedder.generate_embeddings_batch(batch_paths)
            
            # Сохранить результаты
            for product_id, embedding in zip(batch_ids, batch_embeddings):
                if embedding is not None:
                    embeddings.append((product_id, embedding.tolist()))
                else:
                    logger.warning(f"⚠️  Не удалось создать эмбеддинг для товара {product_id}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка обработки batch: {e}")
            continue
    
    logger.success(f"✅ Сгенерировано эмбеддингов: {len(embeddings)}/{len(images)}")
    
    return embeddings


async def save_to_databases(
    embeddings: List[Tuple[str, List[float]]],
    images: List[Tuple[str, str]]
):
    """
    Сохранить данные в PostgreSQL и Qdrant.
    
    Args:
        embeddings: Список (product_id, embedding)
        images: Список (product_id, image_path)
    """
    logger.info(f"💾 Сохранение в базы данных...")
    
    # Создать маппинг product_id -> image_path
    image_map = {pid: path for pid, path in images}
    
    # 1. Сохранить в PostgreSQL
    logger.info("   PostgreSQL...")
    saved_pg = 0
    
    async with get_session() as session:
        for product_id, embedding in tqdm(embeddings, desc="PostgreSQL"):
            try:
                # Генерируем presigned URL для изображения
                s3_client = BakaiS3Client()
                image_key = None
                
                # Найти ключ изображения в S3
                for img in images:
                    if img[0] == product_id:
                        # Извлечь оригинальный ключ из пути
                        filename = Path(img[1]).name
                        # Убрать префикс product_id_
                        original_name = filename[len(product_id) + 1:]
                        image_key = f"{product_id}/{original_name}"
                        break
                
                # Создать presigned URL
                image_url = None
                if image_key:
                    image_url = s3_client.generate_presigned_url(
                        BUCKET_NAME,
                        image_key,
                        expiration=31536000  # 1 год
                    )
                
                # Сохранить в БД
                await create_product(session, {
                    "external_id": f"bakai_{product_id}",
                    "title": f"Product {product_id}",
                    "description": f"BakaiMarket product ID: {product_id}",
                    "category": "bakai",
                    "image_url": image_url or f"s3://{BUCKET_NAME}/{image_key}",
                    "product_metadata": {
                        "source": "bakai_s3",
                        "product_id": product_id,
                        "s3_bucket": BUCKET_NAME,
                        "s3_key": image_key
                    }
                })
                
                saved_pg += 1
                
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения товара {product_id} в PostgreSQL: {e}")
                continue
    
    logger.success(f"✅ PostgreSQL: сохранено {saved_pg}/{len(embeddings)} товаров")
    
    # 2. Сохранить в Qdrant (батчами чтобы избежать timeout)
    logger.info("   Qdrant...")
    
    QDRANT_BATCH_SIZE = 1000  # Загружать по 1000 векторов
    qdrant = QdrantManager()
    
    successful = 0
    failed = 0
    
    total_batches = (len(embeddings) + QDRANT_BATCH_SIZE - 1) // QDRANT_BATCH_SIZE
    
    for i in tqdm(range(0, len(embeddings), QDRANT_BATCH_SIZE), desc="Qdrant", total=total_batches):
        batch = embeddings[i:i + QDRANT_BATCH_SIZE]
        
        try:
            # Подготовить данные для batch
            product_ids = [f"bakai_{pid}" for pid, _ in batch]
            vectors = [emb for _, emb in batch]
            payloads = [
                {
                    "product_id": f"bakai_{pid}",
                    "source": "bakai_s3",
                    "original_id": pid
                }
                for pid, _ in batch
            ]
            
            # Сохранить batch
            await qdrant.upsert_vectors(
                product_ids=product_ids,
                vectors=vectors,
                payloads=payloads
            )
            
            successful += len(batch)
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения batch {i//QDRANT_BATCH_SIZE + 1} в Qdrant: {e}")
            failed += len(batch)
            continue
    
    logger.success(f"✅ Qdrant: сохранено {successful}/{len(embeddings)} векторов")
    if failed > 0:
        logger.warning(f"⚠️  Qdrant: неудачно {failed}/{len(embeddings)} векторов")


async def main(max_products: int = None):
    """
    Основная функция синхронизации.
    
    Args:
        max_products: Максимальное количество товаров (None = все)
    """
    start_time = time.time()
    
    print("\n" + "=" * 70)
    print("  🚀 СИНХРОНИЗАЦИЯ ИЗОБРАЖЕНИЙ ИЗ BAKAI MARKET S3")
    print("=" * 70)
    
    if max_products:
        print(f"\n⚙️  Режим: ТЕСТ (первые {max_products} товаров)")
    else:
        print(f"\n⚙️  Режим: ПОЛНАЯ СИНХРОНИЗАЦИЯ")
    
    # 1. Получить список изображений
    print("\n" + "=" * 70)
    print("📦 ШАГ 1: Получение списка изображений")
    print("=" * 70)
    
    s3_client = BakaiS3Client()
    images = await get_all_product_images(s3_client, max_products)
    
    if not images:
        print("\n❌ Изображения не найдены!")
        return
    
    # 2. Скачать изображения
    print("\n" + "=" * 70)
    print("📥 ШАГ 2: Скачивание изображений")
    print("=" * 70)
    
    downloaded = await download_images(s3_client, images)
    
    if not downloaded:
        print("\n❌ Не удалось скачать изображения!")
        return
    
    # 3. Генерировать эмбеддинги
    print("\n" + "=" * 70)
    print("🧠 ШАГ 3: Генерация CLIP эмбеддингов")
    print("=" * 70)
    
    embedder = CLIPEmbedder()
    embeddings = await generate_embeddings(embedder, downloaded)
    
    if not embeddings:
        print("\n❌ Не удалось создать эмбеддинги!")
        return
    
    # 4. Сохранить в базы данных
    print("\n" + "=" * 70)
    print("💾 ШАГ 4: Сохранение в базы данных")
    print("=" * 70)
    
    await save_to_databases(embeddings, downloaded)
    
    # Итоги
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 70)
    print("📊 ИТОГИ")
    print("=" * 70)
    
    print(f"\n✅ Обработано товаров: {len(embeddings)}")
    print(f"⏱️  Время выполнения: {elapsed:.2f} секунд ({elapsed/60:.2f} минут)")
    print(f"📈 Скорость: {len(embeddings) / elapsed:.2f} товаров/сек")
    
    print("\n💡 Следующие шаги:")
    print("   1. Протестировать поиск: python scripts/test_search_api.py")
    print("   2. Проверить данные в БД")
    print("   3. Запустить API и попробовать поиск по фото")
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Синхронизация изображений из BakaiMarket S3")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Максимальное количество товаров (для теста)"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<level>{message}</level>",
        level="INFO"
    )
    
    asyncio.run(main(max_products=args.limit))

