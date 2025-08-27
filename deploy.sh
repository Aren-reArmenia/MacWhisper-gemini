#!/bin/bash

# 🇦🇲 Оптимальная настройка для Армении
PROJECT_ID="eastern-academy-468907-c9"  # ИЗМЕНИ НА СВОЙ PROJECT ID
SERVICE_NAME="gemini-audio-proxy"

# Ближайший к Армении регион для минимальной латентности
REGION="europe-west1"  # Бельгия - лучший выбор для Армении
# Альтернативы: europe-west3 (Франкфурт), europe-west2 (Лондон)

echo "🚀 Deploying Gemini Audio Proxy to Cloud Run..."
echo "🇦🇲 Optimized for Armenia → 🇧🇪 Europe West 1 (Belgium)"
echo "📂 Project: $PROJECT_ID"

# Проверка установки gcloud
if ! command -v gcloud &> /dev/null; then
    echo "❌ Google Cloud SDK not installed!"
    echo "Install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Установка проекта
echo "🔧 Setting up project..."
gcloud config set project $PROJECT_ID

# Включение API
echo "🔌 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com

# Деплой с максимальной оптимизацией для скорости
echo "🚀 Deploying optimized service..."
gcloud run deploy $SERVICE_NAME \
    --source . \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 4Gi \
    --cpu 2 \
    --concurrency 1000 \
    --max-instances 10 \
    --min-instances 1 \
    --timeout 300 \
    --port 8080 \
    --execution-environment gen2

# Получение URL
echo "📡 Getting service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')

echo ""
echo "✅ DEPLOYMENT COMPLETED!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Service URL: $SERVICE_URL"
echo "📍 Region: $REGION (Belgium)"
echo "🇦🇲 Expected latency from Armenia: 50-80ms"
echo ""
echo "🧪 TEST WITH CURL:"
echo "curl -X POST $SERVICE_URL/v1/audio/transcriptions \\"
echo "  -H \"Authorization: Bearer YOUR_GEMINI_API_KEY\" \\"
echo "  -F \"file=@test.mp3\""
echo ""
echo "📊 PERFORMANCE MONITORING:"
echo "• Check logs: gcloud run services logs tail $SERVICE_NAME --region=$REGION"
echo "• Monitor: https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME"
