# 🔗 Настройка Webhook для BakaiMarket

**Пошаговая инструкция по настройке автоматической синхронизации через webhooks**

---

## 📋 Содержание

1. [Что такое Webhook](#что-такое-webhook)
2. [Подготовка на вашей стороне](#подготовка-на-вашей-стороне)
3. [Информация для BakaiMarket](#информация-для-bakaimarket)
4. [Варианты развертывания](#варианты-развертывания)
5. [Тестирование](#тестирование)
6. [Безопасность](#безопасность)
7. [Мониторинг](#мониторинг)

---

## 🎯 Что такое Webhook

**Webhook** - это механизм автоматического уведомления вашей системы об изменениях в BakaiMarket.

### Как это работает:

```
BakaiMarket                          Ваша система
    │                                      │
    │  Товар изменился                     │
    │  (создан/обновлен/удален)            │
    │                                      │
    │  ─────── POST запрос ──────>         │
    │  (с данными о товаре)                │
    │                                      │
    │                              Обработка в фоне
    │                              (Celery worker)
    │                                      │
    │                              Обновление БД
    │                              (PostgreSQL + Qdrant)
    │                                      │
    │  <────── 200 OK ────────             │
    │                                      │
```

### Зачем это нужно:

- ✅ **Автоматическая синхронизация** - не нужно вручную обновлять данные
- ✅ **Актуальность** - изменения применяются сразу
- ✅ **Экономия ресурсов** - не нужно постоянно опрашивать API

---

## 🔧 Подготовка на вашей стороне

### Шаг 1: Сгенерировать секретный ключ

```bash
# Сгенерировать случайный секрет (32 байта)
openssl rand -hex 32
```

**Пример вывода:**
```
a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2
```

**Сохраните этот ключ!** Он понадобится для настройки.

### Шаг 2: Добавить секрет в .env

```bash
nano .env
```

Добавьте строку:
```bash
WEBHOOK_SECRET=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2
```

### Шаг 3: Перезапустить API

```bash
# Если используете systemd
sudo systemctl restart visual-search-api
sudo systemctl restart visual-search-celery

# Или вручную (Ctrl+C и заново)
poetry run uvicorn app.api.main:app --host 0.0.0.0 --port 8008
```

### Шаг 4: Проверить что webhook endpoint работает

```bash
curl http://localhost:8008/api/v1/webhooks/health
```

**Ожидаемый ответ:**
```json
{
  "status": "healthy",
  "service": "webhooks",
  "message": "Webhook endpoint is ready to receive events"
}
```

---

## 📤 Информация для BakaiMarket

### Что нужно передать команде BakaiMarket:

#### 1. **Webhook URL**

**Формат:**
```
https://your-domain.com/api/v1/webhooks/bakai
```

**Примеры:**
- Production: `https://visual-search.bakaimarket.kg/api/v1/webhooks/bakai`
- Staging: `https://staging.visual-search.bakaimarket.kg/api/v1/webhooks/bakai`

**⚠️ ВАЖНО:** URL должен быть доступен из интернета!

#### 2. **Webhook Secret**

Тот секрет, который вы сгенерировали в Шаге 1:
```
a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2
```

**⚠️ ВАЖНО:** Передавайте секрет безопасным способом (не в открытом виде)!

#### 3. **Поддерживаемые события**

Ваша система поддерживает следующие типы событий:

| Событие | Описание | Когда отправлять |
|---------|----------|------------------|
| `product.created` | Новый товар создан | При добавлении нового товара |
| `product.updated` | Товар обновлен | При изменении названия, описания, цены |
| `product.deleted` | Товар удален | При удалении товара |
| `product.image.updated` | Изображение обновлено | При изменении главного изображения |

#### 4. **Формат запроса**

**HTTP Method:** `POST`

**Headers:**
```
Content-Type: application/json
X-Webhook-Signature: sha256=<hmac_signature>
```

**Body (JSON):**
```json
{
  "event_type": "product.created",
  "event_id": "unique_event_id_123",
  "timestamp": "2025-11-12T10:00:00Z",
  "data": {
    "product_id": "12345",
    "title": "Название товара",
    "description": "Описание товара",
    "category": "Электроника",
    "price": 15000.0,
    "currency": "KGS",
    "image_key": "12345/main.jpg"
  }
}
```

#### 5. **Подпись (HMAC-SHA256)**

**Алгоритм подписи:**

```python
import hmac
import hashlib
import json

# Данные
secret = "your_webhook_secret"
payload = json.dumps(event_data)

# Создать подпись
signature = hmac.new(
    secret.encode('utf-8'),
    payload.encode('utf-8'),
    hashlib.sha256
).hexdigest()

# Заголовок
headers = {
    "X-Webhook-Signature": f"sha256={signature}"
}
```

**Пример на bash:**
```bash
SECRET="your_webhook_secret"
PAYLOAD='{"event_type":"product.created",...}'

SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

curl -X POST "https://your-domain.com/api/v1/webhooks/bakai" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=$SIGNATURE" \
  -d "$PAYLOAD"
```

#### 6. **Ожидаемый ответ**

**Успешная обработка (200 OK):**
```json
{
  "success": true,
  "message": "Webhook received and queued for processing",
  "event_id": "unique_event_id_123",
  "task_id": "celery-task-uuid"
}
```

**Ошибки:**
- `401 Unauthorized` - Неверная подпись
- `400 Bad Request` - Неверный формат данных
- `422 Unprocessable Entity` - Ошибка валидации

---

## 🌐 Варианты развертывания

### Вариант 1: С доменом (Production) ✅ Рекомендуется

**Что нужно:**
1. Купить домен (например, `visual-search.bakaimarket.kg`)
2. Настроить DNS (A-запись на IP вашего сервера)
3. Настроить Nginx (reverse proxy)
4. Получить SSL сертификат (Let's Encrypt)

**Преимущества:**
- ✅ Безопасное HTTPS соединение
- ✅ Красивый URL
- ✅ Готово для production

**Инструкция:** См. `DEPLOYMENT.md` → "Настройка Nginx" и "SSL сертификат"

**Итоговый URL:**
```
https://visual-search.bakaimarket.kg/api/v1/webhooks/bakai
```

---

### Вариант 2: Через ngrok (Тестирование) 🧪

**Что нужно:**
1. Установить ngrok
2. Запустить туннель

**Шаги:**

```bash
# 1. Скачать ngrok
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xvzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/

# 2. Зарегистрироваться на ngrok.com и получить authtoken
ngrok config add-authtoken YOUR_AUTH_TOKEN

# 3. Запустить туннель
ngrok http 8008
```

**Вывод ngrok:**
```
Forwarding    https://abc123.ngrok.io -> http://localhost:8008
```

**Временный URL для BakaiMarket:**
```
https://abc123.ngrok.io/api/v1/webhooks/bakai
```

**⚠️ Недостатки:**
- URL меняется при каждом перезапуске
- Только для тестирования
- Не подходит для production

---

### Вариант 3: По IP адресу (Временное решение)

**Что нужно:**
1. Публичный статический IP адрес
2. Открытый порт 8008 (или другой)

**URL:**
```
http://123.45.67.89:8008/api/v1/webhooks/bakai
```

**⚠️ Недостатки:**
- Нет HTTPS (небезопасно)
- Нужно открывать порт в firewall
- Не рекомендуется для production

---

## 🧪 Тестирование

### Локальное тестирование (без BakaiMarket)

```bash
# Запустить тестовый скрипт
poetry run python scripts/test_webhook_local.py
```

**Ожидаемый вывод:**
```
============================================================
Testing Webhook Endpoints
============================================================

Test 1: Webhook Health Check
✓ Webhook health check passed

Test 2: Product Created Event
✓ Product created event processed

Test 3: Product Updated Event
✓ Product updated event processed

Test 4: Product Deleted Event
✓ Product deleted event processed

Test 5: Image Updated Event
✓ Image updated event processed

============================================================
All webhook tests passed! ✓
============================================================
```

### Ручное тестирование с curl

```bash
# 1. Сгенерировать подпись
SECRET="your_webhook_secret"
PAYLOAD='{"event_type":"product.created","event_id":"test_001","timestamp":"2025-11-12T10:00:00Z","data":{"product_id":"12345","title":"Test","image_key":"12345/test.jpg"}}'

SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

# 2. Отправить запрос
curl -X POST "http://localhost:8008/api/v1/webhooks/bakai" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=$SIGNATURE" \
  -d "$PAYLOAD"
```

### Тестирование с BakaiMarket (staging)

1. Передайте команде BakaiMarket:
   - Webhook URL (staging)
   - Webhook Secret
   
2. Попросите отправить тестовое событие

3. Проверьте логи:
```bash
# Логи API
sudo journalctl -u visual-search-api -f

# Логи Celery
sudo journalctl -u visual-search-celery -f

# Логи приложения
tail -f logs/app_$(date +%Y-%m-%d).log
```

---

## 🔒 Безопасность

### 1. Защита секретного ключа

```bash
# ✅ ПРАВИЛЬНО: Хранить в .env
WEBHOOK_SECRET=a1b2c3d4e5f6g7h8i9j0...

# ❌ НЕПРАВИЛЬНО: Хардкодить в коде
secret = "a1b2c3d4e5f6g7h8i9j0..."
```

### 2. Проверка подписи

Ваша система **автоматически** проверяет подпись каждого запроса:

```python
# app/utils/webhook_security.py
def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected_signature}", signature)
```

### 3. HTTPS обязателен для production

```bash
# ✅ ПРАВИЛЬНО
https://visual-search.bakaimarket.kg/api/v1/webhooks/bakai

# ❌ НЕПРАВИЛЬНО (для production)
http://visual-search.bakaimarket.kg/api/v1/webhooks/bakai
```

### 4. Firewall

```bash
# Разрешить только HTTPS
sudo ufw allow 443/tcp

# Закрыть прямой доступ к API (если используется Nginx)
sudo ufw deny 8008/tcp
```

---

## 📊 Мониторинг

### Проверка работы webhooks

```bash
# 1. Проверить health
curl http://localhost:8008/api/v1/webhooks/health

# 2. Проверить метрики
curl http://localhost:8008/api/v1/metrics | grep webhook

# 3. Проверить логи
tail -f logs/app_$(date +%Y-%m-%d).log | grep webhook
```

### Метрики Prometheus

```bash
# Количество обработанных webhooks
visual_search_webhooks_total{event_type="product.created"} 150

# Ошибки webhooks
visual_search_webhooks_errors_total{event_type="product.created"} 2

# Время обработки
visual_search_webhook_processing_duration_seconds{event_type="product.created"} 0.234
```

### Логи

```bash
# Успешная обработка
2025-11-12 15:30:00 | INFO | Webhook received: product.created (event_id: evt_123)
2025-11-12 15:30:00 | INFO | Task queued: celery-task-uuid
2025-11-12 15:30:05 | INFO | Product created successfully: 12345

# Ошибка
2025-11-12 15:30:00 | ERROR | Invalid webhook signature
2025-11-12 15:30:00 | ERROR | Failed to process webhook: evt_456
```

---

## 📝 Чеклист настройки

### На вашей стороне:

- [ ] Сгенерирован webhook secret
- [ ] Secret добавлен в `.env`
- [ ] API перезапущен
- [ ] Webhook endpoint доступен (`/api/v1/webhooks/health`)
- [ ] Celery worker запущен
- [ ] Настроен домен (для production)
- [ ] Настроен Nginx (для production)
- [ ] Получен SSL сертификат (для production)
- [ ] Проведено локальное тестирование
- [ ] Настроен мониторинг

### Для BakaiMarket:

- [ ] Передан Webhook URL
- [ ] Передан Webhook Secret (безопасно)
- [ ] Объяснен формат запроса
- [ ] Объяснен алгоритм подписи
- [ ] Проведено тестирование на staging
- [ ] Настроена отправка событий на production

---

## 🆘 Troubleshooting

### Проблема: Webhook не приходят

```bash
# 1. Проверить что API запущен
curl http://localhost:8008/api/v1/health

# 2. Проверить что Celery работает
sudo systemctl status visual-search-celery

# 3. Проверить логи
tail -f logs/app_$(date +%Y-%m-%d).log
```

### Проблема: Ошибка 401 (Invalid signature)

```bash
# 1. Проверить что secret одинаковый на обеих сторонах
echo $WEBHOOK_SECRET

# 2. Проверить формат подписи
# Должно быть: sha256=<hex_string>

# 3. Проверить что payload не изменяется
# Подпись должна вычисляться от ТОЧНОГО JSON
```

### Проблема: Webhook обрабатывается медленно

```bash
# 1. Проверить очередь Celery
celery -A app.workers.celery_app inspect active

# 2. Увеличить количество workers
# В systemd сервисе изменить:
ExecStart=... --concurrency=8

# 3. Проверить ресурсы сервера
htop
```

---

## 📞 Контакты для BakaiMarket

**Для технических вопросов:**
- Email: your.email@example.com
- Telegram: @yourusername

**Документация:**
- Полная документация: `README.md`
- Развертывание: `DEPLOYMENT.md`
- Тестирование: `TESTING.md`

---

## 📚 Дополнительные ресурсы

- [HMAC-SHA256 на Wikipedia](https://en.wikipedia.org/wiki/HMAC)
- [Webhook Best Practices](https://docs.github.com/en/webhooks)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Ngrok Documentation](https://ngrok.com/docs)

---

**🎉 После настройки webhook ваша система будет автоматически синхронизироваться с BakaiMarket!**

*Сделано с ❤️ для BakaiMarket*

