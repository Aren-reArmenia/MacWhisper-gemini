#!/bin/bash

# 🚀 СКРИПТ РАЗВЕРТЫВАНИЯ СУПЕР-БЫСТРОГО GEMINI PROXY
# ================================================

set -e  # Выходим при первой ошибке

# Конфигурация
PROJECT_ID=${PROJECT_ID:-"your-project-id"}
SERVICE_NAME=${SERVICE_NAME:-"gemini-audio-proxy"}
REGION=${REGION:-"us-central1"}
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 РАЗВЕРТЫВАНИЕ GEMINI AUDIO PROXY${NC}"
echo "================================================="

# Проверяем наличие необходимых инструментов
check_tool() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 не найден. Установите его и попробуйте снова.${NC}"
        exit 1
    fi
}

echo -e "${YELLOW}🔍 Проверяем инструменты...${NC}"
check_tool "gcloud"
check_tool "docker"

# Проверяем аутентификацию
echo -e "${YELLOW}🔐 Проверяем аутентификацию...${NC}"
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${RED}❌ Не найден активный аккаунт Google Cloud. Выполните 'gcloud auth login'${NC}"
    exit 1
fi

# Устанавливаем проект
echo -e "${YELLOW}📁 Устанавливаем проект: $PROJECT_ID${NC}"
gcloud config set project $PROJECT_ID

# Включаем необходимые API
echo -e "${YELLOW}🔌 Включаем необходимые API...${NC}"
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Конфигурация Docker для GCR
echo -e "${YELLOW}🐳 Настраиваем Docker для Google Container Registry...${NC}"
gcloud auth configure-docker

# Собираем образ
echo -e "${YELLOW}🏗️  Собираем Docker образ...${NC}"
docker build -t $IMAGE_NAME . --platform linux/amd64

# Отправляем образ в реестр
echo -e "${YELLOW}📤 Отправляем образ в Container Registry...${NC}"
docker push $IMAGE_NAME

# Развертываем в Cloud Run
echo -e "${YELLOW}☁️  Развертываем в Cloud Run...${NC}"
gcloud run deploy $SERVICE_NAME \
    --image=$IMAGE_NAME \
    --platform=managed \
    --region=$REGION \
    --allow-unauthenticated \
    --memory=4Gi \
    --cpu=2 \
    --max-instances=50 \
    --concurrency=20 \
    --timeout=900 \
    --set-env-vars="ENABLE_CACHING=true,ENABLE_STREAMING=true,ENABLE_CONNECTION_POOLING=true,ENABLE_PREWARMING=true,CACHE_SIZE=200,MAX_CONNECTIONS=25,STREAMING_THRESHOLD=5" \
    --labels="app=gemini-proxy,version=v2,optimized=true"

# Получаем URL сервиса
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo ""
echo -e "${GREEN}✅ РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО!${NC}"
echo "================================================="
echo -e "🌐 URL сервиса: ${BLUE}$SERVICE_URL${NC}"
echo -e "📊 Health check: ${BLUE}$SERVICE_URL/health${NC}"
echo -e "📈 Метрики: ${BLUE}$SERVICE_URL/metrics${NC}"
echo ""
echo -e "${YELLOW}🧪 Для тестирования:${NC}"
echo "export CLOUD_RUN_URL=\"$SERVICE_URL\""
echo "python performance_tester.py"
echo ""
echo -e "${YELLOW}📝 Логи сервиса:${NC}"
echo "gcloud run logs tail $SERVICE_NAME --region=$REGION"
echo ""
echo -e "${YELLOW}⚡ Быстрый тест API:${NC}"
echo "curl -X POST \"$SERVICE_URL/v1/audio/transcriptions\" \\"
echo "  -H \"Authorization: Bearer \$GEMINI_API_KEY\" \\"
echo "  -F \"file=@test_audio.wav\" \\"
echo "  -F \"response_format=json\""

# Проверяем здоровье сервиса
echo ""
echo -e "${YELLOW}❤️  Проверяем здоровье сервиса...${NC}"
if curl -s "$SERVICE_URL/health" > /dev/null; then
    echo -e "${GREEN}✅ Сервис работает!${NC}"
    
    # Показываем статус оптимизаций
    echo -e "${YELLOW}🔧 Статус оптимизаций:${NC}"
    curl -s "$SERVICE_URL/health" | python -m json.tool | grep -A 10 "optimizations"
else
    echo -e "${RED}❌ Сервис не отвечает. Проверьте логи.${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Готово! Ваш супер-быстрый Gemini Audio Proxy запущен!${NC}"
