FROM python:3.11-slim

# Оптимизация для скорости
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Копируем requirements для кеширования слоев
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY app.py .

# Настройки для Cloud Run
ENV PORT=8080

# Запуск с оптимизированными настройками для скорости
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 300 --preload --worker-class sync app:app
