#!/usr/bin/env python3
"""
Скрипт для переиндексации векторов в Qdrant из локальных файлов.

Загружает эмбеддинги батчами чтобы избежать timeout.
"""
import asyncio
import sys
import pickle
from pathlib import Path
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.db.qdrant import QdrantManager


EMBEDDINGS_DIR = Path("/tmp/bakai_products")
BATCH_SIZE = 1000  # Загружать по 1000 векторов за раз


async def load_embeddings_from_disk():
    """Загрузить эмбеддинги с диска."""
    logger.info("📂 Поиск сохраненных эмбеддингов...")
    
    # Ищем pickle файл с эмбеддингами
    pickle_file = EMBEDDINGS_DIR / "embeddings.pkl"
    
    if not pickle_file.exists():
        logger.error(f"❌ Файл не найден: {pickle_file}")
        logger.info("💡 Запустите sync_images_from_s3.py снова")
        return []
    
    logger.info(f"📥 Загрузка из {pickle_file}...")
    
    with open(pickle_file, 'rb') as f:
        embeddings = pickle.load(f)
    
    logger.success(f"✅ Загружено {len(embeddings)} эмбеддингов")
    
    return embeddings


async def index_to_qdrant_batched(embeddings: list):
    """
    Загрузить эмбеддинги в Qdrant батчами.
    
    Args:
        embeddings: Список (product_id, embedding)
    """
    logger.info(f"🔍 Индексация {len(embeddings)} векторов в Qdrant...")
    logger.info(f"   Размер batch: {BATCH_SIZE}")
    
    qdrant = QdrantManager()
    
    total_batches = (len(embeddings) + BATCH_SIZE - 1) // BATCH_SIZE
    successful = 0
    failed = 0
    
    for i in tqdm(range(0, len(embeddings), BATCH_SIZE), desc="Qdrant batches", total=total_batches):
        batch = embeddings[i:i + BATCH_SIZE]
        
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
            logger.error(f"❌ Ошибка загрузки batch {i//BATCH_SIZE + 1}: {e}")
            failed += len(batch)
            continue
    
    logger.success(f"✅ Успешно: {successful}/{len(embeddings)}")
    if failed > 0:
        logger.warning(f"⚠️  Неудачно: {failed}/{len(embeddings)}")


async def main():
    """Основная функция."""
    print("\n" + "=" * 70)
    print("  🔄 ПЕРЕИНДЕКСАЦИЯ QDRANT")
    print("=" * 70)
    
    # Загрузить эмбеддинги
    embeddings = await load_embeddings_from_disk()
    
    if not embeddings:
        print("\n❌ Эмбеддинги не найдены!")
        return
    
    # Загрузить в Qdrant
    await index_to_qdrant_batched(embeddings)
    
    # Проверить результат
    print("\n" + "=" * 70)
    print("📊 ПРОВЕРКА")
    print("=" * 70)
    
    qdrant = QdrantManager()
    count = await qdrant.count_vectors()
    
    print(f"\n✅ Векторов в Qdrant: {count}")
    print(f"✅ Ожидалось: {len(embeddings)}")
    
    if count == len(embeddings):
        print("\n🎉 ВСЕ ВЕКТОРЫ ЗАГРУЖЕНЫ!")
    else:
        print(f"\n⚠️  Загружено {count}/{len(embeddings)} ({count/len(embeddings)*100:.1f}%)")
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, format="<level>{message}</level>", level="INFO")
    
    asyncio.run(main())

