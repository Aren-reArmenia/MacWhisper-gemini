from flask import Flask, request
import google.generativeai as genai
import tempfile
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные для переиспользования
executor = ThreadPoolExecutor(max_workers=10)
model = None

def create_openai_response(text, format_type="json"):
    """Минимальный ответ без лишних вычислений"""
    if format_type == "text":
        return text
    
    response = {"text": text}
    if format_type == "verbose_json":
        # Упрощенная версия без сложных вычислений
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

def init_model():
    """Инициализация модели при старте"""
    global model
    start_time = time.time()
    model = genai.GenerativeModel("gemini-2.5-flash")
    logger.info(f"⚡ Model initialized in {(time.time() - start_time)*1000:.1f}ms")

@app.route('/v1/audio/transcriptions', methods=['POST'])
def transcribe_audio():
    # 🕐 Общий таймер
    request_start = time.time()
    logger.info("🎯 New transcription request started")
    
    try:
        # 🕐 Этап 1: Получение и валидация запроса
        validation_start = time.time()
        
        api_key = request.headers.get('Authorization', '')[7:].strip()
        if not api_key:
            return {"error": {"message": "No API key"}}, 401
        
        genai.configure(api_key=api_key)
        
        audio_file = request.files.get('file')
        if not audio_file:
            return {"error": {"message": "No file"}}, 400
        
        ext = audio_file.filename.split('.')[-1].lower()
        if ext not in {'flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm'}:
            return {"error": {"message": "Bad format"}}, 400
            
        # Получаем response_format параметр
        response_format = request.form.get('response_format', 'json')
        
        validation_time = (time.time() - validation_start) * 1000
        logger.info(f"✅ Request validation: {validation_time:.1f}ms")
        
        # 🕐 Этап 2: Быстрое создание временного файла
        file_process_start = time.time()
        
        # Получаем размер файла
        audio_file.seek(0, 2)  # Переходим в конец
        file_size = audio_file.tell()
        file_size_mb = file_size / (1024 * 1024)
        audio_file.seek(0)  # Возвращаемся в начало
        
        # Создаем временный файл БЕЗ записи на диск - только в памяти
        with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as temp_file:
            # Копируем напрямую без промежуточного чтения
            audio_file.save(temp_file.name)
            temp_path = temp_file.name
        
        file_process_time = (time.time() - file_process_start) * 1000
        logger.info(f"📁 File ready ({file_size_mb:.1f}MB): {file_process_time:.1f}ms")
        
        try:
            # 🕐 Этап 3: Загрузка в Gemini
            upload_start = time.time()
            uploaded_file = genai.upload_file(temp_path)
            upload_time = (time.time() - upload_start) * 1000
            logger.info(f"⬆️  Upload to Gemini: {upload_time:.1f}ms")
            
            # 🕐 Этап 4: Транскрипция
            transcription_start = time.time()
            global model
            if model is None:
                init_model()
                
            response = model.generate_content([
                "Transcribe this audio to clean text only. Do not include timestamps, speaker labels, or any formatting. Return only the spoken words as plain text:",
                uploaded_file
            ])
            transcription_time = (time.time() - transcription_start) * 1000
            logger.info(f"🤖 Gemini transcription: {transcription_time:.1f}ms")
            
            # Теперь безопасно удаляем файлы
            try:
                genai.delete_file(uploaded_file.name)
                os.unlink(temp_path)
            except:
                pass
            
            # 📊 Общая статистика
            total_time = (time.time() - request_start) * 1000
            
            logger.info(f"""
🎯 TRANSCRIPTION COMPLETED:
📁 File: {file_size_mb:.1f}MB ({ext})
⏱️  TIMING BREAKDOWN:
   • Validation: {validation_time:.1f}ms
   • File processing: {file_process_time:.1f}ms  
   • Upload to Gemini: {upload_time:.1f}ms
   • Gemini processing: {transcription_time:.1f}ms
   • TOTAL: {total_time:.1f}ms
📝 Text length: {len(response.text)} chars
            """)
            
            # Очистка результата от timestamp-ов и лишнего форматирования  
            transcribed_text = response.text.strip()
            
            # Удаляем timestamp-ы типа "00:01", "00:02" etc.
            import re
            transcribed_text = re.sub(r'\d{2}:\d{2}\s*', '', transcribed_text)
            transcribed_text = re.sub(r'\n+', ' ', transcribed_text).strip()
            
            # Возвращаем в формате OpenAI Whisper API
            openai_response = create_openai_response(transcribed_text, response_format)
            
            if response_format == "text":
                return openai_response, 200, {'Content-Type': 'text/plain'}
            else:
                return openai_response
            
        except Exception as e:
            try:
                if 'uploaded_file' in locals():
                    genai.delete_file(uploaded_file.name)
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass
            total_time = (time.time() - request_start) * 1000
            logger.error(f"❌ Error after {total_time:.1f}ms: {str(e)}")
            raise
            
    except Exception as e:
        total_time = (time.time() - request_start) * 1000
        logger.error(f"❌ Request failed after {total_time:.1f}ms: {str(e)}")
        return {"error": {"message": str(e)}}, 500

if __name__ == '__main__':
    print("🚀 Ultra-Fast Gemini Proxy with Performance Monitoring")
    init_model()
    app.run(
        host='0.0.0.0', 
        port=8080, 
        debug=False, 
        threaded=True,
        processes=1,
        use_reloader=False
    )
else:
    # Для Cloud Run - инициализация при импорте модуля
    init_model()
