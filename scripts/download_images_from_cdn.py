#!/usr/bin/env python3
"""
Скрипт для массовой загрузки изображений товаров из BakaiMarket CDN.

Функции:
- Загрузка всех изображений из CDN для локального использования
- Проверка и валидация изображений
- Структурированное хранение по категориям
- Возможность возобновления прерванной загрузки
- Детальная статистика и прогресс
"""
import asyncio
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from tqdm import tqdm
import time
from PIL import Image
import io
import httpx
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.db.postgres import get_session, Product
from app.utils.bakai_cdn_client import BakaiCDNClient
from app.config import settings
from sqlalchemy import select, func


# Настройки
DEFAULT_STORAGE_PATH = Path("/home/zarina/Work/bektemir_comp/BakaiMarket/bakai_cdn_images")
BATCH_SIZE = 10  # Количество параллельных загрузок
MIN_IMAGE_SIZE = 50  # Минимальный размер изображения (px)
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # Максимальный размер файла (20MB)
DOWNLOAD_TIMEOUT = 30  # Таймаут загрузки (секунды)
CHECKPOINT_INTERVAL = 100  # Сохранять прогресс каждые N товаров


class DownloadStats:
    """Статистика загрузки."""
    
    def __init__(self):
        self.total = 0
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.invalid = 0
        self.start_time = time.time()
    
    def add_downloaded(self):
        self.downloaded += 1
    
    def add_skipped(self):
        self.skipped += 1
    
    def add_failed(self):
        self.failed += 1
    
    def add_invalid(self):
        self.invalid += 1
    
    def get_elapsed(self) -> float:
        return time.time() - self.start_time
    
    def get_speed(self) -> float:
        elapsed = self.get_elapsed()
        if elapsed > 0:
            return self.downloaded / elapsed
        return 0.0
    
    def get_eta(self, remaining: int) -> float:
        speed = self.get_speed()
        if speed > 0:
            return remaining / speed
        return 0.0
    
    def print_summary(self):
        elapsed = self.get_elapsed()
        print("\n" + "=" * 70)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 70)
        print(f"\n✅ Успешно загружено: {self.downloaded}/{self.total}")
        print(f"⏭️  Пропущено (уже есть): {self.skipped}")
        print(f"❌ Ошибки загрузки: {self.failed}")
        print(f"⚠️  Невалидные изображения: {self.invalid}")
        print(f"\n⏱️  Время выполнения: {elapsed:.2f} сек ({elapsed/60:.2f} мин)")
        if elapsed > 0:
            print(f"📈 Скорость: {self.get_speed():.2f} изображений/сек")
        print("=" * 70)


def validate_image(image_data: bytes, product_id: str) -> Optional[Image.Image]:
    """
    Валидация изображения.
    
    Args:
        image_data: Байты изображения
        product_id: ID товара
        
    Returns:
        PIL Image если валидно, None если нет
    """
    try:
        # Проверка размера файла
        if len(image_data) > MAX_IMAGE_SIZE:
            logger.warning(f"⚠️  {product_id}: файл слишком большой ({len(image_data)} bytes)")
            return None
        
        if len(image_data) < 1000:  # Меньше 1KB - подозрительно
            logger.warning(f"⚠️  {product_id}: файл слишком маленький ({len(image_data)} bytes)")
            return None
        
        # Открыть изображение
        img = Image.open(io.BytesIO(image_data))
        
        # Проверка размеров
        width, height = img.size
        if width < MIN_IMAGE_SIZE or height < MIN_IMAGE_SIZE:
            logger.warning(f"⚠️  {product_id}: изображение слишком маленькое ({width}x{height})")
            return None
        
        # Проверка формата
        if img.format not in ['JPEG', 'JPG', 'PNG', 'WEBP']:
            logger.warning(f"⚠️  {product_id}: неподдерживаемый формат ({img.format})")
            return None
        
        # Конвертировать в RGB если нужно
        if img.mode in ('RGBA', 'LA', 'P', 'PA'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA', 'PA') else None)
            img = rgb_img
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        return img
        
    except Exception as e:
        logger.warning(f"⚠️  {product_id}: ошибка валидации - {e}")
        return None


async def download_image(
    client: httpx.AsyncClient,
    image_url: str,
    product_id: str,
    cdn_client: BakaiCDNClient
) -> Optional[bytes]:
    """
    Скачать изображение по URL.
    
    Args:
        client: HTTP клиент
        image_url: URL изображения
        product_id: ID товара
        cdn_client: CDN клиент для аутентификации
        
    Returns:
        Байты изображения или None при ошибке
    """
    try:
        # Если URL относительный, добавить базовый URL
        if not image_url.startswith("http"):
            image_url = f"{cdn_client.api_url}{image_url}"
        
        response = await client.get(
            image_url,
            headers=cdn_client.headers,
            timeout=DOWNLOAD_TIMEOUT,
            follow_redirects=True
        )
        response.raise_for_status()
        
        return response.content
        
    except httpx.TimeoutException:
        logger.warning(f"⚠️  {product_id}: таймаут загрузки")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"⚠️  {product_id}: HTTP ошибка {e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"⚠️  {product_id}: ошибка загрузки - {e}")
        return None


async def get_products_from_db(
    skip_existing: bool = True,
    storage_path: Path = DEFAULT_STORAGE_PATH,
    category_filter: Optional[str] = None
) -> List[Dict]:
    """
    Получить список товаров из базы данных.
    
    Args:
        skip_existing: Пропускать уже загруженные изображения
        storage_path: Путь к хранилищу
        category_filter: Фильтр по категории
        
    Returns:
        Список словарей с данными товаров
    """
    logger.info("📦 Получение списка товаров из базы данных...")
    
    products = []
    
    async with get_session() as session:
        # Построить запрос
        stmt = select(Product).order_by(Product.id)
        
        if category_filter:
            stmt = stmt.where(Product.category == category_filter)
        
        result = await session.execute(stmt)
        db_products = result.scalars().all()
        
        for product in db_products:
            # Пропустить если нет URL изображения
            if not product.image_url:
                continue
            
            # Определить путь сохранения
            category = product.category or "uncategorized"
            category_dir = storage_path / category
            
            # Получить расширение из URL или использовать .jpg по умолчанию
            ext = ".jpg"
            if product.image_url:
                parsed = urlparse(product.image_url)
                path_ext = Path(parsed.path).suffix
                if path_ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    ext = path_ext
            
            filename = f"{product.external_id}{ext}"
            file_path = category_dir / filename
            
            # Пропустить если уже загружено
            if skip_existing and file_path.exists():
                continue
            
            products.append({
                'id': product.id,
                'external_id': product.external_id,
                'title': product.title,
                'category': category,
                'image_url': product.image_url,
                'file_path': file_path
            })
    
    logger.success(f"✅ Найдено товаров для загрузки: {len(products)}")
    
    return products


async def download_images_batch(
    products: List[Dict],
    cdn_client: BakaiCDNClient,
    stats: DownloadStats,
    progress_bar: tqdm
) -> None:
    """
    Скачать пакет изображений параллельно.
    
    Args:
        products: Список товаров для загрузки
        cdn_client: CDN клиент
        stats: Объект статистики
        progress_bar: Прогресс-бар
    """
    async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
        tasks = []
        
        for product in products:
            task = download_and_save_image(
                client=client,
                product=product,
                cdn_client=cdn_client,
                stats=stats,
                progress_bar=progress_bar
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)


async def download_and_save_image(
    client: httpx.AsyncClient,
    product: Dict,
    cdn_client: BakaiCDNClient,
    stats: DownloadStats,
    progress_bar: tqdm
) -> bool:
    """
    Скачать и сохранить одно изображение.
    
    Args:
        client: HTTP клиент
        product: Данные товара
        cdn_client: CDN клиент
        stats: Объект статистики
        progress_bar: Прогресс-бар
        
    Returns:
        True если успешно, False иначе
    """
    external_id = product['external_id']
    file_path = product['file_path']
    
    try:
        # Создать директорию если не существует
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Скачать изображение
        image_data = await download_image(
            client=client,
            image_url=product['image_url'],
            product_id=external_id,
            cdn_client=cdn_client
        )
        
        if image_data is None:
            stats.add_failed()
            progress_bar.update(1)
            return False
        
        # Валидировать изображение
        validated_img = validate_image(image_data, external_id)
        
        if validated_img is None:
            stats.add_invalid()
            progress_bar.update(1)
            return False
        
        # Сохранить как JPEG для единообразия
        validated_img.save(file_path, 'JPEG', quality=95)
        
        stats.add_downloaded()
        progress_bar.update(1)
        progress_bar.set_postfix({
            'downloaded': stats.downloaded,
            'failed': stats.failed,
            'speed': f"{stats.get_speed():.1f}/s"
        })
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения {external_id}: {e}")
        stats.add_failed()
        progress_bar.update(1)
        return False


async def save_checkpoint(
    storage_path: Path,
    downloaded: List[str],
    failed: List[str]
) -> None:
    """
    Сохранить контрольную точку (checkpoint).
    
    Args:
        storage_path: Путь к хранилищу
        downloaded: Список успешно загруженных ID
        failed: Список неудачных ID
    """
    checkpoint_file = storage_path / ".download_checkpoint.json"
    
    checkpoint_data = {
        'timestamp': time.time(),
        'downloaded': downloaded,
        'failed': failed
    }
    
    try:
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        logger.debug(f"💾 Checkpoint сохранен: {len(downloaded)} загружено")
    except Exception as e:
        logger.warning(f"⚠️  Не удалось сохранить checkpoint: {e}")


async def load_checkpoint(storage_path: Path) -> Tuple[List[str], List[str]]:
    """
    Загрузить контрольную точку (checkpoint).
    
    Args:
        storage_path: Путь к хранилищу
        
    Returns:
        Кортеж (downloaded, failed)
    """
    checkpoint_file = storage_path / ".download_checkpoint.json"
    
    if not checkpoint_file.exists():
        return [], []
    
    try:
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
        
        downloaded = checkpoint_data.get('downloaded', [])
        failed = checkpoint_data.get('failed', [])
        
        logger.info(f"📥 Загружен checkpoint: {len(downloaded)} ранее загружено, {len(failed)} неудачных")
        return downloaded, failed
        
    except Exception as e:
        logger.warning(f"⚠️  Не удалось загрузить checkpoint: {e}")
        return [], []


async def main(
    storage_path: Path = DEFAULT_STORAGE_PATH,
    skip_existing: bool = True,
    category_filter: Optional[str] = None,
    limit: Optional[int] = None
):
    """
    Основная функция загрузки изображений.
    
    Args:
        storage_path: Путь для сохранения изображений
        skip_existing: Пропускать уже загруженные
        category_filter: Фильтр по категории
        limit: Ограничение количества (для теста)
    """
    start_time = time.time()
    
    print("\n" + "=" * 70)
    print("  📥 ЗАГРУЗКА ИЗОБРАЖЕНИЙ ИЗ BAKAI CDN")
    print("=" * 70)
    
    print(f"\n⚙️  Настройки:")
    print(f"   Путь сохранения: {storage_path}")
    print(f"   Пропуск существующих: {'ДА' if skip_existing else 'НЕТ'}")
    print(f"   Категория: {category_filter or 'ВСЕ'}")
    print(f"   Ограничение: {limit or 'НЕТ'}")
    print(f"   Параллельных загрузок: {BATCH_SIZE}")
    
    # Создать директорию
    storage_path.mkdir(parents=True, exist_ok=True)
    
    # Инициализировать CDN клиент
    cdn_client = BakaiCDNClient()
    
    # Проверить подключение
    print("\n🔍 Проверка подключения к CDN...")
    if not await cdn_client.test_connection():
        print("\n❌ Не удалось подключиться к CDN API!")
        return
    
    print("✅ Подключение установлено")
    
    # Получить список товаров
    print("\n" + "=" * 70)
    print("📦 ШАГ 1: Получение списка товаров")
    print("=" * 70)
    
    products = await get_products_from_db(
        skip_existing=skip_existing,
        storage_path=storage_path,
        category_filter=category_filter
    )
    
    if not products:
        print("\n✅ Все изображения уже загружены!")
        return
    
    # Применить лимит
    if limit and limit < len(products):
        products = products[:limit]
        print(f"⚙️  Применено ограничение: {limit} товаров")
    
    # Инициализировать статистику
    stats = DownloadStats()
    stats.total = len(products)
    
    # Загрузить checkpoint
    downloaded_ids, failed_ids = await load_checkpoint(storage_path)
    
    # Загрузка изображений
    print("\n" + "=" * 70)
    print(f"📥 ШАГ 2: Загрузка {len(products)} изображений")
    print("=" * 70)
    
    downloaded = list(downloaded_ids)
    failed = list(failed_ids)
    
    with tqdm(total=len(products), desc="Загрузка", unit="img") as progress_bar:
        # Обрабатывать батчами
        for i in range(0, len(products), BATCH_SIZE):
            batch = products[i:i + BATCH_SIZE]
            
            await download_images_batch(
                products=batch,
                cdn_client=cdn_client,
                stats=stats,
                progress_bar=progress_bar
            )
            
            # Сохранить checkpoint периодически
            if (i // BATCH_SIZE) % (CHECKPOINT_INTERVAL // BATCH_SIZE) == 0:
                await save_checkpoint(storage_path, downloaded, failed)
    
    # Сохранить финальный checkpoint
    await save_checkpoint(storage_path, downloaded, failed)
    
    # Показать итоги
    stats.print_summary()
    
    # Показать статистику по категориям
    print("\n📊 Статистика по категориям:")
    categories = {}
    for product in products:
        cat = product['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        cat_dir = storage_path / cat
        actual_count = len(list(cat_dir.glob("*.jpg"))) if cat_dir.exists() else 0
        print(f"   {cat}: {actual_count}/{count} изображений")
    
    print("\n💡 Следующие шаги:")
    print(f"   1. Изображения сохранены в: {storage_path}")
    print(f"   2. Используйте их для локальной обработки/тестирования")
    print(f"   3. Для повторной загрузки неудачных используйте --retry")
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Массовая загрузка изображений товаров из BakaiMarket CDN"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_STORAGE_PATH),
        help=f"Путь для сохранения изображений (по умолчанию: {DEFAULT_STORAGE_PATH})"
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Перезагрузить существующие изображения"
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Загрузить только определенную категорию"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ограничить количество загружаемых изображений (для теста)"
    )
    
    args = parser.parse_args()
    
    # Настроить логирование
    logger.remove()
    logger.add(
        sys.stdout,
        format="<level>{message}</level>",
        level="INFO"
    )
    
    # Запустить загрузку
    asyncio.run(main(
        storage_path=Path(args.output),
        skip_existing=not args.no_skip_existing,
        category_filter=args.category,
        limit=args.limit
    ))



