#!/usr/bin/env python3
"""
Скрипт для прямой загрузки изображений товаров из BakaiMarket CDN API.

Отличия от download_images_from_cdn.py:
- Загружает данные напрямую из CDN API (не требует базы данных)
- Сначала получает список товаров через API
- Затем скачивает изображения

Подходит для:
- Первоначальной загрузки изображений
- Когда база данных недоступна
- Создания локального кэша изображений
"""
import asyncio
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional
from tqdm import tqdm
import time
from PIL import Image
import io
import httpx
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.utils.bakai_cdn_client import BakaiCDNClient
from app.config import settings


# Настройки
DEFAULT_STORAGE_PATH = Path("/home/zarina/Work/bektemir_comp/BakaiMarket/bakai_cdn_images")
BATCH_SIZE = 10  # Количество параллельных загрузок
API_BATCH_SIZE = 100  # Количество товаров за один API запрос
MIN_IMAGE_SIZE = 50  # Минимальный размер изображения (px)
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # Максимальный размер файла (20MB)
DOWNLOAD_TIMEOUT = 30  # Таймаут загрузки (секунды)


class DownloadStats:
    """Статистика загрузки."""
    
    def __init__(self):
        self.total = 0
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0
        self.invalid = 0
        self.no_image = 0
        self.start_time = time.time()
    
    def add_downloaded(self):
        self.downloaded += 1
    
    def add_skipped(self):
        self.skipped += 1
    
    def add_failed(self):
        self.failed += 1
    
    def add_invalid(self):
        self.invalid += 1
    
    def add_no_image(self):
        self.no_image += 1
    
    def get_elapsed(self) -> float:
        return time.time() - self.start_time
    
    def get_speed(self) -> float:
        elapsed = self.get_elapsed()
        if elapsed > 0:
            return self.downloaded / elapsed
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
        print(f"🚫 Товары без изображений: {self.no_image}")
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
        
        if len(image_data) < 1000:  # Меньше 1KB
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
        
        # Конвертировать в RGB
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
        
    except Exception as e:
        logger.debug(f"⚠️  {product_id}: ошибка загрузки - {e}")
        return None


async def get_all_products_from_api(
    cdn_client: BakaiCDNClient,
    max_products: Optional[int] = None
) -> List[Dict]:
    """
    Получить все товары через CDN API.
    
    Args:
        cdn_client: CDN клиент
        max_products: Максимальное количество товаров
        
    Returns:
        Список товаров
    """
    logger.info("📦 Получение списка товаров из CDN API...")
    
    all_products = await cdn_client.get_all_products(
        batch_size=API_BATCH_SIZE,
        max_products=max_products
    )
    
    logger.success(f"✅ Получено товаров из API: {len(all_products)}")
    
    return all_products


def prepare_products_for_download(
    api_products: List[Dict],
    storage_path: Path,
    skip_existing: bool = True
) -> List[Dict]:
    """
    Подготовить список товаров для загрузки.
    
    Args:
        api_products: Товары из API
        storage_path: Путь к хранилищу
        skip_existing: Пропускать существующие
        
    Returns:
        Список товаров для загрузки
    """
    products = []
    
    for product in api_products:
        product_id = product.get('id')
        image_url = product.get('image_url')
        
        if not product_id or not image_url:
            continue
        
        # Определить категорию и путь
        category = product.get('category', 'uncategorized')
        if not category:
            category = 'uncategorized'
        
        category_dir = storage_path / category
        
        # Получить расширение
        ext = ".jpg"
        if image_url:
            parsed = urlparse(image_url)
            path_ext = Path(parsed.path).suffix
            if path_ext.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                ext = path_ext.lower()
        
        filename = f"{product_id}{ext}"
        file_path = category_dir / filename
        
        # Пропустить если уже есть
        if skip_existing and file_path.exists():
            continue
        
        products.append({
            'id': product_id,
            'title': product.get('title', f'Product {product_id}'),
            'category': category,
            'image_url': image_url,
            'file_path': file_path
        })
    
    return products


async def download_and_save_image(
    client: httpx.AsyncClient,
    product: Dict,
    cdn_client: BakaiCDNClient,
    stats: DownloadStats
) -> bool:
    """
    Скачать и сохранить одно изображение.
    
    Args:
        client: HTTP клиент
        product: Данные товара
        cdn_client: CDN клиент
        stats: Объект статистики
        
    Returns:
        True если успешно, False иначе
    """
    product_id = product['id']
    file_path = product['file_path']
    
    try:
        # Создать директорию
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Скачать изображение
        image_data = await download_image(
            client=client,
            image_url=product['image_url'],
            product_id=str(product_id),
            cdn_client=cdn_client
        )
        
        if image_data is None:
            stats.add_failed()
            return False
        
        # Валидировать
        validated_img = validate_image(image_data, str(product_id))
        
        if validated_img is None:
            stats.add_invalid()
            return False
        
        # Сохранить
        validated_img.save(file_path, 'JPEG', quality=95)
        stats.add_downloaded()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения {product_id}: {e}")
        stats.add_failed()
        return False


async def download_images_batch(
    products: List[Dict],
    cdn_client: BakaiCDNClient,
    stats: DownloadStats,
    progress_bar: tqdm
) -> None:
    """
    Скачать пакет изображений параллельно.
    
    Args:
        products: Список товаров
        cdn_client: CDN клиент
        stats: Статистика
        progress_bar: Прогресс-бар
    """
    async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
        tasks = []
        
        for product in products:
            async def download_wrapper(p=product):
                result = await download_and_save_image(client, p, cdn_client, stats)
                progress_bar.update(1)
                progress_bar.set_postfix({
                    'downloaded': stats.downloaded,
                    'failed': stats.failed,
                    'speed': f"{stats.get_speed():.1f}/s"
                })
                return result
            
            tasks.append(download_wrapper())
        
        await asyncio.gather(*tasks, return_exceptions=True)


async def main(
    storage_path: Path = DEFAULT_STORAGE_PATH,
    skip_existing: bool = True,
    max_products: Optional[int] = None
):
    """
    Основная функция загрузки.
    
    Args:
        storage_path: Путь для сохранения
        skip_existing: Пропускать существующие
        max_products: Ограничение количества
    """
    start_time = time.time()
    
    print("\n" + "=" * 70)
    print("  📥 ПРЯМАЯ ЗАГРУЗКА ИЗОБРАЖЕНИЙ ИЗ CDN API")
    print("=" * 70)
    
    print(f"\n⚙️  Настройки:")
    print(f"   Путь сохранения: {storage_path}")
    print(f"   Пропуск существующих: {'ДА' if skip_existing else 'НЕТ'}")
    print(f"   Ограничение: {max_products or 'НЕТ'}")
    print(f"   Параллельных загрузок: {BATCH_SIZE}")
    
    # Создать директорию
    storage_path.mkdir(parents=True, exist_ok=True)
    
    # Инициализировать CDN клиент
    cdn_client = BakaiCDNClient()
    
    # Проверить подключение
    print("\n🔍 Проверка подключения к CDN API...")
    if not await cdn_client.test_connection():
        print("\n❌ Не удалось подключиться к CDN API!")
        print("\n💡 Проверьте:")
        print("   1. Настройки в .env файле:")
        print("      - BAKAI_CDN_API_URL")
        print("      - BAKAI_CDN_ACCESS_KEY")
        print("      - BAKAI_CDN_SECRET_KEY")
        print("   2. Доступность CDN API")
        return
    
    print("✅ Подключение установлено")
    
    # Получить товары из API
    print("\n" + "=" * 70)
    print("📦 ШАГ 1: Получение списка товаров из API")
    print("=" * 70)
    
    api_products = await get_all_products_from_api(cdn_client, max_products)
    
    if not api_products:
        print("\n❌ Не удалось получить товары из API!")
        return
    
    # Подготовить список для загрузки
    print("\n📋 Подготовка списка для загрузки...")
    products = prepare_products_for_download(
        api_products=api_products,
        storage_path=storage_path,
        skip_existing=skip_existing
    )
    
    if not products:
        print("\n✅ Все изображения уже загружены!")
        return
    
    print(f"✅ Товаров для загрузки: {len(products)}")
    
    # Подсчитать товары без изображений
    no_image_count = len(api_products) - len(products)
    if skip_existing:
        print(f"⏭️  Пропущено (уже загружено): {no_image_count}")
    
    # Инициализировать статистику
    stats = DownloadStats()
    stats.total = len(products)
    
    # Загрузка изображений
    print("\n" + "=" * 70)
    print(f"📥 ШАГ 2: Загрузка {len(products)} изображений")
    print("=" * 70)
    
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
    
    # Показать итоги
    stats.print_summary()
    
    # Статистика по категориям
    print("\n📊 Статистика по категориям:")
    categories = {}
    for product in products:
        cat = product['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]:
        cat_dir = storage_path / cat
        actual_count = len(list(cat_dir.glob("*.jpg"))) if cat_dir.exists() else 0
        print(f"   {cat}: {actual_count} изображений")
    
    if len(categories) > 10:
        print(f"   ... и еще {len(categories) - 10} категорий")
    
    print(f"\n💡 Изображения сохранены в: {storage_path}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Прямая загрузка изображений из BakaiMarket CDN API"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_STORAGE_PATH),
        help=f"Путь для сохранения (по умолчанию: {DEFAULT_STORAGE_PATH})"
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Перезагрузить существующие изображения"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ограничить количество товаров (для теста)"
    )
    
    args = parser.parse_args()
    
    # Настроить логирование
    logger.remove()
    logger.add(
        sys.stdout,
        format="<level>{message}</level>",
        level="INFO"
    )
    
    # Запустить
    asyncio.run(main(
        storage_path=Path(args.output),
        skip_existing=not args.no_skip_existing,
        max_products=args.limit
    ))



