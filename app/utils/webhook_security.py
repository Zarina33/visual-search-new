"""
Webhook security utilities for signature validation.
"""
import hmac
import hashlib
from typing import Optional
from loguru import logger
from app.config import settings


def generate_signature(payload: str, secret: str) -> str:
    """
    Генерировать HMAC-SHA256 подпись для payload.
    
    Args:
        payload: JSON строка payload
        secret: Секретный ключ
        
    Returns:
        Hex строка подписи
    """
    signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_signature(payload: str, signature: str, secret: Optional[str] = None) -> bool:
    """
    Проверить HMAC-SHA256 подпись webhook запроса.
    
    Args:
        payload: JSON строка payload
        signature: Подпись из заголовка
        secret: Секретный ключ (по умолчанию из settings)
        
    Returns:
        True если подпись валидна
    """
    if secret is None:
        secret = settings.webhook_secret
    
    # Если секрет не настроен, пропускаем валидацию (только для разработки!)
    if not secret:
        logger.warning("⚠️  Webhook secret not configured! Skipping signature validation.")
        return True
    
    expected_signature = generate_signature(payload, secret)
    
    # Безопасное сравнение для защиты от timing attacks
    is_valid = hmac.compare_digest(signature, expected_signature)
    
    if not is_valid:
        logger.warning(f"❌ Invalid webhook signature! Expected: {expected_signature[:10]}..., Got: {signature[:10]}...")
    
    return is_valid

