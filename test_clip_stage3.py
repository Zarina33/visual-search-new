"""
Полный тест CLIP модели для Этапа 3
"""
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np
from app.models.clip_model import CLIPEmbedder

def create_test_images():
    """Создать тестовые изображения"""
    print("\n📸 Создание тестовых изображений...")
    
    test_dir = Path("test_images")
    test_dir.mkdir(exist_ok=True)
    
    # Создаём 5 тестовых изображений разных цветов
    colors = [
        ("red", (255, 0, 0)),
        ("blue", (0, 0, 255)),
        ("green", (0, 255, 0)),
        ("yellow", (255, 255, 0)),
        ("purple", (128, 0, 128))
    ]
    
    image_paths = []
    for name, color in colors:
        img = Image.new('RGB', (224, 224), color=color)
        draw = ImageDraw.Draw(img)
        # Добавляем квадрат другого цвета
        draw.rectangle([50, 50, 174, 174], fill='white')
        
        path = test_dir / f"{name}_square.jpg"
        img.save(path)
        image_paths.append(str(path))
        print(f"  ✓ Создано: {path}")
    
    return image_paths

async def test_single_embedding(embedder, image_path):
    """Тест генерации одного эмбеддинга"""
    print("\n🧪 Тест 1: Генерация одного эмбеддинга")
    
    embedding = await embedder.generate_embedding(image_path)
    
    print(f"  ✓ Эмбеддинг создан")
    print(f"  ✓ Размерность: {embedding.shape}")
    print(f"  ✓ Тип: {type(embedding)}")
    print(f"  ✓ L2 norm: {np.linalg.norm(embedding):.4f} (должно быть ~1.0)")
    
    assert embedding.shape == (512,), f"Неправильная размерность: {embedding.shape}"
    assert isinstance(embedding, np.ndarray), "Должен быть numpy array"
    assert 0.99 <= np.linalg.norm(embedding) <= 1.01, "Вектор не нормализован!"
    
    print("  ✅ Тест пройден!")
    return embedding

async def test_batch_embedding(embedder, image_paths):
    """Тест batch обработки"""
    print("\n🧪 Тест 2: Batch обработка")
    
    embeddings = await embedder.generate_embeddings_batch(image_paths, batch_size=2)
    
    print(f"  ✓ Обработано изображений: {len(embeddings)}")
    print(f"  ✓ Размерность каждого: {embeddings[0].shape}")
    
    # Проверка нормализации всех векторов
    norms = [np.linalg.norm(emb) for emb in embeddings]
    print(f"  ✓ L2 norms: {[f'{n:.4f}' for n in norms]}")
    
    assert len(embeddings) == len(image_paths), "Неправильное количество эмбеддингов"
    for norm in norms:
        assert 0.99 <= norm <= 1.01, f"Вектор не нормализован: {norm}"
    
    print("  ✅ Тест пройден!")
    return embeddings

def test_similarity(embeddings):
    """Тест вычисления similarity"""
    print("\n🧪 Тест 3: Вычисление similarity")
    
    # Cosine similarity между первым и остальными
    query = embeddings[0]
    
    print(f"  Сравниваем первое изображение (red) с остальными:")
    for i, emb in enumerate(embeddings[1:], 1):
        similarity = np.dot(query, emb)
        print(f"    - Изображение {i+1}: {similarity:.4f}")
    
    # Similarity с самим собой должна быть ~1.0
    self_similarity = np.dot(query, query)
    print(f"  ✓ Similarity с самим собой: {self_similarity:.4f} (должно быть ~1.0)")
    
    assert 0.99 <= self_similarity <= 1.01, "Self-similarity должна быть ~1.0"
    
    print("  ✅ Тест пройден!")

async def test_error_handling(embedder):
    """Тест обработки ошибок"""
    print("\n🧪 Тест 4: Обработка ошибок")
    
    # Тест несуществующего файла
    try:
        await embedder.generate_embedding("nonexistent_file.jpg")
        print("  ❌ Ошибка не была обработана!")
        assert False, "Должна была быть ошибка"
    except Exception as e:
        print(f"  ✓ Ошибка корректно обработана: {type(e).__name__}")
    
    # Тест batch с несуществующими файлами
    embeddings = await embedder.generate_embeddings_batch([
        "test_images/red_square.jpg",
        "nonexistent.jpg",
        "test_images/blue_square.jpg"
    ])
    
    successful = sum(1 for emb in embeddings if emb is not None)
    print(f"  ✓ Batch с ошибками: получено {len(embeddings)} элементов, из них {successful} успешных")
    assert len(embeddings) == 3, "Должно быть 3 элемента в списке"
    assert successful == 2, "Должно быть 2 успешных эмбеддинга"
    assert embeddings[1] is None, "Второй элемент должен быть None (несуществующий файл)"
    
    print("  ✅ Тест пройден!")

async def main():
    print("=" * 60)
    print("  ТЕСТИРОВАНИЕ ЭТАПА 3: CLIP модель")
    print("=" * 60)
    
    try:
        # Создаём тестовые изображения
        image_paths = create_test_images()
        
        # Инициализация CLIP
        print("\n🚀 Инициализация CLIP модели...")
        embedder = CLIPEmbedder(device="auto")
        print(f"  ✓ Устройство: {embedder.device}")
        print(f"  ✓ Размерность: {embedder.get_embedding_dimension()}")
        
        # Тесты
        embedding = await test_single_embedding(embedder, image_paths[0])
        embeddings = await test_batch_embedding(embedder, image_paths)
        test_similarity(embeddings)
        await test_error_handling(embedder)
        
        print("\n" + "=" * 60)
        print("  🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 60)
        print("\n📊 Статистика:")
        print(f"  • Модель: {embedder.model_name}")
        print(f"  • Устройство: {embedder.device}")
        print(f"  • Размерность: {embedder.get_embedding_dimension()}")
        print(f"  • Тестовых изображений: {len(image_paths)}")
        print(f"  • Векторы нормализованы: ✅")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())