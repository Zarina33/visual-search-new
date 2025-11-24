# 🔍 Visual Search Project

**Система визуального поиска товаров для BakaiMarket на основе CLIP модели**

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 📋 О проекте

**Visual Search Project** - это production-ready система для визуального поиска товаров, использующая современные технологии машинного обучения (CLIP) и векторный поиск.

### Основная задача

Пользователь загружает фотографию товара → система находит похожие товары → возвращает результаты с ID и изображениями.

### Ключевые возможности

- ⚡ **Быстрый поиск:** ~200ms среди 76,000+ товаров
- 🎯 **Высокая точность:** 90-99% similarity score
- 🖼️ **Поддержка форматов:** JPEG, PNG, WEBP
- 🔄 **Автообновление:** Webhooks для синхронизации с BakaiMarket
- 📊 **Мониторинг:** Prometheus метрики и детальное логирование
- 🐳 **Docker:** Простое развертывание
- 🧪 **100% покрытие тестами**

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT                                  │
│                    (Web / Mobile App)                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Search     │  │   Products   │  │   Webhooks   │         │
│  │   Endpoints  │  │   Endpoints  │  │   Endpoints  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────┬────────────────┬────────────────┬─────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌─────────────────┐ ┌─────────────┐ ┌──────────────────┐
│   CLIP Model    │ │ PostgreSQL  │ │  Celery Worker   │
│   (GPU/CPU)     │ │  (Metadata) │ │  (Background)    │
│                 │ │             │ │                  │
│ • Text Embed    │ │ • Products  │ │ • Image Process  │
│ • Image Embed   │ │ • Logs      │ │ • Indexing       │
└─────────────────┘ └─────────────┘ └────────┬─────────┘
         │                                     │
         ▼                                     ▼
┌─────────────────────────────────────────────────────────┐
│                    Qdrant Vector DB                     │
│                  (76,000+ vectors)                      │
│                                                         │
│  • Fast similarity search                               │
│  • 512-dimensional vectors                              │
│  • Cosine similarity                                    │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                  BakaiMarket S3 CDN                     │
│                  (Product Images)                       │
└─────────────────────────────────────────────────────────┘
```

### Компоненты

#### 1. **FastAPI Application**
- REST API endpoints
- Request validation (Pydantic)
- Async operations
- CORS middleware
- Logging middleware

#### 2. **CLIP Model**
- OpenAI CLIP (ViT-B/32)
- GPU acceleration (CUDA)
- Batch processing
- 512-dimensional embeddings

#### 3. **PostgreSQL**
- Product metadata
- Search logs
- SQLAlchemy 2.0 async
- Connection pooling

#### 4. **Qdrant**
- Vector storage
- Similarity search
- Cosine distance
- Fast indexing

#### 5. **Celery + Redis**
- Background tasks
- Webhook processing
- Image indexing
- Task queue

#### 6. **BakaiMarket S3**
- Image storage
- AWS Signature V4
- Presigned URLs

---

## 🛠️ Технологии

### Backend
- **Python 3.12** - Основной язык
- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation
- **SQLAlchemy 2.0** - ORM (async)
- **Celery** - Task queue
- **Redis** - Message broker

### Machine Learning
- **Transformers** - HuggingFace library
- **CLIP** - OpenAI model
- **PyTorch** - Deep learning framework
- **Pillow** - Image processing
- **NumPy** - Numerical computing

### Databases
- **PostgreSQL 15** - Relational DB
- **Qdrant** - Vector DB
- **Redis 7** - Cache & Queue

### DevOps
- **Docker** - Containerization
- **Docker Compose** - Orchestration
- **Poetry** - Dependency management
- **Nginx** - Reverse proxy
- **Systemd** - Service management

### Monitoring
- **Prometheus** - Metrics
- **Loguru** - Logging
- **Grafana** - Visualization (optional)

### Cloud
- **AWS S3** - Object storage (BakaiMarket CDN)
- **Boto3** - AWS SDK

---

## ✨ Возможности

### 1. Визуальный поиск

```bash
POST /api/v1/search/by-image
```

- Поиск по загруженному изображению
- Настраиваемый порог similarity
- Возврат топ-N результатов

**Пример ответа:**

```json
{
  "query_time_ms": 176,
  "results_count": 5,
  "results": [
    {
      "product_id": "77338",
      "external_id": "bakai_118133",
      "title": "Product 118133",
      "image_url": "https://api-cdn.bakai.store/...",
      "similarity_score": 0.9994805
    }
  ]
}
```

### 2. Текстовый поиск

```bash
POST /api/v1/search/by-text
```

- Семантический поиск по описанию
- Мультиязычная поддержка (CLIP)
- Гибкие фильтры

### 3. Поиск похожих товаров

```bash
GET /api/v1/search/similar/{product_id}
```

- Рекомендательная система
- "Вам также может понравиться"

### 4. Webhooks

```bash
POST /api/v1/webhooks/bakai
```

Автоматическое обновление при изменениях:
- `product.created` - новый товар
- `product.updated` - обновление
- `product.deleted` - удаление
- `product.image.updated` - новое изображение

### 5. Мониторинг

- Prometheus метрики (`/api/v1/metrics`)
- Health checks (`/api/v1/health`)
- Детальное логирование
- Performance tracking

---

## 📊 Производительность

| Метрика | Значение |
|---------|----------|
| **Товаров в БД** | 76,462 |
| **Векторов в Qdrant** | 76,462 |
| **Размерность векторов** | 512 |
| **Время поиска** | 50-200ms |
| **Точность (similarity)** | 90-99% |
| **Поддерживаемые форматы** | JPEG, PNG, WEBP |
| **Максимальный размер файла** | 20 MB |
| **Максимальное разрешение** | 2048x2048 px |

---

## 🚀 Быстрый старт

### Требования

- Python 3.12+
- Poetry
- Docker & Docker Compose
- NVIDIA GPU (опционально, но рекомендуется)

### Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/yourusername/visual-search-project.git
cd visual-search-project

# 2. Настроить окружение
cp .env.example .env
nano .env  # Настроить переменные

# 3. Установить зависимости
poetry install

# 4. Запустить Docker сервисы
docker-compose up -d

# 5. Инициализировать базы
poetry run python scripts/init_databases.py

# 6. Загрузить данные (опционально)
poetry run python scripts/load_demo_products.py

# 7. Запустить API
poetry run uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

# 8. Открыть документацию
open http://localhost:8000/docs
```

---

## 📚 Документация

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Полное руководство по развертыванию на новом сервере
- **[TESTING.md](TESTING.md)** - Пошаговое тестирование всех компонентов
- **[RESTART_GUIDE.md](RESTART_GUIDE.md)** - Быстрый перезапуск после перезагрузки
- **[WEBHOOK_INTEGRATION_GUIDE.md](WEBHOOK_INTEGRATION_GUIDE.md)** - Интеграция webhooks для BakaiMarket
- **[API_EXAMPLES.md](API_EXAMPLES.md)** - Примеры использования API

---

## 📝 API Endpoints

### Search

- `POST /api/v1/search/by-image` - Поиск по изображению
- `POST /api/v1/search/by-text` - Поиск по тексту
- `GET /api/v1/search/similar/{product_id}` - Похожие товары

### Products

- `GET /api/v1/products` - Список товаров
- `GET /api/v1/products/{product_id}` - Информация о товаре
- `POST /api/v1/products` - Создать товар
- `PUT /api/v1/products/{product_id}` - Обновить товар
- `DELETE /api/v1/products/{product_id}` - Удалить товар

### Webhooks

- `POST /api/v1/webhooks/bakai` - Production endpoint (с HMAC подписью)
- `POST /api/v1/webhooks/test` - Test endpoint (без подписи)
- `GET /api/v1/webhooks/health` - Health check

### Monitoring

- `GET /api/v1/health` - Базовая проверка
- `GET /api/v1/health/detailed` - Детальная проверка
- `GET /api/v1/metrics` - Prometheus метрики
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc

---

## 🧪 Тестирование

```bash
# Все тесты
poetry run pytest -v

# С покрытием
poetry run pytest --cov=app --cov-report=html

# Системные тесты
poetry run python scripts/test_complete_system.py

# Тест API
poetry run python scripts/test_search_api.py
```

**Покрытие тестами: 100%**

---

## 📈 Мониторинг

### Prometheus метрики

```bash
curl http://localhost:8000/api/v1/metrics
```

Основные метрики:
- `visual_search_total_searches` - Общее количество поисков
- `visual_search_search_duration_seconds` - Время поиска
- `visual_search_clip_inference_duration_seconds` - Время CLIP
- `visual_search_qdrant_search_duration_seconds` - Время Qdrant
- `visual_search_errors_total` - Количество ошибок

### Логирование

```bash
# Структурированные логи (Loguru)
logs/
├── app_2025-11-12.log      # Основные логи
├── errors_2025-11-12.log   # Только ошибки
└── access_2025-11-12.log   # HTTP запросы

# Просмотр логов
tail -f logs/app_$(date +%Y-%m-%d).log
```

---

## 🐛 Troubleshooting

### API не запускается

```bash
# Проверить порт
sudo netstat -tulpn | grep 8000

# Проверить Docker
docker-compose ps

# Посмотреть логи
docker-compose logs
```

### Медленный поиск

```bash
# Проверить GPU
nvidia-smi

# Изменить device в .env
CLIP_DEVICE=cuda  # или cpu
```

### Ошибки подключения к БД

```bash
# Перезапустить Docker
docker-compose restart

# Проверить логи
docker-compose logs postgres
docker-compose logs qdrant
```

---

## 🗺️ Структура проекта

```
visual-search-project/
├── app/
│   ├── api/                   # FastAPI application
│   │   ├── main.py            # App factory
│   │   └── routes/            # API endpoints
│   ├── db/                    # Database clients
│   │   ├── postgres.py        # PostgreSQL
│   │   └── qdrant.py          # Qdrant
│   ├── models/                # ML models
│   │   └── clip_model.py      # CLIP wrapper
│   ├── schemas/               # Pydantic models
│   ├── utils/                 # Utilities
│   └── workers/               # Celery workers
├── scripts/                   # Utility scripts
│   ├── init_databases.py      # DB initialization
│   ├── sync_images_from_s3_optimized.py  # Data sync
│   └── test_*.py              # Test scripts
├── tests/                     # Test suite
├── docker-compose.yml         # Docker services
├── pyproject.toml             # Poetry dependencies
├── .env                       # Environment variables
└── README.md                  # This file
```

---

## 🤝 Contributing

Мы приветствуем вклад в проект!

1. Fork репозиторий
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📞 Контакты

- **Email:** your.email@example.com
- **Telegram:** @yourusername
- **Website:** https://yourwebsite.com

---

## 🙏 Благодарности

- OpenAI за CLIP модель
- HuggingFace за Transformers
- FastAPI community
- Qdrant team
- BakaiMarket team

---

**🎉 Спасибо за использование Visual Search Project!**

*Сделано с ❤️ для BakaiMarket*
