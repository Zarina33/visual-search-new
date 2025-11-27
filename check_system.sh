#!/bin/bash

# Скрипт для проверки всех компонентов системы визуального поиска

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Загрузка переменных из .env файла
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
fi

# Установка значений по умолчанию, если не заданы в .env
POSTGRES_DB=${POSTGRES_DB:-visual_search}
POSTGRES_USER=${POSTGRES_USER:-postgres}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Проверка системы визуального поиска${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Счетчики
PASSED=0
FAILED=0
WARNING=0

# Функция для проверки
check() {
    local name="$1"
    local command="$2"
    local is_optional="${3:-false}"
    
    echo -n "Проверка $name... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ OK${NC}"
        ((PASSED++))
        return 0
    else
        if [ "$is_optional" = "true" ]; then
            echo -e "${YELLOW}⚠️  Не запущен (опционально)${NC}"
            ((WARNING++))
        else
            echo -e "${RED}❌ ОШИБКА${NC}"
            ((FAILED++))
        fi
        return 1
    fi
}

echo -e "${BLUE}--- Проверка Docker сервисов ---${NC}"
echo ""

# 1. Docker
check "Docker" "docker --version"

# 2. Docker Compose
check "Docker Compose" "docker-compose --version"

# 3. Контейнеры запущены
check "PostgreSQL контейнер" "docker ps | grep -q visual_search_postgres"
check "Redis контейнер" "docker ps | grep -q visual_search_redis"
check "Qdrant контейнер" "docker ps | grep -q visual_search_qdrant"

echo ""
echo -e "${BLUE}--- Проверка доступности сервисов ---${NC}"
echo ""

# 4. PostgreSQL доступен
check "PostgreSQL подключение" "docker exec visual_search_postgres pg_isready -U postgres"

# 5. Redis доступен
check "Redis подключение" "docker exec visual_search_redis redis-cli ping | grep -q PONG"

# 6. Qdrant доступен
check "Qdrant HTTP API" "curl -s http://localhost:6333/ | grep -q qdrant"

echo ""
echo -e "${BLUE}--- Проверка базы данных ---${NC}"
echo ""

# 7. База данных существует
check "База данных $POSTGRES_DB" "docker exec visual_search_postgres psql -U $POSTGRES_USER -lqt | cut -d \| -f 1 | grep -qw $POSTGRES_DB"

# 8. Таблицы созданы
TABLES=$(docker exec visual_search_postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')
if [ ! -z "$TABLES" ] && [ "$TABLES" -ge "2" ]; then
    echo -e "Проверка таблиц в БД... ${GREEN}✅ OK${NC} (найдено $TABLES таблиц)"
    ((PASSED++))
else
    echo -e "Проверка таблиц в БД... ${YELLOW}⚠️  Таблицы не созданы${NC}"
    echo -e "  ${YELLOW}Запустите: poetry run python scripts/load_sample_data.py${NC}"
    ((WARNING++))
fi

# 9. Есть данные в таблице products
PRODUCTS=$(docker exec visual_search_postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT COUNT(*) FROM products;" 2>/dev/null | tr -d ' ')
if [ ! -z "$PRODUCTS" ] && [ "$PRODUCTS" -gt "0" ]; then
    echo -e "Проверка данных в products... ${GREEN}✅ OK${NC} (найдено $PRODUCTS продуктов)"
    ((PASSED++))
else
    echo -e "Проверка данных в products... ${YELLOW}⚠️  Нет данных${NC}"
    echo -e "  ${YELLOW}Запустите: poetry run python scripts/load_sample_data.py${NC}"
    ((WARNING++))
fi

echo ""
echo -e "${BLUE}--- Проверка Qdrant ---${NC}"
echo ""

# 10. Коллекция Qdrant
if curl -s http://localhost:6333/collections 2>/dev/null | grep -q "product_embeddings"; then
    echo -e "Проверка коллекции Qdrant... ${GREEN}✅ OK${NC}"
    ((PASSED++))
    
    # Получить информацию о коллекции
    VECTORS=$(curl -s http://localhost:6333/collections/product_embeddings 2>/dev/null | grep -o '"points_count":[0-9]*' | cut -d: -f2)
    if [ ! -z "$VECTORS" ]; then
        echo -e "  Векторов в коллекции: $VECTORS"
    fi
else
    echo -e "Проверка коллекции Qdrant... ${YELLOW}⚠️  Коллекция не создана${NC}"
    echo -e "  ${YELLOW}Запустите: poetry run python scripts/load_sample_data.py${NC}"
    ((WARNING++))
fi

echo ""
echo -e "${BLUE}--- Проверка Python окружения ---${NC}"
echo ""

# 11. Poetry установлен
check "Poetry" "poetry --version"

# 12. Виртуальное окружение
if [ -d ".venv" ] || poetry env info > /dev/null 2>&1; then
    echo -e "Проверка виртуального окружения... ${GREEN}✅ OK${NC}"
    ((PASSED++))
else
    echo -e "Проверка виртуального окружения... ${YELLOW}⚠️  Не создано${NC}"
    echo -e "  ${YELLOW}Запустите: poetry install${NC}"
    ((WARNING++))
fi

echo ""
echo -e "${BLUE}--- Проверка API (опционально) ---${NC}"
echo ""

# 13. API запущен (опционально)
if check "API health endpoint" "curl -s http://localhost:8008/api/v1/health | grep -q healthy" "true"; then
    # Проверить детальный health check
    if curl -s http://localhost:8008/api/v1/health/detailed 2>/dev/null | grep -q '"status":"healthy"'; then
        echo -e "  Детальная проверка: ${GREEN}✅ Все компоненты здоровы${NC}"
    fi
fi

echo ""
echo -e "${BLUE}--- Проверка портов ---${NC}"
echo ""

# Функция для проверки порта
check_port() {
    local port=$1
    local service=$2
    
    if nc -z localhost $port 2>/dev/null || (echo > /dev/tcp/localhost/$port) 2>/dev/null; then
        echo -e "Порт $port ($service)... ${GREEN}✅ Открыт${NC}"
        ((PASSED++))
    else
        echo -e "Порт $port ($service)... ${RED}❌ Закрыт${NC}"
        ((FAILED++))
    fi
}

check_port 5432 "PostgreSQL"
check_port 6379 "Redis"
check_port 6333 "Qdrant HTTP"
check_port 6334 "Qdrant gRPC"

echo ""
echo -e "${BLUE}--- Проверка файлов конфигурации ---${NC}"
echo ""

# Проверка наличия важных файлов
check_file() {
    local file=$1
    if [ -f "$file" ]; then
        echo -e "Файл $file... ${GREEN}✅ Существует${NC}"
        ((PASSED++))
    else
        echo -e "Файл $file... ${RED}❌ Не найден${NC}"
        ((FAILED++))
    fi
}

check_file ".env"
check_file "pyproject.toml"
check_file "docker-compose.yml"

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}           Результаты проверки${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${GREEN}✅ Успешно: $PASSED${NC}"
echo -e "${YELLOW}⚠️  Предупреждения: $WARNING${NC}"
echo -e "${RED}❌ Ошибки: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    if [ $WARNING -eq 0 ]; then
        echo -e "${GREEN}🎉 Все проверки пройдены успешно!${NC}"
        echo ""
        echo -e "${BLUE}Следующие шаги:${NC}"
        echo "1. Запустите API: poetry run uvicorn app.api.main:app --host 0.0.0.0 --port 8008 --reload"
        echo "2. Откройте документацию: http://localhost:8008/docs"
        echo "3. Запустите тесты: poetry run pytest"
    else
        echo -e "${YELLOW}⚠️  Система работает, но есть предупреждения${NC}"
        echo ""
        echo -e "${YELLOW}Рекомендуемые действия:${NC}"
        if [ "$TABLES" -lt "2" ] || [ -z "$PRODUCTS" ] || [ "$PRODUCTS" -eq "0" ]; then
            echo "- Инициализируйте базу данных: poetry run python scripts/load_sample_data.py"
        fi
        if [ ! -d ".venv" ]; then
            echo "- Установите зависимости: poetry install"
        fi
    fi
else
    echo -e "${RED}❌ Обнаружены критические ошибки!${NC}"
    echo ""
    echo -e "${RED}Рекомендуемые действия:${NC}"
    echo "1. Проверьте логи: docker-compose logs"
    echo "2. Перезапустите сервисы: docker-compose restart"
    echo "3. Смотрите TESTING_GUIDE.md для подробной диагностики"
fi

echo ""
echo -e "${BLUE}Для подробной информации см. TESTING_GUIDE.md${NC}"
echo ""

# Выход с кодом ошибки если есть критические проблемы
if [ $FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi

