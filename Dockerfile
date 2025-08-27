# СУПЕР-ОПТИМИЗИРОВАННЫЙ Dockerfile для максимальной скорости
FROM python:3.11-slim

# Устанавливаем переменные окружения для оптимизации Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONHASHSEED=random
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Переменные окружения для оптимизаций приложения
ENV ENABLE_CACHING=true
ENV ENABLE_STREAMING=true
ENV ENABLE_CONNECTION_POOLING=true
ENV ENABLE_PREWARMING=true
ENV CACHE_SIZE=200
ENV CACHE_TTL=3600
ENV STREAMING_THRESHOLD=5
ENV MAX_CONNECTIONS=20

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Копируем requirements для кеширования Docker слоя
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY app.py .

# Создаем директории для кеша и логов
RUN mkdir -p /app/cache /app/logs /app/static && \
    touch /app/performance.log

# Создаем пользователя для безопасности
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /tmp/audio /tmp/gemini_cache && \
    chown -R appuser:appuser /tmp/audio /tmp/gemini_cache

USER appuser

# Прогреваем импорты для cold start оптимизации
RUN python -c "\
import google.generativeai as genai; \
import flask; \
import tempfile; \
import os; \
import json; \
import time; \
import hashlib; \
import threading; \
import logging; \
import weakref; \
import gc; \
print('🚀 All imports preloaded for faster cold start')"

# Создаем health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Открываем порт
EXPOSE 8080

# Запускаем с продакшн настройками
# Используем exec форму для правильной обработки сигналов
CMD ["python", "-u", "app.py"]

# Метаданные образа
LABEL maintainer="your-email@example.com"
LABEL version="2.0"
LABEL description="Super-optimized Gemini Audio Transcription Proxy with caching, streaming, connection pooling"
