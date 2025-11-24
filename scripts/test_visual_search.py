#!/usr/bin/env python3
"""
Тестовый скрипт для визуального поиска с созданием коллажа результатов.
"""
import asyncio
import sys
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger


API_URL = "http://localhost:8000"
STORAGE_PATH = Path("/tmp/bakai_products")
OUTPUT_PATH = Path("/tmp/search_results")


async def get_random_test_image():
    """Получить случайное тестовое изображение."""
    logger.info("📂 Поиск тестового изображения...")
    
    images = list(STORAGE_PATH.glob("*.jpg"))
    images.extend(STORAGE_PATH.glob("*.jpeg"))
    
    if not images:
        logger.error("❌ Изображения не найдены!")
        return None
    
    # Выбрать случайное
    test_image = random.choice(images)
    logger.success(f"✅ Выбрано: {test_image.name}")
    
    return test_image


async def search_similar(image_path: Path, top_k: int = 5):
    """
    Поиск похожих изображений через API.
    
    Args:
        image_path: Путь к изображению
        top_k: Количество результатов
        
    Returns:
        Список результатов
    """
    logger.info(f"🔍 Поиск похожих изображений (top {top_k})...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            with open(image_path, 'rb') as f:
                files = {'image': (image_path.name, f, 'image/jpeg')}
                params = {'limit': top_k, 'min_similarity': 0.0}
                
                response = await client.post(
                    f"{API_URL}/api/v1/search/by-image",
                    files=files,
                    params=params
                )
                
                response.raise_for_status()
                data = response.json()
                
                logger.success(f"✅ Найдено результатов: {data['results_count']}")
                logger.info(f"⏱️  Время поиска: {data['query_time_ms']}ms")
                
                return data['results']
                
        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return []


async def download_image_from_url(url: str, save_path: Path):
    """Скачать изображение по URL."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            return True
    except Exception as e:
        logger.error(f"❌ Ошибка скачивания {url}: {e}")
        return False


def create_result_collage(query_image_path: Path, results: list, output_path: Path):
    """
    Создать коллаж с результатами поиска.
    
    Args:
        query_image_path: Путь к query изображению
        results: Список результатов поиска
        output_path: Путь для сохранения коллажа
    """
    logger.info("🎨 Создание коллажа результатов...")
    
    # Параметры
    img_size = 300  # Размер каждого изображения
    padding = 20
    text_height = 60
    
    # Размеры коллажа
    cols = 3  # Query + 2 результата в первом ряду
    rows = (len(results) + 2) // 3 + 1  # +1 для query
    
    canvas_width = cols * img_size + (cols + 1) * padding
    canvas_height = rows * (img_size + text_height) + (rows + 1) * padding
    
    # Создать canvas
    canvas = Image.new('RGB', (canvas_width, canvas_height), color='white')
    draw = ImageDraw.Draw(canvas)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Добавить query изображение
    try:
        query_img = Image.open(query_image_path)
        query_img.thumbnail((img_size, img_size), Image.Resampling.LANCZOS)
        
        # Центрировать
        x = padding
        y = padding
        
        # Создать белый фон
        bg = Image.new('RGB', (img_size, img_size), color='white')
        offset_x = (img_size - query_img.width) // 2
        offset_y = (img_size - query_img.height) // 2
        bg.paste(query_img, (offset_x, offset_y))
        
        canvas.paste(bg, (x, y))
        
        # Добавить текст
        text_y = y + img_size + 5
        draw.text((x + 10, text_y), "QUERY IMAGE", fill='red', font=font)
        draw.text((x + 10, text_y + 25), f"File: {query_image_path.name[:30]}", fill='black', font=font_small)
        
    except Exception as e:
        logger.error(f"❌ Ошибка добавления query изображения: {e}")
    
    # Добавить результаты
    for idx, result in enumerate(results):
        row = (idx + 1) // cols
        col = (idx + 1) % cols
        
        x = col * img_size + (col + 1) * padding
        y = row * (img_size + text_height) + (row + 1) * padding
        
        try:
            # Найти локальное изображение
            product_id = result.get('original_id', result.get('external_id', '').replace('bakai_', ''))
            
            # Поиск файла
            local_files = list(STORAGE_PATH.glob(f"{product_id}_*.jpg"))
            local_files.extend(STORAGE_PATH.glob(f"{product_id}_*.jpeg"))
            
            if local_files:
                img = Image.open(local_files[0])
                img.thumbnail((img_size, img_size), Image.Resampling.LANCZOS)
                
                # Центрировать
                bg = Image.new('RGB', (img_size, img_size), color='white')
                offset_x = (img_size - img.width) // 2
                offset_y = (img_size - img.height) // 2
                bg.paste(img, (offset_x, offset_y))
                
                canvas.paste(bg, (x, y))
                
                # Добавить текст
                text_y = y + img_size + 5
                similarity = result.get('similarity_score', 0)
                
                # Цвет по similarity
                if similarity > 0.9:
                    color = 'green'
                elif similarity > 0.7:
                    color = 'orange'
                else:
                    color = 'gray'
                
                draw.text((x + 10, text_y), f"#{idx + 1} - Score: {similarity:.3f}", fill=color, font=font)
                draw.text((x + 10, text_y + 25), f"ID: {product_id}", fill='black', font=font_small)
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления результата {idx + 1}: {e}")
            continue
    
    # Сохранить
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=95)
    
    logger.success(f"✅ Коллаж сохранен: {output_path}")


async def main():
    """Основная функция."""
    print("\n" + "=" * 70)
    print("  🔍 ТЕСТ ВИЗУАЛЬНОГО ПОИСКА")
    print("=" * 70)
    
    # 1. Выбрать тестовое изображение
    print("\n" + "=" * 70)
    print("📸 ШАГ 1: Выбор тестового изображения")
    print("=" * 70)
    
    test_image = await get_random_test_image()
    
    if not test_image:
        print("\n❌ Не удалось найти тестовое изображение!")
        return
    
    print(f"\n✅ Тестовое изображение: {test_image}")
    
    # 2. Поиск похожих
    print("\n" + "=" * 70)
    print("🔍 ШАГ 2: Поиск похожих изображений")
    print("=" * 70)
    
    results = await search_similar(test_image, top_k=8)
    
    if not results:
        print("\n❌ Результаты не найдены!")
        return
    
    # Показать результаты
    print(f"\n📊 Найдено результатов: {len(results)}")
    print("\n" + "-" * 70)
    
    for i, result in enumerate(results, 1):
        product_id = result.get('external_id', 'N/A')
        similarity = result.get('similarity_score', 0)
        original_id = result.get('original_id', 'N/A')
        
        print(f"\n{i}. Product ID: {product_id}")
        print(f"   Original ID: {original_id}")
        print(f"   Similarity: {similarity:.4f} ({similarity * 100:.2f}%)")
    
    print("-" * 70)
    
    # 3. Создать коллаж
    print("\n" + "=" * 70)
    print("🎨 ШАГ 3: Создание коллажа результатов")
    print("=" * 70)
    
    output_file = OUTPUT_PATH / f"search_result_{test_image.stem}.jpg"
    create_result_collage(test_image, results, output_file)
    
    # Итоги
    print("\n" + "=" * 70)
    print("✅ ТЕСТ ЗАВЕРШЕН")
    print("=" * 70)
    
    print(f"\n📁 Коллаж сохранен: {output_file}")
    print(f"\n💡 Откройте изображение:")
    print(f"   xdg-open {output_file}")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, format="<level>{message}</level>", level="INFO")
    
    asyncio.run(main())

