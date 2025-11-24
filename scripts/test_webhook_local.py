#!/usr/bin/env python3
"""
Локальное тестирование webhook API.

Имитирует запросы от BakaiMarket для проверки работы webhooks.
"""
import asyncio
import sys
from pathlib import Path
import httpx
import json
import hmac
import hashlib
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.config import settings


API_URL = "http://localhost:8000"


def generate_signature(payload: dict, secret: str) -> str:
    """Генерировать HMAC-SHA256 подпись."""
    body = json.dumps(payload, separators=(',', ':'))
    signature = hmac.new(
        secret.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


async def test_webhook_health():
    """Тест health endpoint."""
    print("\n" + "=" * 70)
    print("🏥 ТЕСТ 1: Webhook Health Check")
    print("=" * 70)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_URL}/api/v1/webhooks/health")
            
            if response.status_code == 200:
                data = response.json()
                logger.success(f"✅ Health check passed: {data['status']}")
                print(f"Response: {json.dumps(data, indent=2)}")
                return True
            else:
                logger.error(f"❌ Health check failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False


async def test_webhook_without_signature():
    """Тест без подписи (test endpoint)."""
    print("\n" + "=" * 70)
    print("🧪 ТЕСТ 2: Webhook без подписи (test endpoint)")
    print("=" * 70)
    
    payload = {
        "event_type": "product.created",
        "event_id": "test_local_001",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": {
            "product_id": "test_12345",
            "title": "Тестовый товар",
            "description": "Локальный тест webhook",
            "category": "test",
            "price": 1000.00,
            "currency": "KGS",
            "image_key": "test/test_image.jpg"
        }
    }
    
    print(f"\nPayload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{API_URL}/api/v1/webhooks/test",
                json=payload
            )
            
            print(f"\nStatus Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.success(f"✅ Webhook accepted!")
                print(f"\nResponse:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                
                if data.get('task_id'):
                    logger.info(f"📋 Celery task ID: {data['task_id']}")
                    logger.info("💡 Проверьте логи Celery для статуса обработки")
                
                return True
            else:
                logger.error(f"❌ Webhook rejected: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False


async def test_webhook_with_signature():
    """Тест с подписью (production endpoint)."""
    print("\n" + "=" * 70)
    print("🔒 ТЕСТ 3: Webhook с HMAC подписью (production endpoint)")
    print("=" * 70)
    
    # Проверить что секрет настроен
    if not settings.webhook_secret:
        logger.warning("⚠️  WEBHOOK_SECRET не настроен в .env!")
        logger.info("💡 Для теста используем временный секрет")
        secret = "test_secret_for_local_testing"
    else:
        secret = settings.webhook_secret
        logger.info(f"🔑 Используем секрет из .env (длина: {len(secret)} символов)")
    
    payload = {
        "event_type": "product.image.updated",
        "event_id": "test_local_002",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": {
            "product_id": "test_67890",
            "title": "Товар с новым изображением",
            "image_key": "test/new_image.jpg"
        }
    }
    
    # Генерировать подпись
    signature = generate_signature(payload, secret)
    
    print(f"\nPayload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"\nSignature: sha256={signature[:20]}...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{API_URL}/api/v1/webhooks/bakai",
                json=payload,
                headers={
                    "X-Webhook-Signature": f"sha256={signature}"
                }
            )
            
            print(f"\nStatus Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.success(f"✅ Webhook with signature accepted!")
                print(f"\nResponse:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                
                if data.get('task_id'):
                    logger.info(f"📋 Celery task ID: {data['task_id']}")
                
                return True
            elif response.status_code == 401:
                logger.error(f"❌ Invalid signature!")
                logger.info("💡 Проверьте что WEBHOOK_SECRET одинаковый с обеих сторон")
                print(f"Response: {response.text}")
                return False
            else:
                logger.error(f"❌ Webhook rejected: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False


async def test_all_event_types():
    """Тест всех типов событий."""
    print("\n" + "=" * 70)
    print("📦 ТЕСТ 4: Все типы событий")
    print("=" * 70)
    
    events = [
        {
            "event_type": "product.created",
            "event_id": "test_create_001",
            "data": {
                "product_id": "new_product_123",
                "title": "Новый товар",
                "image_key": "123/image.jpg"
            }
        },
        {
            "event_type": "product.updated",
            "event_id": "test_update_001",
            "data": {
                "product_id": "existing_product_456",
                "title": "Обновленное название",
                "price": 2000.00
            }
        },
        {
            "event_type": "product.deleted",
            "event_id": "test_delete_001",
            "data": {
                "product_id": "old_product_789"
            }
        },
        {
            "event_type": "product.image.updated",
            "event_id": "test_image_001",
            "data": {
                "product_id": "product_999",
                "image_key": "999/new_image.jpg"
            }
        }
    ]
    
    results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for event in events:
            event["timestamp"] = datetime.utcnow().isoformat() + "Z"
            
            print(f"\n📨 Отправка: {event['event_type']}")
            
            try:
                response = await client.post(
                    f"{API_URL}/api/v1/webhooks/test",
                    json=event
                )
                
                if response.status_code == 200:
                    logger.success(f"✅ {event['event_type']} - OK")
                    results.append(True)
                else:
                    logger.error(f"❌ {event['event_type']} - Failed ({response.status_code})")
                    results.append(False)
                    
            except Exception as e:
                logger.error(f"❌ {event['event_type']} - Error: {e}")
                results.append(False)
    
    success_rate = (sum(results) / len(results)) * 100
    print(f"\n📊 Успешность: {sum(results)}/{len(results)} ({success_rate:.0f}%)")
    
    return all(results)


async def test_invalid_requests():
    """Тест невалидных запросов."""
    print("\n" + "=" * 70)
    print("🚫 ТЕСТ 5: Невалидные запросы")
    print("=" * 70)
    
    test_cases = [
        {
            "name": "Без event_type",
            "payload": {
                "event_id": "test_001",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": {"product_id": "123"}
            },
            "expected_status": 422
        },
        {
            "name": "Без product_id",
            "payload": {
                "event_type": "product.created",
                "event_id": "test_002",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": {"title": "Test"}
            },
            "expected_status": 422
        },
        {
            "name": "Неизвестный event_type",
            "payload": {
                "event_type": "product.unknown",
                "event_id": "test_003",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "data": {"product_id": "123"}
            },
            "expected_status": 400
        }
    ]
    
    results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for test_case in test_cases:
            print(f"\n🧪 Тест: {test_case['name']}")
            
            try:
                response = await client.post(
                    f"{API_URL}/api/v1/webhooks/test",
                    json=test_case['payload']
                )
                
                if response.status_code == test_case['expected_status']:
                    logger.success(f"✅ Правильно отклонен ({response.status_code})")
                    results.append(True)
                else:
                    logger.warning(f"⚠️  Неожиданный статус: {response.status_code} (ожидался {test_case['expected_status']})")
                    results.append(False)
                    
            except Exception as e:
                logger.error(f"❌ Error: {e}")
                results.append(False)
    
    success_rate = (sum(results) / len(results)) * 100
    print(f"\n📊 Успешность: {sum(results)}/{len(results)} ({success_rate:.0f}%)")
    
    return all(results)


async def main():
    """Главная функция."""
    print("\n" + "=" * 70)
    print("  🧪 ЛОКАЛЬНОЕ ТЕСТИРОВАНИЕ WEBHOOK API")
    print("=" * 70)
    
    print(f"\n🔗 API URL: {API_URL}")
    print(f"🔑 Webhook Secret: {'настроен' if settings.webhook_secret else 'НЕ настроен'}")
    
    # Проверить что API запущен
    print("\n" + "=" * 70)
    print("🔍 Проверка доступности API")
    print("=" * 70)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/api/v1/health", timeout=5.0)
            if response.status_code == 200:
                logger.success("✅ API доступен")
            else:
                logger.error("❌ API недоступен")
                print("\n💡 Запустите API:")
                print("   poetry run uvicorn app.api.main:app --reload")
                return
    except Exception as e:
        logger.error(f"❌ API недоступен: {e}")
        print("\n💡 Запустите API:")
        print("   poetry run uvicorn app.api.main:app --reload")
        return
    
    # Запустить тесты
    results = []
    
    results.append(await test_webhook_health())
    results.append(await test_webhook_without_signature())
    results.append(await test_webhook_with_signature())
    results.append(await test_all_event_types())
    results.append(await test_invalid_requests())
    
    # Итоги
    print("\n" + "=" * 70)
    print("📊 ИТОГИ")
    print("=" * 70)
    
    total = len(results)
    passed = sum(results)
    
    print(f"\n✅ Пройдено: {passed}/{total}")
    print(f"❌ Провалено: {total - passed}/{total}")
    print(f"📈 Успешность: {(passed/total*100):.0f}%")
    
    if all(results):
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\n💡 Следующие шаги:")
        print("   1. Webhook API готов к использованию")
        print("   2. Настройте домен или ngrok для production")
        print("   3. Передайте URL и секрет команде BakaiMarket")
    else:
        print("\n⚠️  НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        print("\n💡 Проверьте:")
        print("   1. API запущен: poetry run uvicorn app.api.main:app --reload")
        print("   2. Celery запущен: poetry run celery -A app.workers.celery_app worker")
        print("   3. WEBHOOK_SECRET настроен в .env")
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, format="<level>{message}</level>", level="INFO")
    
    asyncio.run(main())

