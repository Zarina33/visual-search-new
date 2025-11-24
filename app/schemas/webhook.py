"""
Pydantic schemas for webhook events from BakaiMarket.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class WebhookEventType(str, Enum):
    """Типы webhook событий."""
    PRODUCT_CREATED = "product.created"
    PRODUCT_UPDATED = "product.updated"
    PRODUCT_DELETED = "product.deleted"
    PRODUCT_IMAGE_UPDATED = "product.image.updated"


class ProductWebhookData(BaseModel):
    """Данные товара в webhook событии."""
    product_id: str = Field(..., description="ID товара в BakaiMarket")
    title: Optional[str] = Field(None, description="Название товара")
    description: Optional[str] = Field(None, description="Описание товара")
    category: Optional[str] = Field(None, description="Категория")
    price: Optional[float] = Field(None, description="Цена")
    currency: Optional[str] = Field(None, description="Валюта")
    image_url: Optional[str] = Field(None, description="URL изображения")
    image_key: Optional[str] = Field(None, description="S3 ключ изображения")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Дополнительные данные")


class WebhookEvent(BaseModel):
    """Webhook событие от BakaiMarket."""
    event_type: WebhookEventType = Field(..., description="Тип события")
    event_id: str = Field(..., description="Уникальный ID события")
    timestamp: datetime = Field(..., description="Время события")
    data: ProductWebhookData = Field(..., description="Данные события")
    signature: Optional[str] = Field(None, description="HMAC подпись для валидации")


class WebhookResponse(BaseModel):
    """Ответ на webhook запрос."""
    success: bool = Field(..., description="Успешность обработки")
    message: str = Field(..., description="Сообщение")
    event_id: str = Field(..., description="ID обработанного события")
    task_id: Optional[str] = Field(None, description="ID фоновой задачи Celery")

