"""
Простой скрипт для скачивания изображений НАПРЯМУЮ из CDN API.
НЕ требует PostgreSQL, работает автономно.

Использование:
    python download_from_cdn_api.py
"""
import asyncio
import sys
from pathlib import Path
import os

try:
    import httpx
    from tqdm import tqdm
except ImportError:
    print("\n❌ Установите: pip install httpx tqdm")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# ============================================================================
# НАСТРОЙКИ
# ============================================================================
OUTPUT_DIR = Path("./cdn_images")
CONCURRENT_DOWNLOADS = 5

# CDN API настройки (из .env или укажите здесь)
CDN_API_URL = os.getenv("BAKAI_CDN_API_URL", "https://api-cdn.bakai.store")
CDN_ACCESS_KEY = os.getenv("BAKAI_CDN_ACCESS_KEY", "")
CDN_SECRET_KEY = os.getenv("BAKAI_CDN_SECRET_KEY", "")

# Заголовки для API
HEADERS = {
    "X-Access-Key": CDN_ACCESS_KEY,
    "X-Secret-Key": CDN_SECRET_KEY,
    "Content-Type": "application/json"
}
# ============================================================================


async def get_products_from_api(client, limit=100):
    """Получить товары из CDN API."""
    all_products = []
    offset = 0
    
    print("📦 Получение списка товаров из CDN API...")
    
    while True:
        try:
            url = f"{CDN_API_URL}/products"
            params = {"limit": limit, "offset": offset}
            
            response = await client.get(url, headers=HEADERS, params=params, timeout=30.0)
            
            if response.status_code != 200:
                print(f"\n❌ API вернул код: {response.status_code}")
                break
            
            data = response.json()
            products = data.get("products", [])
            
            if not products:
                break
            
            all_products.extend(products)
            offset += len(products)
            
            print(f"   Получено: {len(all_products)} товаров...", end='\r')
            
            # Если получили меньше чем limit, значит это последняя страница
            if len(products) < limit:
                break
                
        except Exception as e:
            print(f"\n❌ Ошибка API: {e}")
            break
    
    print(f"\n✅ Всего товаров: {len(all_products)}")
    return all_products


async def download_image(client, url, save_path):
    """Скачать изображение."""
    try:
        # Если URL относительный, добавить базовый URL
        if not url.startswith("http"):
            url = f"{CDN_API_URL}{url}"
        
        response = await client.get(url, headers=HEADERS, timeout=30.0, follow_redirects=True)
        
        if response.status_code == 200:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
    except:
        pass
    return False


async def main():
    """Главная функция."""
    print("\n" + "=" * 70)
    print("  📥 ЗАГРУЗКА ИЗОБРАЖЕНИЙ ИЗ CDN API")
    print("=" * 70)
    print(f"\n📁 Папка: {OUTPUT_DIR.absolute()}")
    print(f"🌐 API: {CDN_API_URL}")
    
    # Проверка credentials
    if not CDN_ACCESS_KEY or not CDN_SECRET_KEY:
        print("\n⚠️  ВНИМАНИЕ: CDN credentials не настроены!")
        print("Добавьте в .env файл:")
        print("   BAKAI_CDN_API_URL=https://api-cdn.bakai.store")
        print("   BAKAI_CDN_ACCESS_KEY=your_key")
        print("   BAKAI_CDN_SECRET_KEY=your_secret")
        print("\nПродолжаю без аутентификации (может не сработать)...")
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Получить товары
    async with httpx.AsyncClient() as client:
        # Тест подключения
        try:
            response = await client.get(f"{CDN_API_URL}/products", headers=HEADERS, params={"limit": 1}, timeout=10.0)
            if response.status_code != 200:
                print(f"\n❌ CDN API недоступен (код: {response.status_code})")
                return
        except Exception as e:
            print(f"\n❌ Не удалось подключиться к CDN API: {e}")
            return
        
        print("✅ Подключение к API успешно\n")
        
        # Получить все товары
        products = await get_products_from_api(client)
        
        if not products:
            print("\n❌ Нет товаров для загрузки")
            return
        
        # Подготовить список
        to_download = []
        for p in products:
            product_id = p.get('id')
            image_url = p.get('image_url')
            
            if not product_id or not image_url:
                continue
            
            save_path = OUTPUT_DIR / f"{product_id}.jpg"
            
            if not save_path.exists():
                to_download.append({
                    'id': product_id,
                    'url': image_url,
                    'path': save_path
                })
        
        print(f"📥 К загрузке: {len(to_download)}")
        print(f"⏭️  Уже есть: {len(products) - len(to_download)}\n")
        
        if not to_download:
            print("✅ Все изображения уже загружены!")
            return
        
        # Загрузить
        print("🚀 Начинаю загрузку...\n")
        downloaded = 0
        failed = 0
        
        with tqdm(total=len(to_download), desc="Загрузка", unit="img") as pbar:
            for i in range(0, len(to_download), CONCURRENT_DOWNLOADS):
                batch = to_download[i:i + CONCURRENT_DOWNLOADS]
                tasks = [download_image(client, item['url'], item['path']) for item in batch]
                results = await asyncio.gather(*tasks)
                
                downloaded += sum(results)
                failed += len(results) - sum(results)
                pbar.update(len(batch))
                pbar.set_postfix({'OK': downloaded, 'ERR': failed})
    
    # Итоги
    print("\n" + "=" * 70)
    print("📊 ИТОГИ")
    print("=" * 70)
    print(f"\n✅ Загружено: {downloaded}/{len(to_download)}")
    if failed > 0:
        print(f"❌ Ошибок: {failed}")
    
    # Размер
    files = list(OUTPUT_DIR.glob("*.jpg"))
    if files:
        total_size = sum(f.stat().st_size for f in files)
        if total_size > 1024**3:
            size_str = f"{total_size / 1024**3:.2f} GB"
        elif total_size > 1024**2:
            size_str = f"{total_size / 1024**2:.2f} MB"
        else:
            size_str = f"{total_size / 1024:.2f} KB"
        
        print(f"\n📁 Папка: {OUTPUT_DIR.absolute()}")
        print(f"💾 Размер: {size_str}")
        print(f"📊 Файлов: {len(files)}")
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано. Запустите снова для продолжения")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")




