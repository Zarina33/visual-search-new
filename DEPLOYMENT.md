# 🚀 Руководство по развертыванию на новом сервере

**Полное пошаговое руководство для развертывания системы визуального поиска с нуля**

---

## 📋 Содержание

1. [Требования к серверу](#-требования-к-серверу)
2. [Установка зависимостей](#-установка-зависимостей)
3. [Настройка проекта](#-настройка-проекта)
4. [Загрузка данных](#-загрузка-данных)
5. [Запуск в production](#-запуск-в-production)
6. [Настройка Nginx](#-настройка-nginx)
7. [SSL сертификат](#-ssl-сертификат)
8. [Мониторинг](#-мониторинг)
9. [Резервное копирование](#-резервное-копирование)
10. [Troubleshooting](#-troubleshooting)

---

## 🖥️ Требования к серверу

### Минимальные требования:
- **OS:** Ubuntu 20.04+ / Debian 11+
- **CPU:** 4 cores
- **RAM:** 16 GB
- **Disk:** 100 GB SSD
- **GPU:** NVIDIA GPU с 4+ GB VRAM (опционально)
- **Network:** Стабильное интернет-соединение

### Рекомендуемые требования:
- **CPU:** 8+ cores
- **RAM:** 32 GB
- **Disk:** 200 GB NVMe SSD
- **GPU:** NVIDIA RTX 3060+ (12 GB VRAM)

---

## 🔧 Установка зависимостей

### Шаг 1: Обновление системы

```bash
# Обновить пакеты
sudo apt update && sudo apt upgrade -y

# Установить базовые утилиты
sudo apt install -y curl wget git build-essential software-properties-common
```

### Шаг 2: Установка Python 3.12

```bash
# Добавить PPA для Python 3.12
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# Установить Python 3.12
sudo apt install -y python3.12 python3.12-venv python3.12-dev

# Проверить версию
python3.12 --version
```

### Шаг 3: Установка Poetry

```bash
# Установить Poetry
curl -sSL https://install.python-poetry.org | python3.12 -

# Добавить в PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Проверить установку
poetry --version
```

### Шаг 4: Установка Docker и Docker Compose

```bash
# Установить Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавить пользователя в группу docker
sudo usermod -aG docker $USER

# Установить Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Перезайти в систему для применения группы
newgrp docker

# Проверить установку
docker --version
docker-compose --version
```

### Шаг 5: Установка NVIDIA драйверов (для GPU)

```bash
# Проверить наличие GPU
lspci | grep -i nvidia

# Установить NVIDIA драйверы
sudo apt install -y nvidia-driver-535

# Установить NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt update
sudo apt install -y nvidia-container-toolkit

# Перезагрузить сервер
sudo reboot

# После перезагрузки проверить
nvidia-smi
```

---

## 📦 Настройка проекта

### Шаг 1: Клонирование репозитория

```bash
# Создать директорию для проектов
mkdir -p ~/projects
cd ~/projects

# Клонировать репозиторий (замените на ваш URL)
git clone https://github.com/yourusername/visual-search-project.git
cd visual-search-project

# Или скопировать через SCP
# scp -r /path/to/visual-search-project user@server:/home/user/projects/
```

### Шаг 2: Настройка окружения

```bash
# Создать .env файл
nano .env
```

**Содержимое `.env`:**

```bash
# Application
APP_NAME=visual-search-project
APP_VERSION=1.0.0
DEBUG=False
LOG_LEVEL=INFO

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=market
POSTGRES_USER=bakaimarket
POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD  # ⚠️ Измените!

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=product_embeddings

# CLIP Model
CLIP_MODEL_NAME=openai/clip-vit-base-patch32
CLIP_DEVICE=cuda  # или cpu если нет GPU
CLIP_BATCH_SIZE=32

# BakaiMarket CDN
BAKAI_CDN_API_URL=https://api-cdn.bakai.store
BAKAI_CDN_ACCESS_KEY=your_access_key_here  # ⚠️ Добавьте ваш ключ!
BAKAI_CDN_SECRET_KEY=your_secret_key_here  # ⚠️ Добавьте ваш ключ!

# Webhook
WEBHOOK_SECRET=your_webhook_secret_here  # ⚠️ Сгенерируйте секрет!

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

**Генерация webhook secret:**

```bash
# Сгенерировать случайный секрет
openssl rand -hex 32
```

### Шаг 3: Установка Python зависимостей

```bash
# Установить зависимости через Poetry
poetry install --no-dev

# Активировать виртуальное окружение
poetry shell
```

### Шаг 4: Запуск Docker сервисов

```bash
# Запустить PostgreSQL, Redis, Qdrant
docker-compose up -d

# Проверить статус
docker-compose ps

# Должно быть 3 контейнера в статусе "Up":
# - visual_search_postgres
# - visual_search_redis
# - visual_search_qdrant
```

### Шаг 5: Инициализация баз данных

```bash
# Инициализировать PostgreSQL и Qdrant
poetry run python scripts/init_databases.py

# Проверить что базы созданы
docker exec visual_search_postgres psql -U bakaimarket -d market -c "\dt"
curl http://localhost:6333/collections/product_embeddings
```

---

## 📥 Загрузка данных

### Вариант 1: Полная синхронизация с BakaiMarket S3 (~76,000 товаров)

```bash
# Запустить полную синхронизацию
poetry run python scripts/sync_images_from_s3_optimized.py

# Это займет ~3-4 часа
# Будет загружено ~76,000 товаров
```

### Вариант 2: Тестовая загрузка (первые 1000 товаров)

```bash
# Загрузить только 1000 товаров для теста
poetry run python scripts/sync_images_from_s3_optimized.py --limit 1000

# Это займет ~5-10 минут
```

### Вариант 3: Demo данные (15 товаров)

```bash
# Загрузить demo данные
poetry run python scripts/load_demo_products.py
```

### Проверка загруженных данных

```bash
# PostgreSQL
docker exec visual_search_postgres psql -U bakaimarket -d market -c "SELECT COUNT(*) FROM products;"

# Qdrant
curl -s http://localhost:6333/collections/product_embeddings | python3 -m json.tool | grep points_count
```

---

## 🚀 Запуск в production

### Создать systemd сервис для API

```bash
sudo nano /etc/systemd/system/visual-search-api.service
```

**Содержимое файла:**

```ini
[Unit]
Description=Visual Search API
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/projects/visual-search-project
Environment="PATH=/home/YOUR_USERNAME/.local/bin:/usr/bin"
ExecStart=/home/YOUR_USERNAME/.local/bin/poetry run uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**⚠️ Замените `YOUR_USERNAME` на ваше имя пользователя!**

### Создать systemd сервис для Celery Worker

```bash
sudo nano /etc/systemd/system/visual-search-celery.service
```

**Содержимое файла:**

```ini
[Unit]
Description=Visual Search Celery Worker
After=network.target redis.service
Requires=redis.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/projects/visual-search-project
Environment="PATH=/home/YOUR_USERNAME/.local/bin:/usr/bin"
ExecStart=/home/YOUR_USERNAME/.local/bin/poetry run celery -A app.workers.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Запустить сервисы

```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Запустить API
sudo systemctl start visual-search-api
sudo systemctl enable visual-search-api

# Запустить Celery
sudo systemctl start visual-search-celery
sudo systemctl enable visual-search-celery

# Проверить статус
sudo systemctl status visual-search-api
sudo systemctl status visual-search-celery

# Посмотреть логи
sudo journalctl -u visual-search-api -f
sudo journalctl -u visual-search-celery -f
```

---

## 🔒 Настройка Nginx

### Установка Nginx

```bash
sudo apt install -y nginx
```

### Конфигурация

```bash
sudo nano /etc/nginx/sites-available/visual-search
```

**Содержимое:**

```nginx
server {
    listen 80;
    server_name your-domain.com;  # ⚠️ Замените на ваш домен

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Websocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

### Активация

```bash
# Создать символическую ссылку
sudo ln -s /etc/nginx/sites-available/visual-search /etc/nginx/sites-enabled/

# Проверить конфигурацию
sudo nginx -t

# Перезапустить Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 🔐 SSL сертификат

### Let's Encrypt (бесплатный SSL)

```bash
# Установить Certbot
sudo apt install -y certbot python3-certbot-nginx

# Получить сертификат
sudo certbot --nginx -d your-domain.com

# Автоматическое обновление
sudo certbot renew --dry-run
```

---

## 🔥 Настройка Firewall

```bash
# Установить UFW
sudo apt install -y ufw

# Разрешить SSH
sudo ufw allow 22/tcp

# Разрешить HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Включить firewall
sudo ufw enable

# Проверить статус
sudo ufw status
```

---

## 📊 Мониторинг

### Проверка здоровья системы

```bash
# API health check
curl http://localhost:8000/api/v1/health

# Детальная проверка
curl http://localhost:8000/api/v1/health/detailed

# Метрики
curl http://localhost:8000/api/v1/metrics
```

### Просмотр логов

```bash
# API логи (systemd)
sudo journalctl -u visual-search-api -f

# Celery логи
sudo journalctl -u visual-search-celery -f

# Docker логи
docker-compose logs -f

# Логи приложения
tail -f logs/app_$(date +%Y-%m-%d).log
tail -f logs/errors_$(date +%Y-%m-%d).log
```

### Мониторинг ресурсов

```bash
# CPU и память
htop

# GPU (если есть)
nvidia-smi

# Диск
df -h

# Docker контейнеры
docker stats
```

---

## 💾 Резервное копирование

### Создать скрипт для бэкапа

```bash
nano ~/backup_visual_search.sh
```

**Содержимое:**

```bash
#!/bin/bash

BACKUP_DIR="/backup/visual-search"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Бэкап PostgreSQL
docker exec visual_search_postgres pg_dump -U bakaimarket market > $BACKUP_DIR/postgres_$DATE.sql

# Бэкап Qdrant
docker exec visual_search_qdrant tar czf - /qdrant/storage > $BACKUP_DIR/qdrant_$DATE.tar.gz

# Удалить старые бэкапы (старше 7 дней)
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
```

```bash
# Сделать исполняемым
chmod +x ~/backup_visual_search.sh

# Добавить в cron (ежедневно в 2:00)
crontab -e
```

Добавить строку:
```
0 2 * * * /home/YOUR_USERNAME/backup_visual_search.sh >> /var/log/visual-search-backup.log 2>&1
```

---

## 🧪 Тестирование после развертывания

```bash
# Полное тестирование системы
poetry run python scripts/test_complete_system.py

# Тест API
poetry run python scripts/test_search_api.py

# Тест webhook
poetry run python scripts/test_webhook_local.py
```

---

## 🐛 Troubleshooting

### Проблема: API не запускается

```bash
# Проверить логи
sudo journalctl -u visual-search-api -n 50

# Проверить порт
sudo netstat -tulpn | grep 8000

# Проверить Docker сервисы
docker-compose ps
```

### Проблема: Нет GPU

```bash
# Проверить драйверы
nvidia-smi

# Изменить в .env
CLIP_DEVICE=cpu
```

### Проблема: Медленный поиск

```bash
# Проверить использование GPU
nvidia-smi

# Увеличить количество workers
# В systemd сервисе изменить:
ExecStart=... --workers 8
```

### Проблема: Ошибки подключения к базам

```bash
# Проверить Docker контейнеры
docker-compose ps

# Перезапустить
docker-compose restart

# Проверить логи
docker-compose logs postgres
docker-compose logs qdrant
```

---

## 🔄 Обновление системы

```bash
# 1. Остановить сервисы
sudo systemctl stop visual-search-api
sudo systemctl stop visual-search-celery

# 2. Обновить код
cd ~/projects/visual-search-project
git pull origin main

# 3. Обновить зависимости
poetry install --no-dev

# 4. Применить миграции (если есть)
poetry run python scripts/init_databases.py

# 5. Запустить сервисы
sudo systemctl start visual-search-api
sudo systemctl start visual-search-celery

# 6. Проверить
curl http://localhost:8000/api/v1/health
```

---

## ✅ Чеклист развертывания

- [ ] Сервер соответствует требованиям
- [ ] Установлены все зависимости (Python, Docker, Poetry)
- [ ] Настроен `.env` файл
- [ ] Запущены Docker сервисы
- [ ] Инициализированы базы данных
- [ ] Загружены данные (полностью или частично)
- [ ] Настроены systemd сервисы
- [ ] Настроен Nginx
- [ ] Настроен SSL сертификат
- [ ] Настроен firewall
- [ ] Настроено резервное копирование
- [ ] Проведено тестирование
- [ ] Система работает в production

---

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `sudo journalctl -u visual-search-api -f`
2. Запустите тесты: `poetry run python scripts/test_complete_system.py`
3. Проверьте документацию: `/docs` endpoint
4. Создайте issue в репозитории

---

**🎉 Поздравляем! Система визуального поиска успешно развернута!**

