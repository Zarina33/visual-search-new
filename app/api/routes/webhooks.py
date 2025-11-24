"""
Webhook endpoints for receiving events from BakaiMarket.
"""
from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional
import json
from loguru import logger

from app.schemas.webhook import WebhookEvent, WebhookResponse, WebhookEventType
from app.utils.webhook_security import verify_signature
from app.workers.webhook_tasks import (
    process_product_created,
    process_product_updated,
    process_product_deleted,
    process_product_image_updated
)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/bakai", response_model=WebhookResponse)
async def receive_bakai_webhook(
    request: Request,
    x_webhook_signature: Optional[str] = Header(None, description="HMAC-SHA256 signature")
) -> WebhookResponse:
    """
    Принять webhook событие от BakaiMarket.
    
    Обрабатывает события:
    - product.created - новый товар
    - product.updated - обновление товара
    - product.deleted - удаление товара
    - product.image.updated - обновление изображения
    
    Args:
        request: FastAPI request
        x_webhook_signature: HMAC подпись в заголовке
        
    Returns:
        Ответ с подтверждением приема
        
    Raises:
        HTTPException: Если подпись невалидна или событие некорректно
    """
    try:
        # 1. Получить raw body для валидации подписи
        body = await request.body()
        body_str = body.decode('utf-8')
        
        # 2. Валидировать подпись
        if x_webhook_signature:
            if not verify_signature(body_str, x_webhook_signature):
                logger.error("❌ Invalid webhook signature")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid webhook signature"
                )
        else:
            logger.warning("⚠️  No signature provided in webhook request")
        
        # 3. Парсить событие
        try:
            event_dict = json.loads(body_str)
            event = WebhookEvent(**event_dict)
        except Exception as e:
            logger.error(f"❌ Failed to parse webhook event: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid webhook payload: {str(e)}"
            )
        
        logger.info(f"📨 Received webhook: {event.event_type} (ID: {event.event_id})")
        
        # 4. Отправить в Celery для фоновой обработки
        task = None
        event_data = event.data.model_dump()
        
        if event.event_type == WebhookEventType.PRODUCT_CREATED:
            task = process_product_created.delay(event_data)
            
        elif event.event_type == WebhookEventType.PRODUCT_UPDATED:
            task = process_product_updated.delay(event_data)
            
        elif event.event_type == WebhookEventType.PRODUCT_DELETED:
            task = process_product_deleted.delay(event_data)
            
        elif event.event_type == WebhookEventType.PRODUCT_IMAGE_UPDATED:
            task = process_product_image_updated.delay(event_data)
            
        else:
            logger.warning(f"⚠️  Unknown event type: {event.event_type}")
            raise HTTPException(
                status_code=400,
                detail=f"Unknown event type: {event.event_type}"
            )
        
        # 5. Немедленно вернуть 200 OK
        response = WebhookResponse(
            success=True,
            message=f"Webhook received and queued for processing",
            event_id=event.event_id,
            task_id=task.id if task else None
        )
        
        logger.success(f"✅ Webhook queued: {event.event_type} (task: {task.id if task else 'N/A'})")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Webhook processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Webhook processing failed: {str(e)}"
        )


@router.get("/health")
async def webhook_health_check():
    """
    Проверка здоровья webhook endpoint.
    
    Returns:
        Статус webhook сервиса
    """
    return {
        "status": "healthy",
        "service": "webhooks",
        "message": "Webhook endpoint is ready to receive events"
    }


@router.post("/test", response_model=WebhookResponse)
async def test_webhook(event: WebhookEvent) -> WebhookResponse:
    """
    Тестовый endpoint для проверки webhook обработки (без signature валидации).
    
    Args:
        event: Webhook событие
        
    Returns:
        Ответ с подтверждением
    """
    logger.info(f"🧪 Test webhook: {event.event_type} (ID: {event.event_id})")
    
    # Отправить в Celery
    task = None
    event_data = event.data.model_dump()
    
    if event.event_type == WebhookEventType.PRODUCT_CREATED:
        task = process_product_created.delay(event_data)
    elif event.event_type == WebhookEventType.PRODUCT_UPDATED:
        task = process_product_updated.delay(event_data)
    elif event.event_type == WebhookEventType.PRODUCT_DELETED:
        task = process_product_deleted.delay(event_data)
    elif event.event_type == WebhookEventType.PRODUCT_IMAGE_UPDATED:
        task = process_product_image_updated.delay(event_data)
    
    return WebhookResponse(
        success=True,
        message="Test webhook processed",
        event_id=event.event_id,
        task_id=task.id if task else None
    )

