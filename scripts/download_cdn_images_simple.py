"""
Простой скрипт для скачивания изображений из CDN в локальную папку.
Использование: python download_cdn_images_simple.py
"""
import asyncio
import sys
from pathlib import Path

# Проверка и установка зависимостей
try:
    import httpx
    from tqdm import tqdm
except ImportError:
    print("❌ Установите зависимости: pip install httpx tqdm")
    sys.exit(1)

# Добавить путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app.db.postgres import get_session, Product
    from sqlalchemy import select
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("💡 Убедитесь что запускаете из корня проекта")
    sys.exit(1)


# ============================================================================
# НАСТРОЙКИ - ИЗМЕНИТЕ ПО НЕОБХОДИМОСТИ
# ============================================================================
OUTPUT_DIR = Path("./cdn_images")  # Папка для сохранения
CONCURRENT_DOWNLOADS = 5  # Сколько загружать параллельно
# ============================================================================


async def download_image(client, url, save_path):
    """Скачать одно изображение."""
    try:
        response = await client.get(url, timeout=30.0, follow_redirects=True)
        if response.status_code == 200:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Ошибка {url}: {e}")
    return False


async def main():
    print(f"📥 Скачивание изображений в: {OUTPUT_DIR.absolute()}")
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Получить список товаров из БД
    print("📦 Получение списка товаров из базы...")
    products = []
    async with get_session() as session:
        result = await session.execute(select(Product))
        for product in result.scalars().all():
            if product.image_url:
                products.append({
                    'id': product.external_id,
                    'url': product.image_url,
                    'path': OUTPUT_DIR / f"{product.external_id}.jpg"
                })
    
    # Фильтровать уже загруженные
    to_download = [p for p in products if not p['path'].exists()]
    print(f"✅ Найдено: {len(products)} товаров")
    print(f"📥 К загрузке: {len(to_download)} (пропущено уже загруженных: {len(products) - len(to_download)})")
    
    if not to_download:
        print("✅ Все изображения уже загружены!")
        return
    
    # Скачать изображения
    print("\n🚀 Начинаю загрузку...")
    downloaded = 0
    failed = 0
    
    async with httpx.AsyncClient() as client:
        with tqdm(total=len(to_download), desc="Загрузка", unit="img") as pbar:
            # Загружать батчами
            for i in range(0, len(to_download), CONCURRENT_DOWNLOADS):
                batch = to_download[i:i + CONCURRENT_DOWNLOADS]
                tasks = [download_image(client, p['url'], p['path']) for p in batch]
                results = await asyncio.gather(*tasks)
                
                downloaded += sum(results)
                failed += len(results) - sum(results)
                pbar.update(len(batch))
                pbar.set_postfix({'успешно': downloaded, 'ошибок': failed})
    
    # Итоги
    print(f"\n✅ Загружено: {downloaded}/{len(to_download)}")
    if failed > 0:
        print(f"❌ Ошибок: {failed}")
    print(f"📁 Папка: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    asyncio.run(main())

