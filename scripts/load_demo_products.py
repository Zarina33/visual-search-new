"""
Скрипт для загрузки демо товаров в систему визуального поиска.

Сканирует директорию с изображениями, генерирует эмбеддинги через CLIP,
создаёт записи в PostgreSQL и добавляет векторы в Qdrant.
"""
import asyncio
import os
import time
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import random
from collections import defaultdict

from tqdm.asyncio import tqdm as async_tqdm
from tqdm import tqdm
from loguru import logger

from app.models.clip_model import CLIPEmbedder
from app.db.postgres import get_session, create_product, init_db
from app.db.qdrant import QdrantManager
from app.config import settings


# Словарь для определения категорий по ключевым словам
CATEGORY_KEYWORDS = {
    "furniture": ["sofa", "table", "chair", "desk", "bed", "cabinet", "shelf"],
    "vehicles": ["car", "auto", "vehicle", "truck", "bike", "motorcycle"],
    "electronics": ["phone", "laptop", "computer", "tablet", "tv", "monitor", "camera"],
    "clothing": ["dress", "shirt", "pants", "jacket", "shoes", "hat", "coat"],
    "appliances": ["fridge", "refrigerator", "washer", "dryer", "oven", "microwave"],
}


async def scan_images(directory: str) -> List[Path]:
    """
    Сканировать директорию и найти все изображения.
    
    Args:
        directory: Путь к директории с изображениями
        
    Returns:
        Список Path объектов для всех найденных изображений
    """
    logger.info(f"Сканирование директории: {directory}")
    
    # Поддерживаемые форматы
    supported_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    
    image_paths = []
    directory_path = Path(directory)
    
    if not directory_path.exists():
        logger.error(f"Директория не существует: {directory}")
        return []
    
    # Рекурсивный поиск всех изображений
    for ext in supported_extensions:
        image_paths.extend(directory_path.rglob(f"*{ext}"))
        image_paths.extend(directory_path.rglob(f"*{ext.upper()}"))
    
    logger.info(f"Найдено изображений: {len(image_paths)}")
    return sorted(image_paths)


def determine_category(image_path: Path) -> str:
    """
    Определить категорию товара из пути к файлу.
    
    Args:
        image_path: Путь к изображению
        
    Returns:
        Название категории
    """
    # Получаем имя файла и родительскую директорию
    filename = image_path.stem.lower()
    parent_dir = image_path.parent.name.lower()
    
    # Проверяем ключевые слова в имени файла и директории
    text_to_check = f"{filename} {parent_dir}"
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_to_check:
                return category
    
    return "other"


def generate_product_data(image_path: Path) -> dict:
    """
    Сгенерировать данные продукта из пути к файлу.
    
    Args:
        image_path: Путь к изображению
        
    Returns:
        Словарь с данными продукта
    """
    # external_id из имени файла
    filename = image_path.stem
    external_id = f"prod_{filename}_{random.randint(1000, 9999)}"
    
    # title из имени файла (красиво отформатировать)
    # Убираем цифры в конце, заменяем _ на пробелы, capitalize
    title_parts = filename.replace("_", " ").replace("-", " ").split()
    # Убираем числа в конце
    title_parts = [part for part in title_parts if not part.isdigit()]
    title = " ".join(part.capitalize() for part in title_parts)
    
    # Если title пустой, используем имя файла
    if not title:
        title = filename.capitalize()
    
    # category из названия папки или из имени файла
    category = determine_category(image_path)
    
    # Случайная цена в зависимости от категории
    price_ranges = {
        "furniture": (5000, 50000),
        "vehicles": (100000, 500000),
        "electronics": (10000, 100000),
        "clothing": (1000, 10000),
        "appliances": (15000, 80000),
        "other": (1000, 20000),
    }
    
    min_price, max_price = price_ranges.get(category, (1000, 20000))
    price = random.randint(min_price, max_price)
    
    return {
        "external_id": external_id,
        "title": title,
        "description": f"Demo product: {title}",
        "category": category,
        "price": price,
        "currency": "KGS",
        "image_url": f"file://{image_path.absolute()}",
        "product_metadata": {
            "source": "demo",
            "original_filename": image_path.name,
            "parent_directory": image_path.parent.name,
        }
    }


async def process_image(
    image_path: Path,
    clip_embedder: CLIPEmbedder,
    qdrant_manager: QdrantManager
) -> Tuple[bool, str, Optional[str]]:
    """
    Обработать одно изображение.
    
    Args:
        image_path: Путь к изображению
        clip_embedder: CLIP embedder для генерации векторов
        qdrant_manager: Менеджер Qdrant для хранения векторов
        
    Returns:
        (success: bool, message: str, category: Optional[str])
    """
    try:
        # 1. Генерация эмбеддинга
        logger.debug(f"Обработка: {image_path.name}")
        
        embedding = await clip_embedder.generate_embedding(str(image_path))
        
        if embedding is None:
            return False, f"Не удалось сгенерировать эмбеддинг для {image_path.name}", None
        
        # 2. Создание продукта в PostgreSQL
        product_data = generate_product_data(image_path)
        category = product_data["category"]
        
        async with get_session() as session:
            product = await create_product(session, product_data)
            
            if product is None:
                return False, f"Не удалось создать продукт для {image_path.name}", category
            
            # 3. Добавление вектора в Qdrant
            success = await qdrant_manager.upsert_vectors(
                product_ids=[product.external_id],
                vectors=[embedding.tolist()],
                payloads=[{
                    "product_id": product.external_id,
                    "title": product.title,
                    "category": product.category,
                    "price": float(product.price),
                    "image_url": product.image_url,
                }]
            )
            
            if not success:
                return False, f"Не удалось добавить вектор для {image_path.name}", category
        
        return True, f"✅ {product.title}", category
        
    except FileNotFoundError as e:
        logger.warning(f"Файл не найден: {image_path}")
        return False, f"❌ Файл не найден: {image_path.name}", None
        
    except Exception as e:
        logger.error(f"Ошибка при обработке {image_path.name}: {e}")
        return False, f"❌ Ошибка: {image_path.name} - {str(e)[:50]}", None


async def load_demo_products(images_dir: str):
    """
    Главная функция загрузки демо товаров.
    
    Args:
        images_dir: Путь к директории с изображениями
    """
    print("\n" + "=" * 70)
    print("  🚀 ЗАГРУЗКА ДЕМО ТОВАРОВ В СИСТЕМУ ВИЗУАЛЬНОГО ПОИСКА")
    print("=" * 70 + "\n")
    
    start_time = time.time()
    
    # 1. Инициализация компонентов
    print("📦 Инициализация компонентов...")
    
    try:
        # Инициализация БД
        await init_db()
        logger.info("PostgreSQL инициализирована")
        
        # CLIP embedder
        clip_embedder = CLIPEmbedder(device="auto")
        logger.info(f"CLIP embedder готов (device={clip_embedder.device})")
        
        # Qdrant
        qdrant_manager = QdrantManager(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            collection_name=settings.qdrant_collection_name
        )
        
        # Создание коллекции если не существует
        if not await qdrant_manager.collection_exists():
            await qdrant_manager.create_collection(
                vector_size=clip_embedder.get_embedding_dimension(),
                distance="Cosine"
            )
            logger.info("Qdrant коллекция создана")
        else:
            logger.info("Qdrant коллекция уже существует")
        
        print("✅ Все компоненты готовы\n")
        
    except Exception as e:
        logger.error(f"Ошибка инициализации: {e}")
        print(f"❌ Ошибка инициализации: {e}")
        return
    
    # 2. Сканирование изображений
    print(f"🔍 Сканирование директории: {images_dir}")
    image_paths = await scan_images(images_dir)
    
    if not image_paths:
        print("❌ Изображения не найдены!")
        return
    
    print(f"✅ Найдено изображений: {len(image_paths)}\n")
    
    # 3. Обработка каждого изображения
    print("⚙️  Обработка изображений...\n")
    
    successful = 0
    failed = 0
    categories_count: Dict[str, int] = defaultdict(int)
    
    # Progress bar
    with tqdm(total=len(image_paths), desc="Обработка", unit="img") as pbar:
        for image_path in image_paths:
            success, message, category = await process_image(
                image_path,
                clip_embedder,
                qdrant_manager
            )
            
            if success:
                successful += 1
                if category:
                    categories_count[category] += 1
            else:
                failed += 1
                logger.error(message)
            
            pbar.update(1)
            pbar.set_postfix({
                "✅": successful,
                "❌": failed
            })
    
    # 4. Итоговый отчёт
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 70)
    print("  📊 ИТОГОВЫЙ ОТЧЁТ")
    print("=" * 70)
    print(f"\n📸 Всего изображений:        {len(image_paths)}")
    print(f"✅ Успешно загружено:        {successful}")
    print(f"❌ Ошибок:                   {failed}")
    print(f"⏱️  Время обработки:          {elapsed_time:.2f} сек")
    
    if successful > 0:
        speed = successful / elapsed_time
        print(f"🚀 Средняя скорость:         {speed:.2f} изображений/сек")
    
    # Статистика по категориям
    if categories_count:
        print(f"\n📦 Категории товаров:")
        for category, count in sorted(categories_count.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {category.capitalize():<15} {count} товаров")
    
    # Информация о коллекции
    try:
        collection_info = await qdrant_manager.get_collection_info()
        print(f"\n💾 Qdrant коллекция:")
        print(f"   • Название:              {collection_info['name']}")
        print(f"   • Векторов:              {collection_info['points_count']}")
        print(f"   • Размерность:           {collection_info['vector_size']}")
        print(f"   • Distance:              {collection_info['distance']}")
    except Exception as e:
        logger.warning(f"Не удалось получить информацию о коллекции: {e}")
    
    print("\n" + "=" * 70)
    
    if successful > 0:
        print("✅ Загрузка завершена успешно!")
    else:
        print("❌ Не удалось загрузить ни одного товара")
    
    print("=" * 70 + "\n")


async def main():
    """Точка входа."""
    # Путь к изображениям
    images_directory = "/home/user/Desktop/BakaiMarket/clip/images"
    
    # Настройка логирования
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Запуск загрузки
    await load_demo_products(images_directory)


if __name__ == "__main__":
    asyncio.run(main())

