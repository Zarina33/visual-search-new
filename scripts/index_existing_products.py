#!/usr/bin/env python3
"""
Скрипт для индексации существующих товаров в Qdrant.

Берет товары из PostgreSQL, генерирует эмбеддинги и загружает в Qdrant батчами.
"""
import asyncio
import sys
from pathlib import Path
from tqdm import tqdm
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.db import get_session, get_products
from app.models.clip_model import CLIPEmbedder
from app.db.qdrant import QdrantManager
from app.utils.bakai_s3_client import BakaiS3Client


BATCH_SIZE = 32  # CLIP batch size
QDRANT_BATCH_SIZE = 1000  # Qdrant batch size
STORAGE_PATH = Path("/tmp/bakai_reindex")


async def get_bakai_products():
    """Получить все товары BakaiMarket из PostgreSQL."""
    logger.info("📦 Получение товаров из PostgreSQL...")
    
    all_products = []
    offset = 0
    limit = 1000
    
    while True:
        async with get_session() as session:
            products = await get_products(session, skip=offset, limit=limit)
            
            # Фильтруем только bakai товары
            bakai_products = [p for p in products if p.external_id.startswith('bakai_')]
            
            if not bakai_products:
                break
            
            all_products.extend(bakai_products)
            offset += limit
            
            logger.info(f"   Загружено: {len(all_products)} товаров...")
            
            if len(products) < limit:
                break
    
    logger.success(f"✅ Всего товаров BakaiMarket: {len(all_products)}")
    
    return all_products


async def download_and_generate_embeddings(products: list):
    """
    Скачать изображения и сгенерировать эмбеддинги.
    
    Args:
        products: Список Product объектов
        
    Returns:
        Список (product_id, embedding)
    """
    logger.info(f"🧠 Генерация эмбеддингов для {len(products)} товаров...")
    
    # Создать директорию
    STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    
    s3_client = BakaiS3Client()
    embedder = CLIPEmbedder()
    
    embeddings = []
    failed = 0
    
    # Обработка батчами
    for i in tqdm(range(0, len(products), BATCH_SIZE), desc="CLIP обработка"):
        batch = products[i:i + BATCH_SIZE]
        
        batch_paths = []
        batch_ids = []
        
        # Скачать изображения для batch
        for product in batch:
            try:
                # Извлечь оригинальный ID
                original_id = product.external_id.replace('bakai_', '')
                
                # Извлечь S3 key из metadata
                s3_key = product.product_metadata.get('s3_key')
                
                if not s3_key:
                    logger.warning(f"⚠️  Нет S3 key для {product.external_id}")
                    failed += 1
                    continue
                
                # Локальный путь
                local_path = STORAGE_PATH / f"{product.external_id}.jpg"
                
                # Скачать если еще не скачан
                if not local_path.exists():
                    success = s3_client.download_file(
                        "product-images",
                        s3_key,
                        str(local_path)
                    )
                    
                    if not success:
                        logger.warning(f"⚠️  Не удалось скачать {s3_key}")
                        failed += 1
                        continue
                
                batch_paths.append(str(local_path))
                batch_ids.append(original_id)
                
            except Exception as e:
                logger.error(f"❌ Ошибка подготовки {product.external_id}: {e}")
                failed += 1
                continue
        
        # Генерация эмбеддингов для batch
        if batch_paths:
            try:
                batch_embeddings = await embedder.generate_embeddings_batch(batch_paths)
                
                for product_id, embedding in zip(batch_ids, batch_embeddings):
                    if embedding is not None:
                        embeddings.append((product_id, embedding.tolist()))
                    else:
                        failed += 1
                        
            except Exception as e:
                logger.error(f"❌ Ошибка CLIP batch: {e}")
                failed += len(batch_paths)
    
    logger.success(f"✅ Сгенерировано: {len(embeddings)}/{len(products)}")
    if failed > 0:
        logger.warning(f"⚠️  Неудачно: {failed}/{len(products)}")
    
    return embeddings


async def index_to_qdrant_batched(embeddings: list):
    """
    Загрузить эмбеддинги в Qdrant батчами.
    
    Args:
        embeddings: Список (product_id, embedding)
    """
    logger.info(f"🔍 Индексация {len(embeddings)} векторов в Qdrant...")
    logger.info(f"   Размер batch: {QDRANT_BATCH_SIZE}")
    
    qdrant = QdrantManager()
    
    total_batches = (len(embeddings) + QDRANT_BATCH_SIZE - 1) // QDRANT_BATCH_SIZE
    successful = 0
    failed = 0
    
    for i in tqdm(range(0, len(embeddings), QDRANT_BATCH_SIZE), desc="Qdrant batches", total=total_batches):
        batch = embeddings[i:i + QDRANT_BATCH_SIZE]
        
        try:
            # Подготовить данные
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
            
            # Загрузить batch
            await qdrant.upsert_vectors(
                product_ids=product_ids,
                vectors=vectors,
                payloads=payloads
            )
            
            successful += len(batch)
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки batch {i//QDRANT_BATCH_SIZE + 1}: {e}")
            failed += len(batch)
            continue
    
    logger.success(f"✅ Успешно: {successful}/{len(embeddings)}")
    if failed > 0:
        logger.warning(f"⚠️  Неудачно: {failed}/{len(embeddings)}")


async def main():
    """Основная функция."""
    start_time = time.time()
    
    print("\n" + "=" * 70)
    print("  🔄 ИНДЕКСАЦИЯ СУЩЕСТВУЮЩИХ ТОВАРОВ В QDRANT")
    print("=" * 70)
    
    # 1. Получить товары из PostgreSQL
    print("\n" + "=" * 70)
    print("📦 ШАГ 1: Получение товаров из PostgreSQL")
    print("=" * 70)
    
    products = await get_bakai_products()
    
    if not products:
        print("\n❌ Товары не найдены!")
        return
    
    # 2. Скачать изображения и генерировать эмбеддинги
    print("\n" + "=" * 70)
    print("🧠 ШАГ 2: Генерация CLIP эмбеддингов")
    print("=" * 70)
    
    embeddings = await download_and_generate_embeddings(products)
    
    if not embeddings:
        print("\n❌ Не удалось создать эмбеддинги!")
        return
    
    # 3. Загрузить в Qdrant
    print("\n" + "=" * 70)
    print("🔍 ШАГ 3: Загрузка в Qdrant")
    print("=" * 70)
    
    await index_to_qdrant_batched(embeddings)
    
    # 4. Проверить результат
    print("\n" + "=" * 70)
    print("📊 ПРОВЕРКА")
    print("=" * 70)
    
    qdrant = QdrantManager()
    count = await qdrant.count_vectors()
    
    print(f"\n✅ Векторов в Qdrant: {count}")
    print(f"✅ Ожидалось: {len(embeddings)}")
    
    if count >= len(embeddings):
        print("\n🎉 ВСЕ ВЕКТОРЫ ЗАГРУЖЕНЫ!")
    else:
        print(f"\n⚠️  Загружено {count}/{len(embeddings)} ({count/len(embeddings)*100:.1f}%)")
    
    elapsed = time.time() - start_time
    print(f"\n⏱️  Время: {elapsed:.2f} секунд ({elapsed/60:.2f} минут)")
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, format="<level>{message}</level>", level="INFO")
    
    asyncio.run(main())

