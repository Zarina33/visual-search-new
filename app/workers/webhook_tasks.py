"""
Celery tasks for webhook event processing.
"""
import asyncio
from typing import Dict, Any
from pathlib import Path
import tempfile

from app.workers.celery_app import celery_app
from app.models.clip_model import CLIPEmbedder
from app.db.qdrant import QdrantManager
from app.db.postgres import get_session, create_product, update_product, delete_product, get_product_by_external_id
from app.utils.bakai_s3_client import BakaiS3Client
from app.config import settings
from loguru import logger


@celery_app.task(name="process_product_created", bind=True, max_retries=3)
def process_product_created(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Обработать событие создания товара.
    
    Args:
        event_data: Данные события
        
    Returns:
        Результат обработки
    """
    try:
        product_id = event_data["product_id"]
        logger.info(f"📦 Processing product.created: {product_id}")
        
        # Запустить async обработку
        result = asyncio.run(_process_product_created_async(event_data))
        
        logger.success(f"✅ Product created: {product_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to process product.created: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


async def _process_product_created_async(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Async обработка создания товара."""
    product_id = event_data["product_id"]
    image_key = event_data.get("image_key")
    
    if not image_key:
        logger.warning(f"⚠️  No image_key for product {product_id}")
        return {"status": "skipped", "reason": "no_image"}
    
    # 1. Скачать изображение из S3
    s3_client = BakaiS3Client()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        success = s3_client.download_file(
            bucket_name="product-images",
            object_key=image_key,
            local_path=temp_file.name
        )
        
        if not success:
            logger.error(f"❌ Failed to download image: {image_key}")
            return {"status": "error", "reason": "download_failed"}
        
        temp_path = temp_file.name
    
    try:
        # 2. Генерировать CLIP эмбеддинг
        embedder = CLIPEmbedder()
        embedding = await embedder.generate_embedding(temp_path)
        
        if embedding is None:
            logger.error(f"❌ Failed to generate embedding for {product_id}")
            return {"status": "error", "reason": "embedding_failed"}
        
        # 3. Сохранить в PostgreSQL
        image_url = s3_client.generate_presigned_url(
            bucket_name="product-images",
            object_key=image_key,
            expiration=31536000  # 1 год
        )
        
        async with get_session() as session:
            await create_product(session, {
                "external_id": f"bakai_{product_id}",
                "title": event_data.get("title", f"Product {product_id}"),
                "description": event_data.get("description", ""),
                "category": event_data.get("category", "bakai"),
                "price": event_data.get("price"),
                "currency": event_data.get("currency", "KGS"),
                "image_url": image_url,
                "product_metadata": {
                    "source": "webhook",
                    "product_id": product_id,
                    "s3_key": image_key,
                    **event_data.get("metadata", {})
                }
            })
        
        # 4. Сохранить в Qdrant
        qdrant = QdrantManager()
        await qdrant.upsert_vectors(
            product_ids=[f"bakai_{product_id}"],
            vectors=[embedding.tolist()],
            payloads=[{
                "product_id": f"bakai_{product_id}",
                "source": "webhook",
                "original_id": product_id
            }]
        )
        
        return {
            "status": "success",
            "product_id": product_id,
            "message": "Product created and indexed"
        }
        
    finally:
        # Удалить временный файл
        try:
            Path(temp_path).unlink()
        except Exception as e:
            logger.warning(f"⚠️  Failed to delete temp file: {e}")


@celery_app.task(name="process_product_updated", bind=True, max_retries=3)
def process_product_updated(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Обработать событие обновления товара.
    
    Args:
        event_data: Данные события
        
    Returns:
        Результат обработки
    """
    try:
        product_id = event_data["product_id"]
        logger.info(f"🔄 Processing product.updated: {product_id}")
        
        # Запустить async обработку
        result = asyncio.run(_process_product_updated_async(event_data))
        
        logger.success(f"✅ Product updated: {product_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to process product.updated: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


async def _process_product_updated_async(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Async обработка обновления товара."""
    product_id = event_data["product_id"]
    external_id = f"bakai_{product_id}"
    
    # Проверить существует ли товар
    async with get_session() as session:
        product = await get_product_by_external_id(session, external_id)
        
        if not product:
            logger.warning(f"⚠️  Product not found, creating: {product_id}")
            # Если товар не найден, создаем его
            return await _process_product_created_async(event_data)
        
        # Обновить метаданные в PostgreSQL
        update_data = {}
        
        if "title" in event_data:
            update_data["title"] = event_data["title"]
        if "description" in event_data:
            update_data["description"] = event_data["description"]
        if "category" in event_data:
            update_data["category"] = event_data["category"]
        if "price" in event_data:
            update_data["price"] = event_data["price"]
        if "currency" in event_data:
            update_data["currency"] = event_data["currency"]
        
        if update_data:
            await update_product(session, external_id, update_data)
        
        # Если изображение изменилось, переиндексировать
        image_key = event_data.get("image_key")
        if image_key:
            logger.info(f"🖼️  Re-indexing image for {product_id}")
            # Вызвать создание (переиндексацию)
            return await _process_product_created_async(event_data)
        
        return {
            "status": "success",
            "product_id": product_id,
            "message": "Product metadata updated"
        }


@celery_app.task(name="process_product_deleted", bind=True, max_retries=3)
def process_product_deleted(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Обработать событие удаления товара.
    
    Args:
        event_data: Данные события
        
    Returns:
        Результат обработки
    """
    try:
        product_id = event_data["product_id"]
        logger.info(f"🗑️  Processing product.deleted: {product_id}")
        
        # Запустить async обработку
        result = asyncio.run(_process_product_deleted_async(event_data))
        
        logger.success(f"✅ Product deleted: {product_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to process product.deleted: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


async def _process_product_deleted_async(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Async обработка удаления товара."""
    product_id = event_data["product_id"]
    external_id = f"bakai_{product_id}"
    
    # 1. Удалить из PostgreSQL
    async with get_session() as session:
        deleted = await delete_product(session, external_id)
        
        if not deleted:
            logger.warning(f"⚠️  Product not found in PostgreSQL: {product_id}")
    
    # 2. Удалить из Qdrant
    qdrant = QdrantManager()
    try:
        await qdrant.delete_vectors([external_id])
    except Exception as e:
        logger.warning(f"⚠️  Failed to delete from Qdrant: {e}")
    
    return {
        "status": "success",
        "product_id": product_id,
        "message": "Product deleted from all databases"
    }


@celery_app.task(name="process_product_image_updated", bind=True, max_retries=3)
def process_product_image_updated(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Обработать событие обновления изображения товара.
    
    Args:
        event_data: Данные события
        
    Returns:
        Результат обработки
    """
    try:
        product_id = event_data["product_id"]
        logger.info(f"🖼️  Processing product.image.updated: {product_id}")
        
        # Переиндексировать изображение (то же что и создание)
        result = asyncio.run(_process_product_created_async(event_data))
        
        logger.success(f"✅ Product image updated: {product_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to process product.image.updated: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

