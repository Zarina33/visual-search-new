#!/bin/bash

# Visual Search Project - Quick Start Script

set -e

echo "=========================================="
echo "Visual Search Project - Quick Start"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}✗ Poetry is not installed${NC}"
    echo "Install it with: curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi
echo -e "${GREEN}✓ Poetry found${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗ docker-compose is not installed${NC}"
    echo "Please install docker-compose: https://docs.docker.com/compose/install/"
    exit 1
fi
echo -e "${GREEN}✓ docker-compose found${NC}"

echo ""
echo "Step 1: Installing Python dependencies..."
poetry install

echo ""
echo "Step 2: Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env file${NC}"
    echo -e "${YELLOW}⚠ Please review .env file and adjust settings if needed${NC}"
else
    echo -e "${YELLOW}⚠ .env file already exists, skipping${NC}"
fi

echo ""
echo "Step 3: Starting Docker services..."
docker-compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

echo ""
echo "Step 4: Initializing database..."
poetry run python scripts/load_sample_data.py

echo ""
echo -e "${GREEN}=========================================="
echo "✓ Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Start the API server:"
echo "   ${YELLOW}poetry run uvicorn app.api.main:app --host 0.0.0.0 --port 8008 --reload${NC}"
echo ""
echo "2. (Optional) Start Celery worker in another terminal:"
echo "   ${YELLOW}poetry run celery -A app.workers.celery_app worker --loglevel=info${NC}"
echo ""
echo "3. Open API documentation:"
echo "   ${YELLOW}http://localhost:8008/docs${NC}"
echo ""
echo "4. Test health endpoint:"
echo "   ${YELLOW}curl http://localhost:8008/api/v1/health${NC}"
echo ""
echo "For more information, see README.md or QUICKSTART.md"
echo ""

