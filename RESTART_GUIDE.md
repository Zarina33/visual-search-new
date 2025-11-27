# 🚀 Быстрый перезапуск проекта

## После перезагрузки компьютера или остановки Docker

### **Шаг 1: Запустить Docker контейнеры**

```bash
cd /home/user/Desktop/BakaiMarket/visual-search-project
docker-compose up -d
```

Проверить:
```bash
docker-compose ps
```

Должно быть **3 контейнера** в статусе "Up":
- `visual_search_postgres`
- `visual_search_redis`
- `visual_search_qdrant`

---

### **Шаг 2: Запустить API сервер**

```bash
poetry run uvicorn app.api.main:app --host 0.0.0.0 --port 8008 --reload
```

**API доступен на:**
- `http://localhost:8008`
- `http://localhost:8008/docs` (документация)

---

### **Шаг 3: Проверить что работает**

```bash
curl http://localhost:8008/api/v1/health
```

Должен вернуть: `{"status":"healthy",...}`

---

## ✅ Готово!

Теперь можно работать с API.

---

## 🔧 Дополнительно (если нужно)

### Запустить Celery worker (для фоновых задач)

В **отдельном терминале**:
```bash
cd /home/user/Desktop/BakaiMarket/visual-search-project
poetry run celery -A app.workers.celery_app worker --loglevel=info
```

---

## 📊 Быстрая проверка данных

### Количество товаров в PostgreSQL:
```bash
docker exec visual_search_postgres psql -U bakaimarket -d market -c "SELECT COUNT(*) FROM products;"
```

### Количество векторов в Qdrant:
```bash
curl -s http://localhost:6333/collections/product_embeddings | python3 -m json.tool | grep points_count
```

---

## 🧪 Тестирование

### Полный тест API:
```bash
poetry run python scripts/test_search_api.py
```

### Тест мониторинга:
```bash
poetry run python scripts/test_monitoring.py
```

---

## 🛑 Остановить всё

```bash
# Остановить API: Ctrl+C

# Остановить Docker (данные сохранятся)
docker-compose down
```

---

## 📝 Конфигурация

**База данных:**
- PostgreSQL: `localhost:5432`
- Database: `market`
- User: `bakaimarket`
- Password: `market`

**Qdrant:**
- URL: `http://localhost:6333`
- Коллекция: `product_embeddings`

**Redis:**
- URL: `localhost:6379`

---

## 🐛 Если что-то не работает

### API не запускается:
```bash
# Проверить Docker
docker-compose ps

# Установить зависимости
poetry install
```

### Нет данных:
```bash
# Загрузить demo продукты
poetry run python scripts/load_demo_products.py
```

### Посмотреть логи:
```bash
# Docker
docker-compose logs -f

# Приложение
tail -f logs/app_$(date +%Y-%m-%d).log
```

---

## 🎯 Основные endpoints

- `GET /api/v1/health` - проверка здоровья
- `GET /api/v1/health/detailed` - детальная проверка
- `GET /api/v1/metrics` - метрики Prometheus
- `POST /api/v1/search/by-text` - текстовый поиск
- `POST /api/v1/search/by-image` - поиск по изображению
- `GET /api/v1/search/similar/{product_id}` - похожие товары
- `GET /docs` - Swagger документация
