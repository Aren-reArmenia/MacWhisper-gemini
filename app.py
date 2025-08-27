from flask import Flask, request, jsonify
import google.generativeai as genai
import tempfile
import os
import json
import time
import logging
import hashlib
import threading
from functools import wraps, lru_cache
from pathlib import Path
import requests
from urllib.parse import urlparse
import weakref
import gc

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('performance.log')
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация оптимизаций (можно отключить при проблемах)
CONFIG = {
    'ENABLE_CACHING': os.getenv('ENABLE_CACHING', 'true').lower() == 'true',
    'ENABLE_STREAMING': os.getenv('ENABLE_STREAMING', 'true').lower() == 'true',
    'ENABLE_CONNECTION_POOLING': os.getenv('ENABLE_CONNECTION_POOLING', 'true').lower() == 'true',
    'ENABLE_PREWARMING': os.getenv('ENABLE_PREWARMING', 'true').lower() == 'true',
    'CACHE_SIZE': int(os.getenv('CACHE_SIZE', '100')),
    'CACHE_TTL': int(os.getenv('CACHE_TTL', '3600')),  # 1 час
    'STREAMING_THRESHOLD': int(os.getenv('STREAMING_THRESHOLD', '10')) * 1024 * 1024,  # 10MB
    'MAX_CONNECTIONS': int(os.getenv('MAX_CONNECTIONS', '10'))
}

logger.info(f"🔧 Конфигурация: {CONFIG}")

# Константы
MAX_FILE_SIZE = 100 * 1024 * 1024
SUPPORTED_FORMATS = {'flac','m4a','mp3','mp4','mpeg','mpga','oga','ogg','wav','webm'}

# ================================
# 🗄️ КЕШИРОВАНИЕ
# ================================

class TranscriptionCache:
    """Потокобезопасный кеш для транскрипций"""
    
    def __init__(self, max_size=100, ttl=3600):
        self.max_size = max_size
        self.ttl = ttl
        self.cache = {}
        self.access_times = {}
        self.lock = threading.RLock()
        logger.info(f"🗄️ Инициализирован кеш: размер={max_size}, TTL={ttl}s")
    
    def _cleanup_expired(self):
        """Удаляем устаревшие записи"""
        current_time = time.time()
        expired_keys = [
            key for key, access_time in self.access_times.items()
            if current_time - access_time > self.ttl
        ]
        for key in expired_keys:
            self.cache.pop(key, None)
            self.access_times.pop(key, None)
        
        if expired_keys:
            logger.info(f"🗑️ Очищено {len(expired_keys)} устаревших записей")
    
    def _evict_lru(self):
        """Удаляем наименее используемые записи"""
        while len(self.cache) >= self.max_size:
            oldest_key = min(self.access_times, key=self.access_times.get)
            self.cache.pop(oldest_key, None)
            self.access_times.pop(oldest_key, None)
            logger.info(f"🗑️ Evicted LRU entry: {oldest_key[:20]}...")
    
    def get_file_hash(self, file_data, filename, prompt=""):
        """Создаем хеш для файла + промпта"""
        hasher = hashlib.sha256()
        hasher.update(file_data)
        hasher.update(filename.encode())
        hasher.update(prompt.encode())
        return hasher.hexdigest()
    
    def get(self, key):
        """Получаем из кеша"""
        with self.lock:
            self._cleanup_expired()
            if key in self.cache:
                self.access_times[key] = time.time()
                logger.info(f"🎯 Cache HIT: {key[:20]}...")
                return self.cache[key]
            logger.info(f"❌ Cache MISS: {key[:20]}...")
            return None
    
    def set(self, key, value):
        """Сохраняем в кеш"""
        with self.lock:
            self._cleanup_expired()
            self._evict_lru()
            self.cache[key] = value
            self.access_times[key] = time.time()
            logger.info(f"💾 Cache SET: {key[:20]}... (размер кеша: {len(self.cache)})")
    
    def clear(self):
        """Очищаем кеш"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            logger.info("🧹 Кеш очищен")

# Глобальный кеш
transcription_cache = TranscriptionCache(
    max_size=CONFIG['CACHE_SIZE'], 
    ttl=CONFIG['CACHE_TTL']
) if CONFIG['ENABLE_CACHING'] else None

# ================================
# 🌊 STREAMING UPLOAD
# ================================

class StreamingUploader:
    """Потоковая загрузка больших файлов"""
    
    @staticmethod
    def should_use_streaming(file_size):
        """Определяем, нужен ли стриминг"""
        return CONFIG['ENABLE_STREAMING'] and file_size > CONFIG['STREAMING_THRESHOLD']
    
    @staticmethod
    def save_file_streaming(audio_file, chunk_size=8192):
        """Сохраняем файл по частям"""
        file_ext = os.path.splitext(audio_file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            temp_path = temp_file.name
            
            total_written = 0
            while True:
                chunk = audio_file.read(chunk_size)
                if not chunk:
                    break
                temp_file.write(chunk)
                total_written += len(chunk)
            
            logger.info(f"🌊 Streaming upload: {total_written/1024/1024:.2f}MB")
            return temp_path

# ================================
# 🔗 CONNECTION POOLING
# ================================

class GeminiConnectionPool:
    """Пул соединений для Gemini API"""
    
    def __init__(self, max_connections=10):
        self.max_connections = max_connections
        self.active_connections = 0
        self.lock = threading.Semaphore(max_connections)
        logger.info(f"🔗 Connection pool создан: {max_connections} соединений")
    
    def acquire(self):
        """Получаем соединение"""
        acquired = self.lock.acquire(blocking=True, timeout=30)
        if acquired:
            self.active_connections += 1
            logger.info(f"🔗 Соединение получено ({self.active_connections}/{self.max_connections})")
            return True
        logger.warning("⚠️ Не удалось получить соединение")
        return False
    
    def release(self):
        """Освобождаем соединение"""
        self.active_connections = max(0, self.active_connections - 1)
        self.lock.release()
        logger.info(f"🔗 Соединение освобождено ({self.active_connections}/{self.max_connections})")

# Глобальный пул соединений
connection_pool = GeminiConnectionPool(
    max_connections=CONFIG['MAX_CONNECTIONS']
) if CONFIG['ENABLE_CONNECTION_POOLING'] else None

# ================================
# 🔥 PRE-WARMING
# ================================

class PreWarmer:
    """Предварительный прогрев системы"""
    
    def __init__(self):
        self.is_warmed = False
        self.warmup_lock = threading.Lock()
        logger.info("🔥 PreWarmer инициализирован")
    
    def warmup(self, api_key=None):
        """Прогреваем систему"""
        if self.is_warmed or not CONFIG['ENABLE_PREWARMING']:
            return
        
        with self.warmup_lock:
            if self.is_warmed:
                return
            
            try:
                logger.info("🔥 Начинаем прогрев системы...")
                start_time = time.perf_counter()
                
                # Прогреваем импорты
                import google.generativeai as genai
                import tempfile
                import hashlib
                
                # Прогреваем Gemini API если есть ключ
                if api_key:
                    genai.configure(api_key=api_key)
                    # Создаем модель заранее
                    model = genai.GenerativeModel("gemini-2.5-flash")
                    logger.info("🤖 Gemini модель предзагружена")
                
                # Прогреваем файловую систему
                with tempfile.NamedTemporaryFile(delete=True) as f:
                    f.write(b"warmup")
                
                warmup_time = time.perf_counter() - start_time
                self.is_warmed = True
                logger.info(f"🔥 Система прогрета за {warmup_time:.3f}s")
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка прогрева: {e}")

# Глобальный прогреватель
prewarmer = PreWarmer()

# ================================
# 📊 PERFORMANCE TRACKING
# ================================

def timing_decorator(operation_name):
    """Декоратор для измерения времени операций"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start_time
                logger.info(f"⏱️  {operation_name}: {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.perf_counter() - start_time
                logger.error(f"❌ {operation_name} FAILED after {duration:.3f}s: {str(e)}")
                raise
        return wrapper
    return decorator

class PerformanceTracker:
    def __init__(self):
        self.start_time = None
        self.checkpoints = []
    
    def start(self):
        self.start_time = time.perf_counter()
        self.checkpoints = []
        logger.info("🚀 REQUEST START")
    
    def checkpoint(self, name):
        if self.start_time:
            elapsed = time.perf_counter() - self.start_time
            self.checkpoints.append((name, elapsed))
            logger.info(f"📍 {name}: {elapsed:.3f}s (total)")
    
    def finish(self):
        if self.start_time:
            total_time = time.perf_counter() - self.start_time
            logger.info(f"✅ REQUEST COMPLETE: {total_time:.3f}s total")
            
            # Выводим детальную разбивку
            prev_time = 0
            for name, elapsed in self.checkpoints:
                step_time = elapsed - prev_time
                logger.info(f"   📊 {name}: {step_time:.3f}s")
                prev_time = elapsed

# ================================
# 🛠️ CORE FUNCTIONS
# ================================

def extract_api_key(request):
    """Быстрое извлечение ключа без лишних проверок"""
    auth_header = request.headers.get('Authorization', '')
    return auth_header[7:].strip() if auth_header.startswith('Bearer ') else None

@timing_decorator("File save")
def save_uploaded_file(audio_file):
    """Сохранение файла с оптимизациями"""
    # Определяем размер файла
    audio_file.seek(0, 2)
    file_size = audio_file.tell()
    audio_file.seek(0)
    
    # Используем стриминг для больших файлов
    if StreamingUploader.should_use_streaming(file_size):
        logger.info(f"🌊 Используем streaming для файла {file_size/1024/1024:.2f}MB")
        return StreamingUploader.save_file_streaming(audio_file)
    else:
        # Обычное сохранение для небольших файлов
        file_ext = os.path.splitext(audio_file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            audio_file.save(temp_file.name)
            return temp_file.name

@timing_decorator("Gemini file upload")
def upload_to_gemini(temp_path):
    """Загрузка файла в Gemini с пулом соединений"""
    if connection_pool:
        if not connection_pool.acquire():
            raise Exception("Не удалось получить соединение к Gemini")
        try:
            return genai.upload_file(temp_path)
        finally:
            connection_pool.release()
    else:
        return genai.upload_file(temp_path)

@timing_decorator("Gemini transcription") 
def transcribe_with_gemini(uploaded_file, prompt):
    """Транскрипция через Gemini"""
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content([prompt, uploaded_file])
    return response

@timing_decorator("File cleanup")
def cleanup_files(uploaded_file, temp_path):
    """Очистка файлов"""
    try:
        if uploaded_file:
            genai.delete_file(uploaded_file.name)
    except Exception as e:
        logger.warning(f"Failed to delete Gemini file: {e}")
    
    try:
        if temp_path:
            os.unlink(temp_path)
    except Exception as e:
        logger.warning(f"Failed to delete temp file: {e}")

def create_openai_response(text, format_type="json"):
    """Минимальный ответ без лишних вычислений"""
    if format_type == "text":
        return text
    
    response = {"text": text}
    if format_type == "verbose_json":
        response = {
            "task": "transcribe",
            "language": "auto", 
            "duration": 1.0,
            "text": text,
            "segments": [{
                "id": 0,
                "start": 0.0,
                "end": 1.0,
                "text": text
            }]
        }
    return response

# ================================
# 🌐 MAIN API ENDPOINT
# ================================

@app.route('/v1/audio/transcriptions', methods=['POST'])
def transcribe_audio():
    tracker = PerformanceTracker()
    tracker.start()
    
    uploaded_file = None
    temp_path = None
    cache_key = None
    
    try:
        # 1. Проверка API ключа и прогрев
        api_key = extract_api_key(request)
        if not api_key:
            return {"error": {"message": "No API key"}}, 401
        
        genai.configure(api_key=api_key)
        
        # Прогреваем систему при первом запросе
        prewarmer.warmup(api_key)
        
        tracker.checkpoint("API key validated")
        
        # 2. Проверка файла
        audio_file = request.files.get('file')
        if not audio_file or not audio_file.filename:
            return {"error": {"message": "No file provided"}}, 400
        
        # Получаем размер и проверяем формат
        audio_file.seek(0, 2)
        file_size = audio_file.tell()
        audio_file.seek(0)
        
        logger.info(f"📄 File: {audio_file.filename}, Size: {file_size/1024/1024:.2f}MB")
        
        ext = audio_file.filename.lower().split('.')[-1] if '.' in audio_file.filename else ''
        if ext not in SUPPORTED_FORMATS:
            return {"error": {"message": f"Unsupported format: {ext}"}}, 400
        
        tracker.checkpoint("File validated")
        
        # 3. Получаем параметры
        response_format = request.form.get('response_format', 'json')
        language = request.form.get('language')
        prompt = request.form.get('prompt', '')
        
        # 4. Проверяем кеш
        if transcription_cache:
            # Читаем файл для хеширования
            file_data = audio_file.read()
            audio_file.seek(0)  # Возвращаемся в начало
            
            cache_key = transcription_cache.get_file_hash(
                file_data, audio_file.filename, prompt
            )
            
            cached_result = transcription_cache.get(cache_key)
            if cached_result:
                tracker.checkpoint("Cache hit")
                logger.info("🎯 Возвращаем результат из кеша")
                
                if response_format == "text":
                    result = cached_result, 200, {'Content-Type': 'text/plain'}
                else:
                    response_data = create_openai_response(cached_result, response_format)
                    result = response_data, 200
                
                tracker.finish()
                return result
        
        tracker.checkpoint("Cache checked")
        
        # 5. Сохраняем файл
        temp_path = save_uploaded_file(audio_file)
        tracker.checkpoint("File saved to temp")
        
        # 6. Загружаем в Gemini
        uploaded_file = upload_to_gemini(temp_path)
        tracker.checkpoint("File uploaded to Gemini")
        
        # 7. Создаем промпт
        base_prompt = """Transcribe this audio to text. Rules:
- Keep original language (Armenian/English/Russian mix is common)
- Remove filler words (uh, um, like)
- Clean up false starts and repetitions  
- Output only the clean transcription text"""
        
        if language:
            base_prompt += f"\nLanguage: {language}"
        if prompt:
            base_prompt += f"\nContext: {prompt}"
        
        # 8. Транскрибируем
        response = transcribe_with_gemini(uploaded_file, base_prompt)
        tracker.checkpoint("Transcription completed")
        
        if not response or not response.text:
            raise Exception("Empty response from Gemini")
        
        transcribed_text = response.text.strip()
        logger.info(f"📝 Transcribed {len(transcribed_text)} characters")
        
        # 9. Сохраняем в кеш
        if transcription_cache and cache_key:
            transcription_cache.set(cache_key, transcribed_text)
            tracker.checkpoint("Result cached")
        
        # 10. Очищаем ресурсы
        cleanup_files(uploaded_file, temp_path)
        tracker.checkpoint("Cleanup completed")
        
        # 11. Формируем ответ
        if response_format == "text":
            result = transcribed_text, 200, {'Content-Type': 'text/plain'}
        else:
            response_data = create_openai_response(transcribed_text, response_format)
            result = response_data, 200
        
        tracker.checkpoint("Response formatted")
        tracker.finish()
        
        # Принудительная сборка мусора для освобождения памяти
        gc.collect()
        
        return result
        
    except Exception as e:
        logger.error(f"🔥 ERROR: {str(e)}")
        
        # Очистка при ошибке
        cleanup_files(uploaded_file, temp_path)
        
        tracker.finish()
        return {"error": {"message": str(e)}}, 500

# ================================
# 🛠️ UTILITY ENDPOINTS
# ================================

@app.route('/health', methods=['GET'])
def health_check():
    """Расширенная проверка здоровья сервиса"""
    health_data = {
        "status": "healthy",
        "timestamp": time.time(),
        "optimizations": {
            "caching": CONFIG['ENABLE_CACHING'],
            "streaming": CONFIG['ENABLE_STREAMING'],
            "connection_pooling": CONFIG['ENABLE_CONNECTION_POOLING'],
            "prewarming": CONFIG['ENABLE_PREWARMING']
        },
        "system": {
            "prewarmed": prewarmer.is_warmed if prewarmer else False,
            "active_connections": connection_pool.active_connections if connection_pool else 0,
            "cache_size": len(transcription_cache.cache) if transcription_cache else 0
        }
    }
    return jsonify(health_data), 200

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Эндпоинт для получения метрик"""
    try:
        metrics = {
            "cache_stats": {},
            "performance_logs": []
        }
        
        if transcription_cache:
            metrics["cache_stats"] = {
                "size": len(transcription_cache.cache),
                "max_size": transcription_cache.max_size,
                "ttl": transcription_cache.ttl
            }
        
        # Последние логи
        try:
            with open('performance.log', 'r') as f:
                recent_logs = f.readlines()[-50:]
                metrics["performance_logs"] = recent_logs
        except:
            pass
        
        return jsonify(metrics), 200
    except Exception as e:
        return {"error": str(e)}, 500

@app.route('/cache/clear', methods=['POST'])
def clear_cache():
    """Очистка кеша"""
    if transcription_cache:
        transcription_cache.clear()
        return {"message": "Cache cleared"}, 200
    else:
        return {"message": "Caching disabled"}, 200

@app.route('/warmup', methods=['POST'])
def manual_warmup():
    """Ручной прогрев системы"""
    api_key = extract_api_key(request)
    prewarmer.warmup(api_key)
    return {"message": "Warmup completed", "warmed": prewarmer.is_warmed}, 200

# ================================
# 🎯 CDN & STATIC RESOURCES
# ================================

@app.route('/static/<path:filename>')
def static_files(filename):
    """Простая раздача статических файлов с кешированием"""
    # В реальном продакшене используйте nginx или CDN
    response = app.send_static_file(filename)
    response.cache_control.max_age = 86400  # 24 часа
    return response

# ================================
# 🚀 APPLICATION STARTUP
# ================================

@app.before_request
def before_request():
    """Перед каждым запросом"""
    # Прогреваем систему при первом запросе
    if not prewarmer.is_warmed:
        api_key = extract_api_key(request)
        if api_key:
            threading.Thread(target=prewarmer.warmup, args=(api_key,), daemon=True).start()

@app.after_request  
def after_request(response):
    """После каждого запроса"""
    # CORS заголовки
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'POST,GET'
    
    # Кеширование для статических ресурсов
    if request.endpoint == 'static_files':
        response.headers['Cache-Control'] = 'public, max-age=86400'
    
    return response

if __name__ == '__main__':
    print("🚀 СУПЕР-БЫСТРЫЙ Gemini Audio Proxy")
    print("="*50)
    print("🔧 Активные оптимизации:")
    for key, value in CONFIG.items():
        emoji = "✅" if value else "❌"
        print(f"   {emoji} {key}: {value}")
    print("="*50)
    print("📊 Эндпоинты:")
    print("   🎵 /v1/audio/transcriptions - основной API")
    print("   ❤️  /health - проверка здоровья")
    print("   📊 /metrics - метрики производительности")
    print("   🧹 /cache/clear - очистка кеша")
    print("   🔥 /warmup - прогрев системы")
    print("="*50)
    
    # Запускаем с оптимальными настройками
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
