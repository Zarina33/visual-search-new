# 🧪 Руководство по тестированию системы

**Пошаговая инструкция для проверки работоспособности всех компонентов**

---

## 📋 Содержание

1. [Этап 1: Docker контейнеры](#этап-1-docker-контейнеры)
2. [Этап 2: PostgreSQL](#этап-2-postgresql)
3. [Этап 3: Qdrant](#этап-3-qdrant)
4. [Этап 4: Redis](#этап-4-redis)
5. [Этап 5: Python зависимости](#этап-5-python-зависимости)
6. [Этап 6: Инициализация баз](#этап-6-инициализация-баз)
7. [Этап 7: CLIP модель](#этап-7-clip-модель)
8. [Этап 8: API сервер](#этап-8-api-сервер)
9. [Этап 9: Поиск по изображению](#этап-9-поиск-по-изображению)
10. [Этап 10: Поиск по тексту](#этап-10-поиск-по-тексту)
11. [Этап 11: Webhooks](#этап-11-webhooks)
12. [Этап 12: Celery Worker](#этап-12-celery-worker)
13. [Этап 13: Unit тесты](#этап-13-unit-тесты)
14. [Этап 14: E2E тесты](#этап-14-e2e-тесты)

---

## Этап 1: Docker контейнеры

### 1.1. Запустить Docker Compose

```bash
cd /home/user/Desktop/BakaiMarket/visual-search-project
docker-compose up -d
```

**Ожидаемый вывод:**
```
Creating network "visual-search-project_visual_search_network" ... done
Creating visual_search_postgres ... done
Creating visual_search_redis    ... done
Creating visual_search_qdrant   ... done
```

### 1.2. Подождать инициализации

```bash
sleep 10
```

### 1.3. Проверить статус

```bash
docker-compose ps
```

**Ожидаемый вывод (все контейнеры должны быть "Up"):**
```
         Name                       Command               State                    Ports                  
----------------------------------------------------------------------------------------------------------
visual_search_postgres   docker-entrypoint.sh postgres    Up      0.0.0.0:5432->5432/tcp
visual_search_qdrant     ./entrypoint.sh                  Up      0.0.0.0:6333->6333/tcp, 0.0.0.0:6334->6334/tcp
visual_search_redis      docker-entrypoint.sh redis ...   Up      0.0.0.0:6379->6379/tcp
```

### ✅ Результат: Все 3 контейнера работают

---

## Этап 2: PostgreSQL

### 2.1. Проверить подключение

```bash
docker exec visual_search_postgres pg_isready -U bakaimarket
```

**Ожидаемый вывод:**
```
/var/run/postgresql:5432 - accepting connections
```

### 2.2. Подключиться к базе

```bash
docker exec -it visual_search_postgres psql -U bakaimarket -d market
```

### 2.3. Выполнить тестовые команды

```sql
-- Проверить версию
SELECT version();

-- Список таблиц
\dt

-- Выход
\q
```

### 2.4. Быстрая проверка

```bash
# Проверить таблицы
docker exec visual_search_postgres psql -U bakaimarket -d market -c "\dt"

# Количество продуктов
docker exec visual_search_postgres psql -U bakaimarket -d market -c "SELECT COUNT(*) FROM products;"
```

### ✅ Результат: PostgreSQL работает и принимает подключения

---

## Этап 3: Qdrant

### 3.1. Проверить API

```bash
curl http://localhost:6333/
```

**Ожидаемый вывод:**
```json
{"title":"qdrant - vector search engine","version":"..."}
```

### 3.2. Список коллекций

```bash
curl http://localhost:6333/collections
```

**Ожидаемый вывод:**
```json
{"result":{"collections":[...]},"status":"ok","time":0.000...}
```

### 3.3. Открыть UI в браузере

```
http://localhost:6333/dashboard
```

### 3.4. Проверить метрики

```bash
curl http://localhost:6333/metrics
```

### ✅ Результат: Qdrant работает и доступен

---

## Этап 4: Redis

### 4.1. Проверить подключение

```bash
docker exec visual_search_redis redis-cli ping
```

**Ожидаемый вывод:**
```
PONG
```

### 4.2. Подключиться к Redis CLI

```bash
docker exec -it visual_search_redis redis-cli
```

### 4.3. Выполнить тестовые команды

```redis
# Проверка
PING

# Установить значение
SET test_key "Hello Redis"

# Получить значение
GET test_key

# Удалить
DEL test_key

# Выход
exit
```

### ✅ Результат: Redis работает

---

## Этап 5: Python зависимости

### 5.1. Проверить Poetry

```bash
poetry --version
```

**Если не установлен:**
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 5.2. Установить зависимости

```bash
poetry install
```

**Это займет несколько минут (особенно PyTorch)**

### 5.3. Активировать окружение

```bash
poetry shell
```

### 5.4. Проверить установку

```bash
# Проверить Python
python --version

# Список пакетов
poetry show
```

### ✅ Результат: Все зависимости установлены

---

## Этап 6: Инициализация баз

### 6.1. Инициализировать базы данных

```bash
poetry run python scripts/init_databases.py
```

**Ожидаемый вывод:**
```
============================================================
Initializing Databases for Visual Search Project
============================================================

Connecting to PostgreSQL...
Creating tables...
✓ Tables created successfully

Connecting to Qdrant...
Creating collection...
✓ Qdrant collection created successfully

============================================================
Setup complete!
============================================================
```

### 6.2. Проверить таблицы

```bash
docker exec visual_search_postgres psql -U bakaimarket -d market -c "\dt"
```

**Ожидаемый вывод:**
```
              List of relations
 Schema |     Name     | Type  |    Owner    
--------+--------------+-------+-------------
 public | products     | table | bakaimarket
 public | search_logs  | table | bakaimarket
```

### 6.3. Проверить коллекцию Qdrant

```bash
curl http://localhost:6333/collections/product_embeddings
```

### ✅ Результат: Базы данных инициализированы

---

## Этап 7: CLIP модель

### 7.1. Тест загрузки модели

```bash
poetry run python test_clip_gpu.py
```

**Ожидаемый вывод:**
```
============================================================
Testing CLIP Model
============================================================

Loading CLIP model...
✓ Model loaded successfully
Device: cuda
Embedding dimension: 512

Testing text embedding...
✓ Text embedding generated: (512,)

Testing image embedding...
✓ Image embedding generated: (512,)

============================================================
All tests passed!
============================================================
```

### 7.2. Проверить GPU (если есть)

```bash
nvidia-smi
```

### ✅ Результат: CLIP модель работает

---

## Этап 8: API сервер

### 8.1. Запустить API

```bash
poetry run uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Ожидаемый вывод:**
```
INFO:     Will watch for changes in these directories: ['/home/user/Desktop/BakaiMarket/visual-search-project']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [XXXXX] using StatReload
INFO:     Started server process [XXXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Оставьте этот терминал открытым!**

### 8.2. Проверить health endpoint (в новом терминале)

```bash
curl http://localhost:8000/api/v1/health
```

**Ожидаемый вывод:**
```json
{
  "status": "healthy",
  "service": "visual-search-project",
  "version": "0.1.0"
}
```

### 8.3. Детальная проверка

```bash
curl http://localhost:8000/api/v1/health/detailed
```

**Ожидаемый вывод:**
```json
{
  "status": "healthy",
  "service": "visual-search-project",
  "version": "0.1.0",
  "components": {
    "postgres": "healthy",
    "qdrant": "healthy"
  }
}
```

### 8.4. Открыть Swagger UI

```
http://localhost:8000/docs
```

### ✅ Результат: API сервер работает

---

## Этап 9: Поиск по изображению

### 9.1. Загрузить demo данные (если еще не загружены)

```bash
poetry run python scripts/load_demo_products.py
```

### 9.2. Тест поиска с тестовым изображением

```bash
curl -X POST "http://localhost:8000/api/v1/search/by-image?limit=5" \
  -F "image=@test_images/red_square.jpg"
```

**Ожидаемый вывод:**
```json
{
  "query_time_ms": 176,
  "results_count": 5,
  "results": [
    {
      "product_id": "...",
      "external_id": "...",
      "title": "...",
      "image_url": "...",
      "similarity_score": 0.95
    }
  ]
}
```

### 9.3. Тест с реальным товаром

```bash
# Найти товар в базе
docker exec visual_search_postgres psql -U bakaimarket -d market -c "SELECT id FROM products LIMIT 1;"

# Использовать его фото
curl -X POST "http://localhost:8000/api/v1/search/by-image?limit=5" \
  -F "image=@/tmp/bakai_products/118133_87295487377438.jpeg" | python3 -m json.tool
```

### 9.4. Запустить полный тест

```bash
poetry run python scripts/test_search_api.py
```

### ✅ Результат: Поиск по изображению работает

---

## Этап 10: Поиск по тексту

### 10.1. Простой текстовый запрос

```bash
curl -X POST "http://localhost:8000/api/v1/search/by-text" \
  -H "Content-Type: application/json" \
  -d '{"query": "телефон", "limit": 5}'
```

**Ожидаемый вывод:**
```json
{
  "query_time_ms": 134,
  "results_count": 5,
  "results": [...]
}
```

### 10.2. Тест с минимальным порогом

```bash
curl -X POST "http://localhost:8000/api/v1/search/by-text" \
  -H "Content-Type: application/json" \
  -d '{"query": "красный диван", "limit": 10, "min_similarity": 0.7}'
```

### 10.3. Поиск похожих товаров

```bash
curl "http://localhost:8000/api/v1/search/similar/118133?limit=5"
```

### ✅ Результат: Текстовый поиск работает

---

## Этап 11: Webhooks

### 11.1. Проверить webhook health

```bash
curl http://localhost:8000/api/v1/webhooks/health
```

**Ожидаемый вывод:**
```json
{
  "status": "healthy",
  "service": "webhooks",
  "message": "Webhook endpoint is ready to receive events"
}
```

### 11.2. Тест webhook (без подписи)

```bash
curl -X POST "http://localhost:8000/api/v1/webhooks/test" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "product.created",
    "event_id": "test_001",
    "timestamp": "2025-11-12T10:00:00Z",
    "data": {
      "product_id": "12345",
      "title": "Тестовый товар",
      "image_key": "12345/test.jpg"
    }
  }'
```

**Ожидаемый вывод:**
```json
{
  "success": true,
  "message": "Test webhook processed",
  "event_id": "test_001",
  "task_id": "..."
}
```

### 11.3. Запустить полный тест webhook

```bash
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

### ✅ Результат: Webhooks работают

---

## Этап 12: Celery Worker

### 12.1. Запустить Celery worker (в новом терминале)

```bash
cd /home/user/Desktop/BakaiMarket/visual-search-project
poetry shell
celery -A app.workers.celery_app worker --loglevel=info
```

**Ожидаемый вывод:**
```
 -------------- celery@hostname v5.3.4 (emerald-rush)
--- ***** ----- 
-- ******* ---- Linux-6.14.0-33-generic-x86_64-with-glibc2.35 2025-11-12 15:00:00
- *** --- * --- 
- ** ---------- [config]
- ** ---------- .> app:         visual_search_workers:0x...
- ** ---------- .> transport:   redis://localhost:6379/0
- ** ---------- .> results:     redis://localhost:6379/0
- *** --- * --- .> concurrency: 4 (prefork)
-- ******* ---- .> task events: OFF
--- ***** ----- 
 -------------- [queues]
                .> celery           exchange=celery(direct) key=celery

[tasks]
  . app.workers.webhook_tasks.process_product_created
  . app.workers.webhook_tasks.process_product_deleted
  . app.workers.webhook_tasks.process_product_image_updated
  . app.workers.webhook_tasks.process_product_updated

[2025-11-12 15:00:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2025-11-12 15:00:00,000: INFO/MainProcess] mingle: searching for neighbors
[2025-11-12 15:00:00,000: INFO/MainProcess] mingle: all alone
[2025-11-12 15:00:00,000: INFO/MainProcess] celery@hostname ready.
```

### 12.2. Проверить обработку задач

Отправьте webhook (из Этапа 11.2) и проверьте логи Celery worker.

### ✅ Результат: Celery worker работает

---

## Этап 13: Unit тесты

### 13.1. Запустить все тесты

```bash
poetry run pytest -v
```

**Ожидаемый вывод:**
```
============================= test session starts ==============================
platform linux -- Python 3.12.x, pytest-7.4.3, pluggy-1.3.0
rootdir: /home/user/Desktop/BakaiMarket/visual-search-project
collected X items

tests/test_api.py::test_health_endpoint PASSED                           [ 10%]
tests/test_api.py::test_detailed_health PASSED                           [ 20%]
tests/test_api.py::test_search_by_image PASSED                           [ 30%]
tests/test_api.py::test_search_by_text PASSED                            [ 40%]
tests/test_clip_model.py::test_model_loading PASSED                      [ 50%]
tests/test_clip_model.py::test_text_embedding PASSED                     [ 60%]
tests/test_clip_model.py::test_image_embedding PASSED                    [ 70%]
tests/test_clip_model.py::test_batch_processing PASSED                   [ 80%]
tests/test_database_modules.py::test_postgres_connection PASSED          [ 90%]
tests/test_database_modules.py::test_qdrant_connection PASSED            [100%]

============================== X passed in X.XXs ===============================
```

### 13.2. Тесты с покрытием

```bash
poetry run pytest --cov=app --cov-report=term
```

**Ожидаемый вывод:**
```
---------- coverage: platform linux, python 3.12.x -----------
Name                                Stmts   Miss  Cover
-------------------------------------------------------
app/__init__.py                         0      0   100%
app/api/main.py                        45      0   100%
app/api/routes/health.py               20      0   100%
app/api/routes/search.py               65      0   100%
app/db/postgres.py                     80      0   100%
app/db/qdrant.py                       90      0   100%
app/models/clip_model.py              120      0   100%
-------------------------------------------------------
TOTAL                                 420      0   100%
```

### ✅ Результат: Все unit тесты проходят

---

## Этап 14: E2E тесты

### 14.1. Запустить E2E тесты

```bash
poetry run pytest tests/test_e2e.py -v
```

**Ожидаемый вывод:**
```
tests/test_e2e.py::test_complete_search_flow PASSED                      [ 25%]
tests/test_e2e.py::test_webhook_to_search_flow PASSED                    [ 50%]
tests/test_e2e.py::test_product_lifecycle PASSED                         [ 75%]
tests/test_e2e.py::test_concurrent_searches PASSED                       [100%]

============================== 4 passed in X.XXs ================================
```

### 14.2. Полный системный тест

```bash
poetry run python scripts/test_complete_system.py
```

**Ожидаемый вывод:**
```
============================================================
Complete System Test
============================================================

Test 1: Docker Services
✓ PostgreSQL is running
✓ Redis is running
✓ Qdrant is running

Test 2: Database Connectivity
✓ PostgreSQL connection successful
✓ Qdrant connection successful

Test 3: API Endpoints
✓ Health check passed
✓ Detailed health check passed

Test 4: Search Functionality
✓ Image search working (176ms)
✓ Text search working (134ms)
✓ Similar products search working (59ms)

Test 5: Webhooks
✓ Webhook health check passed
✓ Test webhook processed

Test 6: Data Integrity
✓ Products count: 76462
✓ Qdrant vectors count: 76462
✓ Data consistency verified

============================================================
All tests passed! ✓
System is fully operational.
============================================================
```

### ✅ Результат: Вся система работает корректно

---

## 📊 Итоговый чеклист

- [ ] **Этап 1:** Docker контейнеры запущены
- [ ] **Этап 2:** PostgreSQL работает
- [ ] **Этап 3:** Qdrant работает
- [ ] **Этап 4:** Redis работает
- [ ] **Этап 5:** Python зависимости установлены
- [ ] **Этап 6:** Базы данных инициализированы
- [ ] **Этап 7:** CLIP модель загружается
- [ ] **Этап 8:** API сервер работает
- [ ] **Этап 9:** Поиск по изображению работает
- [ ] **Этап 10:** Поиск по тексту работает
- [ ] **Этап 11:** Webhooks работают
- [ ] **Этап 12:** Celery worker работает
- [ ] **Этап 13:** Unit тесты проходят
- [ ] **Этап 14:** E2E тесты проходят

---

## 🔧 Полезные команды

### Остановка сервисов

```bash
# Остановить Docker
docker-compose down

# Остановить API (Ctrl+C в терминале)

# Остановить Celery (Ctrl+C в терминале)
```

### Перезапуск сервисов

```bash
# Перезапустить все Docker контейнеры
docker-compose restart

# Перезапустить конкретный сервис
docker-compose restart postgres
docker-compose restart redis
docker-compose restart qdrant
```

### Просмотр логов

```bash
# Логи всех сервисов
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f qdrant

# Логи приложения
tail -f logs/app_$(date +%Y-%m-%d).log
tail -f logs/errors_$(date +%Y-%m-%d).log
```

### Очистка данных

```bash
# Удалить все контейнеры и volumes
docker-compose down -v

# Очистить Python кэш
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
```

---

## 🐛 Решение проблем

### Порты уже заняты

```bash
# Проверить занятые порты
sudo lsof -i :5432  # PostgreSQL
sudo lsof -i :6379  # Redis
sudo lsof -i :6333  # Qdrant
sudo lsof -i :8000  # API

# Остановить конфликтующие процессы или изменить порты в .env
```

### Docker контейнеры не запускаются

```bash
# Проверить логи
docker-compose logs

# Пересоздать контейнеры
docker-compose down
docker-compose up -d --force-recreate
```

### Poetry не находит зависимости

```bash
# Обновить Poetry
poetry self update

# Очистить кэш
poetry cache clear pypi --all

# Переустановить зависимости
rm -rf .venv
poetry install
```

### CLIP модель не загружается

```bash
# Проверить интернет-соединение
# Модель загружается из HuggingFace при первом запуске

# Проверить место на диске
df -h

# Проверить логи API сервера
```

---

**🎉 Тестирование завершено! Система готова к использованию!**

