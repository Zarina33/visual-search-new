"""
Простой скрипт для массовой загрузки изображений из CDN.
Работает напрямую с Python (не требует poetry run).

Использование:
    python download_cdn.py

Или укажите свою папку:
    python download_cdn.py --output /path/to/save
"""
import asyncio
import sys
from pathlib import Path
import os

# Проверка зависимостей
try:
    import httpx
    from tqdm import tqdm
except ImportError:
    print("\n❌ Не хватает библиотек!")
    print("📦 Установите: pip install httpx tqdm")
    print("Или через poetry: poetry install")
    sys.exit(1)

# Добавить путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from app.db.postgres import get_session, Product
    from sqlalchemy import select
except ImportError as e:
    print(f"\n❌ Ошибка импорта модулей проекта: {e}")
    print("💡 Убедитесь что:")
    print("   1. Вы в корне проекта")
    print("   2. Установлены зависимости: poetry install")
    sys.exit(1)


# ============================================================================
# НАСТРОЙКИ
# ============================================================================
DEFAULT_OUTPUT_DIR = Path("./cdn_images")
CONCURRENT_DOWNLOADS = 5  # Параллельных загрузок
TIMEOUT = 30  # Таймаут в секундах
# ============================================================================


async def download_image(client, url, save_path):
    """
    Скачать одно изображение.
    
    Args:
        client: httpx.AsyncClient
        url: URL изображения
        save_path: Путь для сохранения
        
    Returns:
        True если успешно, False если ошибка
    """
    try:
        response = await client.get(url, timeout=TIMEOUT, follow_redirects=True)
        if response.status_code == 200:
            # Создать директорию если не существует
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Сохранить файл
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            return True
        else:
            return False
            
    except Exception as e:
        print(f"\n⚠️  Ошибка при загрузке {save_path.name}: {e}")
        return False


async def get_products_from_db():
    """
    Получить список товаров с изображениями из базы данных.
    
    Returns:
        Список словарей с информацией о товарах
    """
    products = []
    
    try:
        async with get_session() as session:
            result = await session.execute(select(Product))
            
            for product in result.scalars().all():
                if product.image_url:  # Только товары с изображениями
                    products.append({
                        'id': product.external_id,
                        'url': product.image_url,
                        'title': product.title
                    })
        
        return products
        
    except Exception as e:
        print(f"\n❌ Ошибка при получении товаров из БД: {e}")
        print("💡 Убедитесь что:")
        print("   1. PostgreSQL запущен: docker-compose ps")
        print("   2. База инициализирована")
        sys.exit(1)


async def download_all_images(output_dir: Path):
    """
    Главная функция загрузки всех изображений.
    
    Args:
        output_dir: Директория для сохранения
    """
    print("\n" + "=" * 70)
    print("  📥 МАССОВАЯ ЗАГРУЗКА ИЗОБРАЖЕНИЙ ИЗ CDN")
    print("=" * 70)
    print(f"\n📁 Папка сохранения: {output_dir.absolute()}")
    
    # Создать папку
    output_dir.mkdir(exist_ok=True)
    
    # Шаг 1: Получить товары из БД
    print("\n📦 Получение списка товаров из базы данных...")
    products = await get_products_from_db()
    print(f"✅ Найдено товаров: {len(products)}")
    
    if not products:
        print("\n⚠️  В базе нет товаров с изображениями!")
        return
    
    # Подготовить список для загрузки
    to_download = []
    for product in products:
        save_path = output_dir / f"{product['id']}.jpg"
        
        if not save_path.exists():
            to_download.append({
                **product,
                'path': save_path
            })
    
    already_downloaded = len(products) - len(to_download)
    print(f"📥 К загрузке: {len(to_download)}")
    
    if already_downloaded > 0:
        print(f"⏭️  Пропущено (уже загружено): {already_downloaded}")
    
    if not to_download:
        print("\n✅ Все изображения уже загружены!")
        return
    
    # Шаг 2: Загрузить изображения
    print(f"\n🚀 Начинаю загрузку ({CONCURRENT_DOWNLOADS} параллельно)...")
    
    downloaded = 0
    failed = 0
    
    async with httpx.AsyncClient() as client:
        with tqdm(total=len(to_download), desc="Загрузка", unit=" img") as pbar:
            # Загружать батчами для контроля параллелизма
            for i in range(0, len(to_download), CONCURRENT_DOWNLOADS):
                batch = to_download[i:i + CONCURRENT_DOWNLOADS]
                
                # Запустить загрузку батча параллельно
                tasks = [
                    download_image(client, item['url'], item['path'])
                    for item in batch
                ]
                results = await asyncio.gather(*tasks)
                
                # Обновить статистику
                downloaded += sum(results)
                failed += len(results) - sum(results)
                
                # Обновить прогресс-бар
                pbar.update(len(batch))
                pbar.set_postfix({
                    'успешно': downloaded,
                    'ошибок': failed,
                    'скорость': f"{downloaded / (pbar.format_dict['elapsed'] or 1):.1f}/s"
                })
    
    # Итоги
    print("\n" + "=" * 70)
    print("📊 ИТОГИ")
    print("=" * 70)
    print(f"\n✅ Успешно загружено: {downloaded}/{len(to_download)}")
    
    if failed > 0:
        print(f"❌ Ошибок загрузки: {failed}")
    
    print(f"\n📁 Изображения сохранены в: {output_dir.absolute()}")
    print(f"💾 Размер на диске: ", end="")
    
    # Подсчитать размер
    total_size = sum(f.stat().st_size for f in output_dir.glob("*.jpg"))
    if total_size > 1024**3:
        print(f"{total_size / 1024**3:.2f} GB")
    elif total_size > 1024**2:
        print(f"{total_size / 1024**2:.2f} MB")
    else:
        print(f"{total_size / 1024:.2f} KB")
    
    print("\n💡 Для повторной загрузки просто запустите скрипт снова")
    print("   (уже загруженные файлы будут пропущены)")
    print("=" * 70 + "\n")


def main():
    """Точка входа в программу."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Массовая загрузка изображений товаров из CDN",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  
  # Базовое использование (сохранит в ./cdn_images)
  python download_cdn.py
  
  # Указать свою папку
  python download_cdn.py --output /home/user/images
  
  # С относительным путем
  python download_cdn.py --output ../product_images
        """
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help=f'Папка для сохранения изображений (по умолчанию: {DEFAULT_OUTPUT_DIR})'
    )
    
    args = parser.parse_args()
    
    # Преобразовать путь
    output_dir = Path(args.output)
    
    # Запустить загрузку
    try:
        asyncio.run(download_all_images(output_dir))
    except KeyboardInterrupt:
        print("\n\n⚠️  Загрузка прервана пользователем")
        print("💡 Запустите скрипт снова для продолжения")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()



