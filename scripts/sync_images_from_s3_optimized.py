#!/usr/bin/env python3
"""
Оптимизированный скрипт для синхронизации изображений товаров из BakaiMarket S3.

Улучшения:
- Валидация качества изображений
- Удаление файлов после обработки (экономия места)
- Проверка на дубликаты
- Лучшая обработка ошибок
- Прогресс-бар с ETA
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from tqdm import tqdm
import time
from PIL import Image
import io

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.utils.bakai_s3_client import BakaiS3Client
from app.models.clip_model import CLIPEmbedder
from app.db.qdrant import QdrantManager
from app.db import get_session, create_product
from app.config import settings
from sqlalchemy import select, text
from app.db.postgres import Product


# Настройки
BUCKET_NAME = "product-images"
STORAGE_PATH = Path("/tmp/bakai_products")
BATCH_SIZE = 32  # Размер batch для CLIP
QDRANT_BATCH_SIZE = 1000  # Размер batch для Qdrant
MIN_IMAGE_SIZE = 50  # Минимальный размер изображения (px)
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # Максимальный размер файла (20MB)
MAX_DIMENSION = 2048  # Максимальное разрешение (автоматически сжимать больше)


def extract_product_id(object_key: str) -> str:
    """Извлечь ID товара из пути к файлу."""
    parts = object_key.split('/')
    if len(parts) >= 2:
        return parts[0]
    return "unknown"


def is_main_image(object_key: str) -> bool:
    """Проверить является ли изображение главным (первым)."""
    filename = Path(object_key).stem
    
    if filename.endswith('_1'):
        return True
    
    if not any(filename.endswith(f'_{i}') for i in range(2, 10)):
        return True
    
    return False


def validate_image(image_data: bytes, product_id: str) -> Optional[Image.Image]:
    """
    Валидировать изображение.
    
    Args:
        image_data: Байты изображения
        product_id: ID товара
        
    Returns:
        PIL Image если валидно, None если нет
    """
    try:
        # Проверка размера файла
        if len(image_data) > MAX_IMAGE_SIZE:
            logger.warning(f"⚠️  Товар {product_id}: файл слишком большой ({len(image_data)} bytes)")
            return None
        
        if len(image_data) < 1000:  # Меньше 1KB - подозрительно
            logger.warning(f"⚠️  Товар {product_id}: файл слишком маленький ({len(image_data)} bytes)")
            return None
        
        # Открыть изображение
        img = Image.open(io.BytesIO(image_data))
        
        # Проверка размеров
        width, height = img.size
        if width < MIN_IMAGE_SIZE or height < MIN_IMAGE_SIZE:
            logger.warning(f"⚠️  Товар {product_id}: изображение слишком маленькое ({width}x{height})")
            return None
        
        # Проверка формата (поддерживаем JPEG, PNG, WEBP)
        if img.format not in ['JPEG', 'JPG', 'PNG', 'WEBP']:
            logger.warning(f"⚠️  Товар {product_id}: неподдерживаемый формат ({img.format})")
            return None
        
        # Сжать если слишком большое (для экономии памяти и ускорения CLIP)
        width, height = img.size
        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            # Пропорциональное уменьшение
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
            logger.info(f"   Товар {product_id}: сжато с {width}x{height} до {img.size[0]}x{img.size[1]}")
        
        # Конвертировать в RGB (для совместимости с JPEG и CLIP)
        # RGBA (PNG с прозрачностью), P (палитра), LA (grayscale + alpha) -> RGB
        if img.mode in ('RGBA', 'LA', 'P', 'PA'):
            # Создать белый фон для прозрачности
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA', 'PA') else None)
            img = rgb_img
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        return img
        
    except Exception as e:
        logger.warning(f"⚠️  Товар {product_id}: ошибка валидации - {e}")
        return None


async def get_existing_products() -> set:
    """Получить список уже загруженных товаров из PostgreSQL."""
    logger.info("🔍 Проверка существующих товаров в БД...")
    
    existing = set()
    
    try:
        async with get_session() as session:
            result = await session.execute(
                select(Product.external_id).where(
                    Product.external_id.like('bakai_%')
                )
            )
            
            for row in result:
                # Извлечь ID из external_id (bakai_123 -> 123)
                external_id = row[0]
                product_id = external_id.replace('bakai_', '')
                existing.add(product_id)
        
        logger.success(f"✅ Найдено существующих товаров: {len(existing)}")
        
    except Exception as e:
        logger.warning(f"⚠️  Ошибка проверки существующих товаров: {e}")
    
    return existing


async def get_all_product_images(
    s3_client: BakaiS3Client,
    max_products: int = None,
    skip_existing: bool = True
) -> List[Dict]:
    """Получить список всех изображений товаров из S3."""
    logger.info(f"📦 Получение списка изображений из bucket '{BUCKET_NAME}'...")
    
    # Получить список уже загруженных товаров
    existing_products = await get_existing_products() if skip_existing else set()
    
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
    skipped = 0
    
    for obj in all_objects:
        key = obj['Key']
        product_id = extract_product_id(key)
        
        # Пропустить если уже есть в БД
        if product_id in existing_products:
            skipped += 1
            continue
        
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
    if skipped > 0:
        logger.info(f"⏭️  Пропущено (уже в БД): {skipped} товаров")
    
    return main_images


async def download_and_validate_images(
    s3_client: BakaiS3Client,
    images: List[Dict]
) -> List[Tuple[str, str]]:
    """
    Скачать и валидировать изображения из S3.
    
    Returns:
        Список кортежей (product_id, local_path) только для валидных изображений
    """
    logger.info(f"📥 Скачивание и валидация {len(images)} изображений...")
    
    STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    
    downloaded = []
    invalid = 0
    
    for img in tqdm(images, desc="Скачивание"):
        product_id = img['product_id']
        key = img['key']
        
        try:
            # Скачать в память
            response = s3_client.s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
            image_data = response['Body'].read()
            
            # Валидировать
            validated_img = validate_image(image_data, product_id)
            
            if validated_img is None:
                invalid += 1
                continue
            
            # Сохранить локально (всегда как JPEG для единообразия)
            filename = Path(key).stem  # Без расширения
            local_path = STORAGE_PATH / f"{product_id}_{filename}.jpg"
            
            # Сохранить как JPEG
            validated_img.save(local_path, 'JPEG', quality=95)
            
            downloaded.append((product_id, str(local_path)))
            
        except Exception as e:
            logger.warning(f"⚠️  Ошибка загрузки {key}: {e}")
            invalid += 1
            continue
    
    logger.success(f"✅ Скачано и валидировано: {len(downloaded)}/{len(images)} изображений")
    if invalid > 0:
        logger.warning(f"⚠️  Невалидных изображений: {invalid}")
    
    return downloaded


async def generate_embeddings_with_cleanup(
    embedder: CLIPEmbedder,
    images: List[Tuple[str, str]]
) -> List[Tuple[str, List[float]]]:
    """
    Генерировать CLIP эмбеддинги и удалять файлы после обработки.
    
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
            for product_id, embedding, img_path in zip(batch_ids, batch_embeddings, batch_paths):
                if embedding is not None:
                    embeddings.append((product_id, embedding.tolist()))
                else:
                    logger.warning(f"⚠️  Не удалось создать эмбеддинг для товара {product_id}")
                
                # Удалить файл после обработки (экономия места)
                try:
                    Path(img_path).unlink()
                except Exception as e:
                    logger.warning(f"⚠️  Не удалось удалить {img_path}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка обработки batch: {e}")
            continue
    
    logger.success(f"✅ Сгенерировано эмбеддингов: {len(embeddings)}/{len(images)}")
    
    return embeddings


async def save_to_databases(
    embeddings: List[Tuple[str, List[float]]],
    images: List[Tuple[str, str]]
):
    """Сохранить данные в PostgreSQL и Qdrant."""
    logger.info(f"💾 Сохранение в базы данных...")
    
    # Создать маппинг product_id -> image info
    image_map = {}
    for img in images:
        product_id = img[0]
        image_path = img[1]
        filename = Path(image_path).name
        original_name = filename[len(product_id) + 1:]
        image_key = f"{product_id}/{original_name}"
        
        image_map[product_id] = {
            'path': image_path,
            'key': image_key
        }
    
    # 1. Сохранить в PostgreSQL
    logger.info("   PostgreSQL...")
    saved_pg = 0
    s3_client = BakaiS3Client()
    
    async with get_session() as session:
        for product_id, embedding in tqdm(embeddings, desc="PostgreSQL"):
            try:
                # Получить информацию об изображении
                img_info = image_map.get(product_id)
                if not img_info:
                    continue
                
                # Создать presigned URL
                image_url = s3_client.generate_presigned_url(
                    BUCKET_NAME,
                    img_info['key'],
                    expiration=31536000  # 1 год
                )
                
                # Сохранить в БД
                await create_product(session, {
                    "external_id": f"bakai_{product_id}",
                    "title": f"Product {product_id}",
                    "description": f"BakaiMarket product ID: {product_id}",
                    "category": "bakai",
                    "image_url": image_url or f"s3://{BUCKET_NAME}/{img_info['key']}",
                    "product_metadata": {
                        "source": "bakai_s3",
                        "product_id": product_id,
                        "s3_bucket": BUCKET_NAME,
                        "s3_key": img_info['key']
                    }
                })
                
                saved_pg += 1
                
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения товара {product_id} в PostgreSQL: {e}")
                continue
    
    logger.success(f"✅ PostgreSQL: сохранено {saved_pg}/{len(embeddings)} товаров")
    
    # 2. Сохранить в Qdrant (батчами)
    logger.info("   Qdrant...")
    
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


async def main(max_products: int = None, skip_existing: bool = True):
    """
    Основная функция синхронизации.
    
    Args:
        max_products: Максимальное количество товаров (None = все)
        skip_existing: Пропускать уже загруженные товары
    """
    start_time = time.time()
    
    print("\n" + "=" * 70)
    print("  🚀 ОПТИМИЗИРОВАННАЯ СИНХРОНИЗАЦИЯ ИЗОБРАЖЕНИЙ")
    print("=" * 70)
    
    if max_products:
        print(f"\n⚙️  Режим: ТЕСТ (первые {max_products} товаров)")
    else:
        print(f"\n⚙️  Режим: ПОЛНАЯ СИНХРОНИЗАЦИЯ (все товары)")
    
    print(f"⚙️  Пропуск существующих: {'ДА' if skip_existing else 'НЕТ'}")
    
    # 1. Получить список изображений
    print("\n" + "=" * 70)
    print("📦 ШАГ 1: Получение списка изображений")
    print("=" * 70)
    
    s3_client = BakaiS3Client()
    images = await get_all_product_images(s3_client, max_products, skip_existing)
    
    if not images:
        print("\n✅ Нет новых изображений для загрузки!")
        return
    
    # 2. Скачать и валидировать изображения
    print("\n" + "=" * 70)
    print("📥 ШАГ 2: Скачивание и валидация изображений")
    print("=" * 70)
    
    downloaded = await download_and_validate_images(s3_client, images)
    
    if not downloaded:
        print("\n❌ Не удалось скачать валидные изображения!")
        return
    
    # 3. Генерировать эмбеддинги (с удалением файлов)
    print("\n" + "=" * 70)
    print("🧠 ШАГ 3: Генерация CLIP эмбеддингов")
    print("=" * 70)
    
    embedder = CLIPEmbedder()
    embeddings = await generate_embeddings_with_cleanup(embedder, downloaded)
    
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
    
    if elapsed > 0:
        print(f"📈 Скорость: {len(embeddings) / elapsed:.2f} товаров/сек")
        
        # Оценка времени для всех товаров
        if max_products and max_products < 85337:
            estimated_total = (85337 / len(embeddings)) * elapsed
            print(f"⏱️  Оценка для всех 85,337 товаров: {estimated_total/3600:.2f} часов")
    
    print("\n💡 Следующие шаги:")
    print("   1. Протестировать поиск: python scripts/test_visual_search.py")
    print("   2. Проверить данные в БД")
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Оптимизированная синхронизация изображений из BakaiMarket S3")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Максимальное количество товаров (для теста)"
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Не пропускать существующие товары (загрузить заново)"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<level>{message}</level>",
        level="INFO"
    )
    
    asyncio.run(main(
        max_products=args.limit,
        skip_existing=not args.no_skip_existing
    ))

