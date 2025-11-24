#!/usr/bin/env python3
"""
Быстрая индексация в Qdrant из уже скачанных изображений.

Использует изображения из /tmp/bakai_products для генерации эмбеддингов.
"""
import asyncio
import sys
from pathlib import Path
from tqdm import tqdm
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.models.clip_model import CLIPEmbedder
from app.db.qdrant import QdrantManager


STORAGE_PATH = Path("/tmp/bakai_products")
CLIP_BATCH_SIZE = 32
QDRANT_BATCH_SIZE = 1000


async def get_downloaded_images():
    """Получить список скачанных изображений."""
    logger.info(f"📂 Поиск изображений в {STORAGE_PATH}...")
    
    if not STORAGE_PATH.exists():
        logger.error(f"❌ Директория не найдена: {STORAGE_PATH}")
        return []
    
    # Найти все jpg файлы
    images = list(STORAGE_PATH.glob("*.jpg"))
    images.extend(STORAGE_PATH.glob("*.jpeg"))
    images.extend(STORAGE_PATH.glob("*.png"))
    
    logger.success(f"✅ Найдено {len(images)} изображений")
    
    # Извлечь product_id из имени файла
    result = []
    for img_path in images:
        # Имя файла: {product_id}_{filename}.jpg
        filename = img_path.stem
        parts = filename.split('_', 1)
        if len(parts) >= 1:
            product_id = parts[0]
            result.append((product_id, str(img_path)))
    
    logger.info(f"📊 Обработано {len(result)} изображений")
    
    return result


async def generate_embeddings(images: list):
    """
    Генерировать CLIP эмбеддинги.
    
    Args:
        images: Список (product_id, image_path)
        
    Returns:
        Список (product_id, embedding)
    """
    logger.info(f"🧠 Генерация CLIP эмбеддингов для {len(images)} изображений...")
    
    embedder = CLIPEmbedder()
    embeddings = []
    
    # Обработка батчами
    for i in tqdm(range(0, len(images), CLIP_BATCH_SIZE), desc="CLIP обработка"):
        batch = images[i:i + CLIP_BATCH_SIZE]
        
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


async def index_to_qdrant(embeddings: list):
    """
    Загрузить эмбеддинги в Qdrant батчами.
    
    Args:
        embeddings: Список (product_id, embedding)
    """
    logger.info(f"🔍 Индексация {len(embeddings)} векторов в Qdrant...")
    logger.info(f"   Размер batch: {QDRANT_BATCH_SIZE}")
    
    qdrant = QdrantManager()
    
    successful = 0
    failed = 0
    
    total_batches = (len(embeddings) + QDRANT_BATCH_SIZE - 1) // QDRANT_BATCH_SIZE
    
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
    print("  ⚡ БЫСТРАЯ ИНДЕКСАЦИЯ В QDRANT")
    print("=" * 70)
    
    # 1. Получить список изображений
    print("\n" + "=" * 70)
    print("📂 ШАГ 1: Поиск скачанных изображений")
    print("=" * 70)
    
    images = await get_downloaded_images()
    
    if not images:
        print("\n❌ Изображения не найдены!")
        print(f"   Проверьте директорию: {STORAGE_PATH}")
        return
    
    # 2. Генерировать эмбеддинги
    print("\n" + "=" * 70)
    print("🧠 ШАГ 2: Генерация CLIP эмбеддингов")
    print("=" * 70)
    
    embeddings = await generate_embeddings(images)
    
    if not embeddings:
        print("\n❌ Не удалось создать эмбеддинги!")
        return
    
    # 3. Загрузить в Qdrant
    print("\n" + "=" * 70)
    print("🔍 ШАГ 3: Загрузка в Qdrant")
    print("=" * 70)
    
    await index_to_qdrant(embeddings)
    
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
    print(f"📈 Скорость: {len(embeddings) / elapsed:.2f} товаров/сек")
    
    print("\n💡 Следующие шаги:")
    print("   1. Протестировать поиск: python scripts/test_search_api.py")
    print("   2. Запустить API и попробовать поиск по фото")
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, format="<level>{message}</level>", level="INFO")
    
    asyncio.run(main())

